"""Unified test runner for all test types.

Provides single entry point for running Golden, Conversation, and System tests
through a pluggable executor architecture.
"""

import json
import importlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import uuid

from agents.graph import create_aml_copilot_graph
from config.agent_config import AgentsConfig
from config.settings import settings

from evaluation.core.models import (
    BaseTestCase,
    BaseTestResult,
    TestRegistry,
    TestTypeConfig,
    UnifiedEvaluationReport,
    CategoryStats,
    GoldenTestCase,
    ConversationTestCase,
    SystemTestCase,
    GoldenTestResult,
    ConversationTestResult,
    SystemTestResult,
)
from evaluation.core.executors.base import BaseTestExecutor
from evaluation.core.evaluators.registry import EvaluatorRegistry
from evaluation.core.config.models import EvaluationConfig, TestTypeEvaluationConfig


class UnifiedTestRunner:
    """Unified test runner for all test types.

    This runner replaces the 3 separate runners (test_runner.py,
    test_conversations.py, run_system_tests.py) with a single,
    modular framework.

    Key features:
    - Dynamic executor loading based on TestRegistry
    - Pluggable evaluators
    - Type-safe Pydantic models throughout
    - Unified reporting
    """

    def __init__(
        self,
        agents_config: Optional[AgentsConfig] = None,
        evaluator_registry: Optional[EvaluatorRegistry] = None,
        evaluation_config: Optional[EvaluationConfig] = None,
        test_registry: Optional[TestRegistry] = None
    ):
        """Initialize unified test runner.

        Args:
            agents_config: Agent configuration (uses default if None)
            evaluator_registry: Evaluator registry (stateless)
            evaluation_config: Evaluation config with weights/thresholds (from YAML)
            test_registry: Test type registry (uses default if None)

        Example:
            >>> from pathlib import Path
            >>> config = EvaluationConfig.from_yaml(Path("custom_config.yaml"))
            >>> runner = UnifiedTestRunner(evaluation_config=config)
        """
        self.agents_config = agents_config or settings.get_agents_config()
        self.graph = create_aml_copilot_graph(self.agents_config)
        self.evaluators = evaluator_registry or EvaluatorRegistry()
        self.eval_config = evaluation_config or EvaluationConfig.get_default()
        self.test_registry = test_registry or TestRegistry.get_default_registry()

        # Dynamically instantiate executors based on registry
        self.executors: Dict[str, BaseTestExecutor] = {}
        self._initialize_executors()

    def _initialize_executors(self):
        """Initialize executors from test registry.

        Executors are stateless - they don't own evaluators or config.
        Only pass test-specific config (timeouts, etc.).
        """
        for test_type, config in self.test_registry.test_types.items():
            executor_class = self._load_class(config.executor_class)

            # Only pass test-specific config (timeouts, max_turns)
            # NOT evaluator config (that's in EvaluationConfig)
            executor = executor_class(config=config.config)
            self.executors[test_type] = executor

    def _load_class(self, class_path: str):
        """Dynamically load class from string path.

        Args:
            class_path: Fully qualified class name (e.g., "module.Class")

        Returns:
            Class object
        """
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    def load_test_cases(
        self,
        dataset_path: Path,
        test_type: Optional[str] = None
    ) -> List[BaseTestCase]:
        """Load test cases from JSON file.

        Args:
            dataset_path: Path to JSON file containing test cases
            test_type: Explicit test type, or None to auto-detect

        Returns:
            List of test case instances (specific subclass of BaseTestCase)

        Examples:
            >>> runner = UnifiedTestRunner()
            >>> cases = runner.load_test_cases(Path("conversation_cases.json"))
            >>> all(isinstance(c, ConversationTestCase) for c in cases)
            True
        """
        with open(dataset_path) as f:
            raw_cases = json.load(f)

        # Auto-detect test type from first case if not specified
        if test_type is None:
            test_type = self._detect_test_type(raw_cases[0])

        # Get test case class from registry
        config = self.test_registry.get_config(test_type)
        test_case_class = self._load_class(config.test_case_class)

        # Parse into appropriate model
        test_cases = []
        for raw_case in raw_cases:
            # Add test_type if not present
            if "test_type" not in raw_case:
                raw_case["test_type"] = test_type

            test_cases.append(test_case_class(**raw_case))

        return test_cases

    def _detect_test_type(self, raw_case: Dict[str, Any]) -> str:
        """Auto-detect test type from JSON structure.

        Args:
            raw_case: Raw test case dictionary

        Returns:
            Test type string ("golden", "conversation", "system")
        """
        # Explicit type field
        if "test_type" in raw_case:
            return raw_case["test_type"]

        # Structural detection
        if "turns" in raw_case:
            return "conversation"
        elif raw_case.get("category") in ["off_topic", "in_scope_general", "boundary", "error_handling"]:
            return "system"
        else:
            return "golden"  # Default

    def execute_test(self, test_case: BaseTestCase) -> BaseTestResult:
        """Execute single test case with evaluation.

        Strategy Pattern Implementation:
        1. Executor runs the test (invokes graph)
        2. Runner injects evaluators one by one with their configs
        3. Runner calculates weighted scores and checks thresholds

        Args:
            test_case: Test case to execute

        Returns:
            Test result with evaluation scores (specific subclass of BaseTestResult)

        Raises:
            ValueError: If no executor registered for test type
        """
        test_type = test_case.test_type

        if test_type not in self.executors:
            raise ValueError(f"No executor registered for test type: {test_type}")

        # Step 1: Execute test (no evaluation yet)
        executor = self.executors[test_type]
        result = executor.execute(test_case, self.graph)

        # Step 2: Run evaluators if test type requires them
        test_config = self.eval_config.get_test_type_config(test_type)

        if test_config.evaluators:
            # Get agent output for evaluation
            agent_output = result.agent_output if hasattr(result, "agent_output") else {}

            scores = {}
            for eval_config in test_config.evaluators:
                if not eval_config.enabled:
                    continue

                # Get evaluator (strategy)
                evaluator = self.evaluators.get_evaluator(eval_config.name.value)
                if not evaluator:
                    continue

                # Config is ALREADY loaded by Pydantic validator
                # (from config_path if provided, or inline config, or empty dict)
                evaluator_specific_config = eval_config.config

                # Strategy pattern: Inject evaluator + config
                eval_result = executor.evaluate(
                    evaluator=evaluator,
                    evaluator_config=evaluator_specific_config,
                    test_case=test_case,
                    agent_output=agent_output
                )

                scores[eval_config.name.value] = eval_result["score"]

            # Step 3: Calculate weighted overall score
            overall_score = self._calculate_weighted_score(test_type, scores)

            # Step 4: Check thresholds and update result
            result = self._apply_scores_to_result(result, scores, overall_score, test_config)

        return result

    def _calculate_weighted_score(
        self,
        test_type: str,
        scores: Dict[str, float]
    ) -> float:
        """Calculate weighted overall score from config.

        Uses evaluator weights from EvaluationConfig (loaded from YAML).

        Args:
            test_type: Type of test
            scores: Dict mapping evaluator name to score (0-1)

        Returns:
            Weighted overall score (0-100)

        Example:
            >>> scores = {"correctness": 0.85, "completeness": 0.90, "hallucination": 0.95}
            >>> # Config: correctness=0.4, completeness=0.4, hallucination=0.2
            >>> runner._calculate_weighted_score("golden", scores)
            88.0  # (0.85*0.4 + 0.90*0.4 + 0.95*0.2) * 100
        """
        test_config = self.eval_config.get_test_type_config(test_type)

        weighted_sum = 0.0
        for eval_config in test_config.evaluators:
            if not eval_config.enabled:
                continue

            score = scores.get(eval_config.name.value, 0.0)
            weighted_sum += score * eval_config.weight

        return weighted_sum * 100  # Convert to 0-100 scale

    def _apply_scores_to_result(
        self,
        result: BaseTestResult,
        scores: Dict[str, float],
        overall_score: float,
        test_config: TestTypeEvaluationConfig
    ) -> BaseTestResult:
        """Apply evaluation scores to result and check thresholds.

        Args:
            result: Test result to update
            scores: Individual evaluator scores (0-1)
            overall_score: Weighted overall score (0-100)
            test_config: Test type configuration with thresholds

        Returns:
            Updated result with scores and pass/fail status
        """
        # Update scores (assumes result is GoldenTestResult - adapt for other types)
        if hasattr(result, "correctness_score"):
            result.correctness_score = scores.get("correctness", 0.0)
            result.completeness_score = scores.get("completeness", 0.0)
            result.hallucination_score = scores.get("hallucination", 1.0)
            result.overall_score = overall_score

        # Check thresholds
        passed = True
        for eval_config in test_config.evaluators:
            if not eval_config.enabled:
                continue

            score = scores.get(eval_config.name.value, 0.0)
            if score < eval_config.threshold:
                passed = False
                break

        result.status = "PASS" if passed else "FAIL"
        return result

    def run_test_suite(
        self,
        dataset_path: Path,
        test_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        save_results: bool = True
    ) -> UnifiedEvaluationReport:
        """Run complete test suite with unified reporting.

        Args:
            dataset_path: Path to test case JSON file
            test_type: Explicit test type, or None to auto-detect
            filters: Optional filters (priority, category, etc.)
            save_results: Whether to save results to JSON

        Returns:
            UnifiedEvaluationReport with all results

        Examples:
            >>> runner = UnifiedTestRunner()
            >>> report = runner.run_test_suite(Path("tests.json"))
            >>> print(f"Pass rate: {report.pass_rate:.1%}")
            Pass rate: 85.0%
        """
        print(f"\n{'='*70}")
        print(f"UNIFIED TEST SUITE")
        print(f"{'='*70}")
        print(f"Dataset: {dataset_path}")

        # Load test cases
        test_cases = self.load_test_cases(dataset_path, test_type)
        print(f"Loaded {len(test_cases)} test cases")

        # Apply filters if provided
        if filters:
            test_cases = self._apply_filters(test_cases, filters)
            print(f"Filtered to {len(test_cases)} test cases")

        # Detect or confirm test type
        detected_type = test_cases[0].test_type if test_cases else "unknown"
        print(f"Test Type: {detected_type}")
        print(f"{'='*70}\n")

        # Execute all tests
        results: List[BaseTestResult] = []
        for test_case in test_cases:
            try:
                result = self.execute_test(test_case)
                results.append(result)
            except Exception as e:
                # Create error result
                error_result = self._create_error_result(test_case, e)
                results.append(error_result)

        # Aggregate into report
        report = self._create_report(results, dataset_path, detected_type)

        # Print summary
        self._print_summary(report)

        # Save results if requested
        if save_results:
            self._save_report(report, dataset_path)

        return report

    def _apply_filters(
        self,
        test_cases: List[BaseTestCase],
        filters: Dict[str, Any]
    ) -> List[BaseTestCase]:
        """Apply filters to test cases.

        Args:
            test_cases: List of test cases
            filters: Filter criteria

        Returns:
            Filtered list of test cases
        """
        filtered = test_cases

        if "priority" in filters:
            filtered = [tc for tc in filtered if tc.priority == filters["priority"]]

        if "category" in filters:
            filtered = [tc for tc in filtered if tc.category == filters["category"]]

        if "test_ids" in filters:
            test_ids = set(filters["test_ids"])
            filtered = [tc for tc in filtered if tc.test_id in test_ids]

        return filtered

    def _create_error_result(
        self,
        test_case: BaseTestCase,
        exception: Exception
    ) -> BaseTestResult:
        """Create error result for failed test execution.

        Args:
            test_case: Test case that failed
            exception: Exception that occurred

        Returns:
            BaseTestResult with ERROR status
        """
        # Create appropriate result type based on test type
        if test_case.test_type == "golden":
            return GoldenTestResult(
                test_id=test_case.test_id,
                test_type="golden",
                status="ERROR",
                agent_output={"error": str(exception)},
                execution_time_seconds=0.0,
                correctness_score=0.0,
                completeness_score=0.0,
                hallucination_score=0.0,
                overall_score=0.0,
                timestamp=datetime.now(),
                error_message=str(exception)
            )
        elif test_case.test_type == "conversation":
            return ConversationTestResult(
                test_id=test_case.test_id,
                test_type="conversation",
                status="ERROR",
                execution_time_seconds=0.0,
                timestamp=datetime.now(),
                error_message=str(exception)
            )
        else:  # system
            return SystemTestResult(
                test_id=test_case.test_id,
                test_type="system",
                status="ERROR",
                execution_time_seconds=0.0,
                timestamp=datetime.now(),
                error_message=str(exception)
            )

    def _create_report(
        self,
        results: List[BaseTestResult],
        dataset_path: Path,
        test_type: str
    ) -> UnifiedEvaluationReport:
        """Create unified evaluation report from results.

        Args:
            results: List of test results
            dataset_path: Path to dataset
            test_type: Type of tests run

        Returns:
            UnifiedEvaluationReport
        """
        # Calculate summary statistics
        total = len(results)
        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status == "FAIL")
        errors = sum(1 for r in results if r.status == "ERROR")
        pass_rate = passed / total if total > 0 else 0.0

        # Calculate per-category stats
        results_by_category: Dict[str, CategoryStats] = {}
        category_results: Dict[str, List[BaseTestResult]] = {}

        for result in results:
            # Get category from test_id prefix (e.g., CONV_REF_001 -> CONV_REF)
            category = "_".join(result.test_id.split("_")[:2])

            if category not in category_results:
                category_results[category] = []
            category_results[category].append(result)

        for category, cat_results in category_results.items():
            cat_total = len(cat_results)
            cat_passed = sum(1 for r in cat_results if r.status == "PASS")
            cat_failed = sum(1 for r in cat_results if r.status == "FAIL")
            cat_errors = sum(1 for r in cat_results if r.status == "ERROR")

            results_by_category[category] = CategoryStats(
                total=cat_total,
                passed=cat_passed,
                failed=cat_failed,
                errors=cat_errors,
                pass_rate=cat_passed / cat_total if cat_total > 0 else 0.0
            )

        # Calculate metrics (test-type-specific)
        metrics = {}
        if test_type == "golden":
            golden_results = [r for r in results if isinstance(r, GoldenTestResult)]
            if golden_results:
                metrics["avg_correctness"] = sum(r.correctness_score for r in golden_results) / len(golden_results)
                metrics["avg_completeness"] = sum(r.completeness_score for r in golden_results) / len(golden_results)
                metrics["avg_hallucination"] = sum(r.hallucination_score for r in golden_results) / len(golden_results)
                metrics["avg_overall_score"] = sum(r.overall_score for r in golden_results) / len(golden_results)

        # Create report
        return UnifiedEvaluationReport(
            report_id=f"report_{uuid.uuid4().hex[:8]}",
            run_date=datetime.now(),
            test_type=test_type,
            total_cases=total,
            passed=passed,
            failed=failed,
            errors=errors,
            pass_rate=pass_rate,
            metrics=metrics,
            results_by_category=results_by_category,
            test_results=results,
            action_items=[],  # Will be populated by get_recommendations()
            dataset_path=str(dataset_path),
            execution_time_seconds=sum(r.execution_time_seconds for r in results)
        )

    def _print_summary(self, report: UnifiedEvaluationReport):
        """Print test suite summary.

        Args:
            report: Evaluation report
        """
        print(f"\n{'='*70}")
        print(f"TEST SUITE SUMMARY")
        print(f"{'='*70}")
        print(f"Total: {report.total_cases}")
        print(f"Passed: {report.passed} ({report.pass_rate:.1%})")
        print(f"Failed: {report.failed}")
        print(f"Errors: {report.errors}")
        print(f"\nBy Category:")
        for category, stats in report.results_by_category.items():
            print(f"  {category}: {stats.passed}/{stats.total} ({stats.pass_rate:.1%})")
        print(f"{'='*70}\n")

    def _save_report(self, report: UnifiedEvaluationReport, dataset_path: Path):
        """Save report to JSON file.

        Args:
            report: Evaluation report
            dataset_path: Original dataset path
        """
        from evaluation.config import RESULTS_DIR, get_result_file_path

        RESULTS_DIR.mkdir(exist_ok=True, parents=True)

        # Generate filename
        results_file = get_result_file_path(
            "unified_evaluation",
            category=report.test_type,
            timestamped=True
        )

        # Save timestamped file
        with open(results_file, 'w') as f:
            json.dump(report.dict(), f, indent=2, default=str)

        # Save as "latest"
        latest_file = get_result_file_path(
            "unified_evaluation",
            category=report.test_type,
            timestamped=False
        )
        with open(latest_file, 'w') as f:
            json.dump(report.dict(), f, indent=2, default=str)

        print(f"📊 Results saved to: {results_file}")
        print(f"📊 Latest results: {latest_file}")
