"""Golden test executor for AML domain knowledge tests.

Executes single-turn tests that evaluate the agent's ability to identify
AML typologies, red flags, and provide compliant analysis.
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime

from agents.state import AMLCopilotState
from evaluation.core.models import GoldenTestCase, GoldenTestResult
from evaluation.core.executors.base import BaseTestExecutor


class GoldenTestExecutor(BaseTestExecutor):
    """Executor for golden/business test cases.

    Uses specialized evaluators (correctness, completeness, hallucination)
    to score agent outputs across multiple dimensions.
    """

    def __init__(
        self,
        evaluator_registry: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize golden test executor.

        Args:
            evaluator_registry: Registry of evaluators for scoring
            config: Test-specific configuration
        """
        super().__init__(config)
        self.evaluator_registry = evaluator_registry

    def execute(
        self,
        test_case: GoldenTestCase,
        graph: Any
    ) -> GoldenTestResult:
        """Execute a golden test case.

        Args:
            test_case: Golden test case to execute
            graph: LangGraph compiled graph

        Returns:
            GoldenTestResult with evaluation scores
        """
        print(f"\n{'='*60}")
        print(f"Executing Test Case: {test_case.test_id}")
        print(f"Category: {test_case.category} | Priority: {test_case.priority}")
        print(f"Description: {test_case.description}")
        print(f"{'='*60}\n")

        # Create initial state
        initial_state = self._create_initial_state(test_case)

        # Execute workflow
        start_time = time.time()
        try:
            # Invoke the graph (single-turn execution)
            final_state = graph.invoke(initial_state)
            execution_time = time.time() - start_time

            # Extract agent output
            agent_output = self._extract_agent_output(final_state)

            # Evaluate the output
            evaluation = self._evaluate_output(test_case, agent_output, final_state)

            # Create test result
            result = GoldenTestResult(
                test_id=test_case.test_id,
                test_type="golden",
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
            return GoldenTestResult(
                test_id=test_case.test_id,
                test_type="golden",
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
                timestamp=datetime.now(),
                error_message=str(e)
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

    def _validate_output(
        self,
        state: AMLCopilotState,
        test_case: GoldenTestCase
    ) -> Dict[str, Any]:
        """Validate output (called by _evaluate_output).

        Args:
            state: Final state
            test_case: Test case

        Returns:
            Validation results
        """
        # For golden tests, validation is part of evaluation
        # This method satisfies the abstract base class requirement
        return {}

    def _evaluate_output(
        self,
        test_case: GoldenTestCase,
        agent_output: Dict[str, Any],
        final_state: AMLCopilotState
    ) -> Dict[str, Any]:
        """Evaluate agent output against expected output.

        Uses evaluators from registry if available, otherwise falls back
        to basic evaluation.

        Args:
            test_case: Golden test case with expectations
            agent_output: Actual agent output
            final_state: Final state from workflow

        Returns:
            Dictionary with evaluation results
        """
        expected = test_case.expected_output
        criteria = test_case.evaluation_criteria

        # If we have evaluators, use them
        if self.evaluator_registry:
            return self._evaluate_with_evaluators(
                test_case, agent_output, final_state
            )
        else:
            # Fall back to basic evaluation
            return self._basic_evaluation(
                expected, criteria, agent_output
            )

    def _evaluate_with_evaluators(
        self,
        test_case: GoldenTestCase,
        agent_output: Dict[str, Any],
        final_state: AMLCopilotState
    ) -> Dict[str, Any]:
        """Evaluate using specialized evaluators.

        TODO: Implement full evaluator integration once registry is created.

        Args:
            test_case: Test case
            agent_output: Agent output
            final_state: Final state

        Returns:
            Evaluation results
        """
        # Get evaluators for golden test type
        evaluators = self.evaluator_registry.get_evaluators_for_test_type("golden")

        # Initialize evaluation results
        evaluation = {
            "status": "PASS",
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

        # Run each evaluator
        # TODO: Implement evaluator calls when registry is complete
        # For now, fall back to basic evaluation
        expected = test_case.expected_output
        criteria = test_case.evaluation_criteria
        evaluation.update(self._basic_evaluation(expected, criteria, agent_output))

        return evaluation

    def _basic_evaluation(
        self,
        expected: Any,
        criteria: Any,
        agent_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Basic evaluation without specialized evaluators.

        Provides minimal evaluation capability as fallback.

        Args:
            expected: Expected output from test case
            criteria: Evaluation criteria
            agent_output: Complete agent output

        Returns:
            Evaluation scores and details
        """
        compliance_analysis = agent_output.get("compliance_analysis", {})

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

        # Calculate overall score (basic)
        result["overall_score"] = (
            result["correctness_score"] * 40 +
            result["completeness_score"] * 40 +
            result["hallucination_score"] * 20
        )

        # Determine pass/fail
        if len(result["fail_reasons"]) > 0:
            result["status"] = "FAIL"
        elif result["overall_score"] < criteria.min_passing_score:
            result["status"] = "FAIL"
            result["fail_reasons"].append(
                f"Overall score {result['overall_score']:.1f} below minimum {criteria.min_passing_score}"
            )
        else:
            result["status"] = "PASS"

        return result

    def _print_result_summary(self, result: GoldenTestResult):
        """Print test result summary.

        Args:
            result: Test result to print
        """
        status_symbol = "✅" if result.status == "PASS" else "❌"
        print(f"\n{status_symbol} Test {result.test_id}: {result.status}")
        print(f"   Overall Score: {result.overall_score:.1f}/100")
        print(f"   Correctness: {result.correctness_score:.2f}")
        print(f"   Completeness: {result.completeness_score:.2f}")
        print(f"   Hallucination: {result.hallucination_score:.2f}")
        print(f"   Execution Time: {result.execution_time_seconds:.2f}s")

        if result.fail_reasons:
            print(f"\n   Failure Reasons:")
            for reason in result.fail_reasons:
                print(f"     - {reason}")
