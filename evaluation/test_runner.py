"""Test runner for executing golden test cases and generating evaluation reports."""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from agents.graph import create_aml_copilot_graph
from agents.state import AMLCopilotState
from config.agent_config import AgentsConfig
from config.settings import settings
from evaluation.config import (
    RESULTS_DIR,
    EVALUATION_TESTS_LATEST_FILE,
    get_result_file_path
)
from evaluation.models import (
    GoldenTestCase,
    TestResult,
    EvaluationReport,
    BaselineSnapshot
)


class AgentEvaluationRunner:
    """Run golden test cases and collect evaluation metrics.

    This runner executes test cases through the complete agent workflow
    and evaluates outputs against ground truth expectations.
    """

    def __init__(
        self,
        agents_config: Optional[AgentsConfig] = None,
        evaluators: Optional[Dict[str, Any]] = None
    ):
        """Initialize the evaluation runner.

        Args:
            agents_config: Configuration for agents (uses default if None)
            evaluators: Dictionary of evaluator instances (will create defaults if None)
        """
        self.agents_config = agents_config or settings.get_agents_config()
        self.graph = create_aml_copilot_graph(self.agents_config)

        # Evaluators will be injected (or created with defaults)
        self.evaluators = evaluators or {}

    def load_golden_test_cases(
        self,
        dataset_path: Path,
        category: Optional[str] = None,
        priority: Optional[str] = None
    ) -> List[GoldenTestCase]:
        """Load golden test cases from JSON file.

        Args:
            dataset_path: Path to JSON file containing test cases
            category: Optional filter by category (structuring, layering, etc.)
            priority: Optional filter by priority (HIGH, MEDIUM, LOW)

        Returns:
            List of GoldenTestCase objects
        """
        with open(dataset_path, 'r') as f:
            raw_cases = json.load(f)

        # Parse into GoldenTestCase models
        test_cases = [GoldenTestCase(**case) for case in raw_cases]

        # Apply filters
        if category:
            test_cases = [tc for tc in test_cases if tc.category == category]

        if priority:
            test_cases = [tc for tc in test_cases if tc.priority == priority]

        return test_cases

    def create_initial_state(self, test_case: GoldenTestCase) -> AMLCopilotState:
        """Create initial state from test case input.

        Args:
            test_case: Golden test case

        Returns:
            AMLCopilotState ready for agent execution
        """
        test_input = test_case.input

        # Build initial state
        state: AMLCopilotState = {
            "messages": [],
            "user_query": test_input.user_query,
            "context": test_input.context,
            "next_agent": "coordinator",
            "current_step": "start",
            "intent": None,
            "retrieved_data": None,
            "compliance_analysis": None,
            "ml_model_output": test_input.ml_output,
            "final_response": None,
            "review_status": None,
            "review_feedback": None,
            "additional_query": None,
            "review_agent_id": None,
            "review_attempts": 0,
            "session_id": f"test_{test_case.test_id}_{uuid.uuid4().hex[:8]}",
            "started_at": datetime.now().isoformat(),
            "completed": False
        }

        return state

    def execute_test_case(self, test_case: GoldenTestCase) -> TestResult:
        """Execute a single test case through the agent workflow.

        Args:
            test_case: Golden test case to execute

        Returns:
            TestResult with execution details and evaluation scores
        """
        print(f"\n{'='*60}")
        print(f"Executing Test Case: {test_case.test_id}")
        print(f"Category: {test_case.category} | Priority: {test_case.priority}")
        print(f"Description: {test_case.description}")
        print(f"{'='*60}\n")

        # Create initial state
        initial_state = self.create_initial_state(test_case)

        # Execute workflow
        start_time = time.time()
        try:
            # Invoke the graph (this runs the complete workflow)
            final_state = self.graph.invoke(initial_state)
            execution_time = time.time() - start_time

            # Extract agent output
            agent_output = self._extract_agent_output(final_state)

            # Evaluate the output
            evaluation = self._evaluate_output(test_case, agent_output, final_state)

            # Create test result
            result = TestResult(
                test_id=test_case.test_id,
                status=evaluation["status"],
                agent_output=agent_output,
                execution_time_seconds=execution_time,
                tokens_used=None,  # TODO: Track token usage
                correctness_score=evaluation["correctness_score"],
                completeness_score=evaluation["completeness_score"],
                hallucination_score=evaluation["hallucination_score"],
                overall_score=evaluation["overall_score"],
                typology_matches=evaluation["typology_matches"],
                red_flag_matches=evaluation["red_flag_matches"],
                key_facts_covered=evaluation["key_facts_covered"],
                key_facts_missing=evaluation["key_facts_missing"],
                hallucinations_detected=evaluation["hallucinations_detected"],
                pass_reasons=evaluation["pass_reasons"],
                fail_reasons=evaluation["fail_reasons"],
                warnings=evaluation["warnings"],
                timestamp=datetime.now()
            )

            self._print_result_summary(result)
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            print(f"❌ ERROR: Test case {test_case.test_id} failed with exception: {e}")

            # Return error result
            return TestResult(
                test_id=test_case.test_id,
                status="ERROR",
                agent_output={"error": str(e)},
                execution_time_seconds=execution_time,
                tokens_used=None,
                correctness_score=0.0,
                completeness_score=0.0,
                hallucination_score=0.0,
                overall_score=0.0,
                typology_matches={},
                red_flag_matches={},
                key_facts_covered=[],
                key_facts_missing=[],
                hallucinations_detected=[],
                pass_reasons=[],
                fail_reasons=[f"Exception during execution: {str(e)}"],
                warnings=[],
                timestamp=datetime.now()
            )

    def _extract_agent_output(self, final_state: AMLCopilotState) -> Dict[str, Any]:
        """Extract relevant output from final state.

        Args:
            final_state: Final state after workflow execution

        Returns:
            Dictionary with agent outputs
        """
        return {
            "final_response": final_state.get("final_response"),
            "compliance_analysis": final_state.get("compliance_analysis"),
            "review_status": final_state.get("review_status"),
            "review_feedback": final_state.get("review_feedback"),
            "ml_model_output": final_state.get("ml_model_output"),
            "session_id": final_state.get("session_id"),
            "completed": final_state.get("completed", False)
        }

    def _evaluate_output(
        self,
        test_case: GoldenTestCase,
        agent_output: Dict[str, Any],
        final_state: AMLCopilotState
    ) -> Dict[str, Any]:
        """Evaluate agent output against expected output.

        This is the core evaluation logic that uses evaluators
        to score the output.

        Args:
            test_case: Golden test case with expectations
            agent_output: Actual agent output
            final_state: Final state from workflow

        Returns:
            Dictionary with evaluation results
        """
        expected = test_case.expected_output
        criteria = test_case.evaluation_criteria
        compliance_analysis = agent_output.get("compliance_analysis", {})

        evaluation = {
            "status": "PASS",
            "correctness_score": 0.0,
            "completeness_score": 0.0,
            "hallucination_score": 1.0,  # Start at 1.0 (no hallucinations)
            "overall_score": 0.0,
            "typology_matches": {},
            "red_flag_matches": {},
            "key_facts_covered": [],
            "key_facts_missing": [],
            "hallucinations_detected": [],
            "pass_reasons": [],
            "fail_reasons": [],
            "warnings": []
        }

        # If we have evaluators, use them
        if self.evaluators:
            # Use injected evaluators
            # (Will implement evaluator integration in next step)
            pass
        else:
            # Basic evaluation without specialized evaluators
            evaluation.update(self._basic_evaluation(
                expected, criteria, compliance_analysis, agent_output
            ))

        # Determine PASS/FAIL status based on results
        if len(evaluation["fail_reasons"]) > 0:
            evaluation["status"] = "FAIL"
        elif evaluation["overall_score"] < criteria.min_passing_score:
            evaluation["status"] = "FAIL"
            evaluation["fail_reasons"].append(
                f"Overall score {evaluation['overall_score']:.1f} below minimum passing score {criteria.min_passing_score}"
            )
        else:
            evaluation["status"] = "PASS"

        return evaluation

    def _basic_evaluation(
        self,
        expected: Any,
        criteria: Any,
        compliance_analysis: Dict[str, Any],
        agent_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Basic evaluation without specialized evaluators.

        This provides minimal evaluation capability until
        specialized evaluators are implemented.

        Args:
            expected: Expected output from test case
            criteria: Evaluation criteria
            compliance_analysis: Compliance analysis from agent
            agent_output: Complete agent output

        Returns:
            Evaluation scores and details
        """
        result = {
            "correctness_score": 0.0,
            "completeness_score": 0.0,
            "hallucination_score": 1.0,
            "overall_score": 0.0,
            "typology_matches": {},
            "red_flag_matches": {},
            "key_facts_covered": [],
            "key_facts_missing": [],
            "hallucinations_detected": [],
            "pass_reasons": [],
            "fail_reasons": [],
            "warnings": []
        }

        # Extract typologies from compliance analysis
        agent_typologies = compliance_analysis.get("typologies", []) if compliance_analysis else []
        expected_typologies = expected.typologies_identified if expected else []

        # Evaluate typology identification
        if criteria.must_identify_typology and expected_typologies:
            typology_correct = any(
                exp_typ.lower() in [a_typ.lower() for a_typ in agent_typologies]
                for exp_typ in expected_typologies
            )

            if typology_correct:
                result["correctness_score"] += 0.5
                result["pass_reasons"].append("Correctly identified expected typology")
            else:
                result["fail_reasons"].append(
                    f"Failed to identify expected typologies: {expected_typologies}"
                )
                result["warnings"].append(
                    f"Expected: {expected_typologies}, Got: {agent_typologies}"
                )

        # Extract red flags
        agent_red_flags = []
        # Red flags might be in the analysis text or in a structured field
        # For now, we'll check if they appear in the analysis text
        analysis_text = compliance_analysis.get("analysis", "") if compliance_analysis else ""
        expected_red_flags = expected.red_flags_identified if expected else []

        if criteria.must_identify_red_flags and expected_red_flags:
            red_flags_found = sum(
                1 for rf in expected_red_flags
                if rf.lower() in analysis_text.lower()
            )

            if red_flags_found > 0:
                result["correctness_score"] += 0.3
                result["pass_reasons"].append(f"Identified {red_flags_found} expected red flags")
            else:
                result["fail_reasons"].append("Failed to identify expected red flags")

        # Key facts coverage
        if expected and expected.key_facts_mentioned:
            final_response = agent_output.get("final_response", "")
            analysis_text_combined = f"{final_response} {analysis_text}"

            for fact in expected.key_facts_mentioned:
                if fact.lower() in analysis_text_combined.lower():
                    result["key_facts_covered"].append(fact)
                else:
                    result["key_facts_missing"].append(fact)

            coverage = len(result["key_facts_covered"]) / len(expected.key_facts_mentioned)
            result["completeness_score"] = coverage

            if coverage >= criteria.min_key_facts_coverage:
                result["pass_reasons"].append(
                    f"Key facts coverage: {coverage:.1%} (meets minimum {criteria.min_key_facts_coverage:.1%})"
                )
            else:
                result["fail_reasons"].append(
                    f"Insufficient key facts coverage: {coverage:.1%} < {criteria.min_key_facts_coverage:.1%}"
                )

        # Check for things that should NOT be included
        if expected and expected.should_not_include:
            final_response = agent_output.get("final_response", "")
            analysis_text_combined = f"{final_response} {analysis_text}"

            for bad_item in expected.should_not_include:
                if bad_item.lower() in analysis_text_combined.lower():
                    result["hallucinations_detected"].append(bad_item)
                    result["hallucination_score"] -= 0.2
                    result["fail_reasons"].append(f"Output contains prohibited content: {bad_item}")

        # Ensure hallucination score doesn't go below 0
        result["hallucination_score"] = max(0.0, result["hallucination_score"])

        # Calculate overall score
        result["overall_score"] = (
            result["correctness_score"] * 40 +
            result["completeness_score"] * 40 +
            result["hallucination_score"] * 20
        )

        return result

    def _print_result_summary(self, result: TestResult):
        """Print a summary of the test result.

        Args:
            result: Test result to summarize
        """
        status_emoji = "✅" if result.status == "PASS" else "❌" if result.status == "FAIL" else "⚠️"
        print(f"\n{status_emoji} Test Result: {result.status}")
        print(f"   Execution Time: {result.execution_time_seconds:.2f}s")
        print(f"   Overall Score: {result.overall_score:.1f}/100")
        print(f"   - Correctness: {result.correctness_score:.2f}")
        print(f"   - Completeness: {result.completeness_score:.2f}")
        print(f"   - Hallucination: {result.hallucination_score:.2f}")

        if result.pass_reasons:
            print(f"\n   ✓ Pass Reasons:")
            for reason in result.pass_reasons:
                print(f"     - {reason}")

        if result.fail_reasons:
            print(f"\n   ✗ Fail Reasons:")
            for reason in result.fail_reasons:
                print(f"     - {reason}")

        if result.warnings:
            print(f"\n   ⚠ Warnings:")
            for warning in result.warnings:
                print(f"     - {warning}")

    def run_evaluation_suite(
        self,
        dataset_path: Path,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        baseline_path: Optional[Path] = None,
        save_results: bool = True
    ) -> EvaluationReport:
        """Run complete evaluation suite.

        Args:
            dataset_path: Path to golden test cases JSON
            category: Optional category filter
            priority: Optional priority filter
            baseline_path: Optional path to baseline snapshot for regression detection
            save_results: Whether to automatically save results to JSON (default: True)

        Returns:
            EvaluationReport with complete results
        """
        print(f"\n{'='*70}")
        print(f"AML COPILOT - GOLDEN TEST SUITE EVALUATION")
        print(f"{'='*70}")
        print(f"Dataset: {dataset_path}")
        if category:
            print(f"Category Filter: {category}")
        if priority:
            print(f"Priority Filter: {priority}")
        print(f"{'='*70}\n")

        # Load test cases
        test_cases = self.load_golden_test_cases(dataset_path, category, priority)
        print(f"Loaded {len(test_cases)} test cases\n")

        # Execute all test cases
        results: List[TestResult] = []
        for test_case in test_cases:
            result = self.execute_test_case(test_case)
            results.append(result)

        # Generate report
        report = self._generate_report(results, baseline_path)

        # Print report summary
        self._print_report_summary(report)

        # Auto-save results (similar to conversation tests)
        if save_results:
            RESULTS_DIR.mkdir(exist_ok=True)

            # Save timestamped file
            results_file = get_result_file_path(
                "evaluation_tests", category, timestamped=True
            )
            self.save_report(report, results_file)

            # Save as "latest" for easy access
            if category:
                # Categorized latest file
                latest_file = get_result_file_path(
                    "evaluation_tests", category, timestamped=False
                )
            else:
                # Use predefined constant for non-categorized
                latest_file = EVALUATION_TESTS_LATEST_FILE
            
            self.save_report(report, latest_file)
            print(f"📊 Latest results: {latest_file}")

        return report

    def _generate_report(
        self,
        results: List[TestResult],
        baseline_path: Optional[Path] = None
    ) -> EvaluationReport:
        """Generate evaluation report from test results.

        Args:
            results: List of test results
            baseline_path: Optional baseline for regression comparison

        Returns:
            EvaluationReport
        """
        total = len(results)
        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status == "FAIL")
        errors = sum(1 for r in results if r.status == "ERROR")

        # Calculate aggregate metrics
        avg_correctness = sum(r.correctness_score for r in results) / total if total > 0 else 0.0
        avg_completeness = sum(r.completeness_score for r in results) / total if total > 0 else 0.0
        avg_hallucination = sum(r.hallucination_score for r in results) / total if total > 0 else 0.0
        avg_overall = sum(r.overall_score for r in results) / total if total > 0 else 0.0

        # Regression detection (if baseline provided)
        regressions = []
        improvements = []
        if baseline_path and baseline_path.exists():
            with open(baseline_path, 'r') as f:
                baseline_data = json.load(f)
                baseline = BaselineSnapshot(**baseline_data)

                # Compare results
                for result in results:
                    if result.test_id in baseline.results:
                        baseline_result = baseline.results[result.test_id]

                        # Check for regression (score dropped by >5 points)
                        if result.overall_score < baseline_result.overall_score - 5:
                            regressions.append(
                                f"{result.test_id}: Score {baseline_result.overall_score:.1f} → {result.overall_score:.1f}"
                            )

                        # Check for improvement (score increased by >5 points)
                        if result.overall_score > baseline_result.overall_score + 5:
                            improvements.append(
                                f"{result.test_id}: Score {baseline_result.overall_score:.1f} → {result.overall_score:.1f}"
                            )

        # Action items
        action_items = []
        if failed > 0:
            action_items.append(f"Investigate {failed} failed test cases")
        if errors > 0:
            action_items.append(f"Fix {errors} test execution errors")
        if regressions:
            action_items.append(f"Address {len(regressions)} regressions detected")

        report = EvaluationReport(
            report_id=f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            run_date=datetime.now(),
            version="current",
            baseline_version=None,
            total_cases=total,
            passed=passed,
            failed=failed,
            errors=errors,
            pass_rate=passed / total if total > 0 else 0.0,
            avg_correctness_score=avg_correctness,
            avg_completeness_score=avg_completeness,
            avg_hallucination_score=avg_hallucination,
            avg_overall_score=avg_overall,
            results_by_category={},  # TODO: Group by category
            test_results=results,
            regressions_detected=regressions,
            improvements_detected=improvements,
            action_items=action_items
        )

        return report

    def _print_report_summary(self, report: EvaluationReport):
        """Print evaluation report summary.

        Args:
            report: Evaluation report
        """
        print(f"\n{'='*70}")
        print(f"EVALUATION REPORT SUMMARY")
        print(f"{'='*70}")
        print(f"Report ID: {report.report_id}")
        print(f"Run Date: {report.run_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nResults:")
        print(f"  Total Cases: {report.total_cases}")
        print(f"  Passed: {report.passed} ({report.pass_rate:.1%})")
        print(f"  Failed: {report.failed}")
        print(f"  Errors: {report.errors}")
        print(f"\nAggregate Metrics:")
        print(f"  Avg Correctness: {report.avg_correctness_score:.2f}")
        print(f"  Avg Completeness: {report.avg_completeness_score:.2f}")
        print(f"  Avg Hallucination: {report.avg_hallucination_score:.2f}")
        print(f"  Avg Overall Score: {report.avg_overall_score:.1f}/100")

        if report.regressions_detected:
            print(f"\n⚠️  Regressions Detected ({len(report.regressions_detected)}):")
            for reg in report.regressions_detected:
                print(f"  - {reg}")

        if report.improvements_detected:
            print(f"\n✅ Improvements Detected ({len(report.improvements_detected)}):")
            for imp in report.improvements_detected:
                print(f"  - {imp}")

        if report.action_items:
            print(f"\n📋 Action Items:")
            for item in report.action_items:
                print(f"  - {item}")

        print(f"\n{'='*70}\n")

    def save_report(self, report: EvaluationReport, output_path: Path):
        """Save evaluation report to JSON file.

        Args:
            report: Evaluation report
            output_path: Path to save report
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(report.dict(), f, indent=2, default=str)

        print(f"Report saved to: {output_path}")


# Convenience function for quick evaluation
def run_quick_evaluation(
    dataset_path: str = "evaluation/golden_datasets/structuring_cases.json",
    category: Optional[str] = None,
    priority: Optional[str] = None,
    min_passing_score: Optional[float] = None
) -> EvaluationReport:
    """Quick evaluation run with default configuration.

    Args:
        dataset_path: Path to golden test cases
        category: Optional category filter
        priority: Optional priority filter
        min_passing_score: Optional minimum passing score override (0-100).
                          If provided, overrides the default threshold in test cases.

    Returns:
        EvaluationReport
    """
    runner = AgentEvaluationRunner()

    # If threshold is provided, we need to override it in test cases
    if min_passing_score is not None:
        # Load test cases and override threshold
        test_cases = runner.load_golden_test_cases(
            Path(dataset_path),
            category=category,
            priority=priority
        )
        # Override the min_passing_score for all test cases
        for test_case in test_cases:
            test_case.evaluation_criteria.min_passing_score = min_passing_score

        # Execute manually
        print(f"\n{'='*70}")
        print(f"AML COPILOT - GOLDEN TEST SUITE EVALUATION")
        print(f"{'='*70}")
        print(f"Dataset: {dataset_path}")
        print(f"Min Passing Score: {min_passing_score}/100")
        if category:
            print(f"Category Filter: {category}")
        if priority:
            print(f"Priority Filter: {priority}")
        print(f"{'='*70}\n")
        print(f"Loaded {len(test_cases)} test cases\n")

        results = []
        for test_case in test_cases:
            result = runner.execute_test_case(test_case)
            results.append(result)

        report = runner._generate_report(results, baseline_path=None)
        runner._print_report_summary(report)

        # Auto-save results
        from evaluation.config import RESULTS_DIR, EVALUATION_TESTS_LATEST_FILE, get_result_file_path
        RESULTS_DIR.mkdir(exist_ok=True)
        results_file = get_result_file_path("evaluation_tests", category, timestamped=True)
        runner.save_report(report, results_file)
        latest_file = EVALUATION_TESTS_LATEST_FILE if not category else get_result_file_path("evaluation_tests", category, timestamped=False)
        runner.save_report(report, latest_file)
        print(f"📊 Latest results: {latest_file}")
    else:
        # Use default behavior
        report = runner.run_evaluation_suite(
            Path(dataset_path),
            category=category,
            priority=priority
        )

    return report
