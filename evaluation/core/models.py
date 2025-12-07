"""Unified data models for the AML Copilot evaluation framework.

This module provides Pydantic models for all test types (Golden, Conversation, System)
with a common base structure and specialized extensions.
"""

from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# Test Registry - Maps test types to executor/model configurations
# ============================================================================

class TestTypeConfig(BaseModel):
    """Configuration for a test type with executor mapping.

    This model ties together test type, executor implementation, test case model,
    result model, and test-specific configuration.
    """
    test_type: Literal["golden", "conversation", "system"]
    executor_class: str = Field(..., description="Fully qualified class name for executor")
    test_case_class: str = Field(..., description="Fully qualified class name for test case model")
    result_class: str = Field(..., description="Fully qualified class name for result model")
    requires_evaluators: bool = Field(..., description="Whether this test type uses evaluators")
    description: str = Field(..., description="Human-readable description of test type")

    # Test-specific configuration
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Test-type-specific config (timeouts, max_turns, etc.)"
    )


class TestRegistry(BaseModel):
    """Registry mapping test types to configurations.

    This provides a centralized, declarative way to configure test types
    and their corresponding executors, models, and settings.
    """
    test_types: Dict[str, TestTypeConfig]

    @classmethod
    def get_default_registry(cls) -> "TestRegistry":
        """Get default test type registry with all built-in test types."""
        return cls(test_types={
            "golden": TestTypeConfig(
                test_type="golden",
                executor_class="evaluation.core.executors.golden.GoldenTestExecutor",
                test_case_class="evaluation.core.models.GoldenTestCase",
                result_class="evaluation.core.models.GoldenTestResult",
                requires_evaluators=True,
                description="Single-turn AML domain knowledge tests",
                config={"timeout_seconds": 60}
            ),
            "conversation": TestTypeConfig(
                test_type="conversation",
                executor_class="evaluation.core.executors.conversation.ConversationTestExecutor",
                test_case_class="evaluation.core.models.ConversationTestCase",
                result_class="evaluation.core.models.ConversationTestResult",
                requires_evaluators=False,
                description="Multi-turn conversation tests",
                config={"max_turns": 10, "timeout_seconds": 120}
            ),
            "system": TestTypeConfig(
                test_type="system",
                executor_class="evaluation.core.executors.system.SystemTestExecutor",
                test_case_class="evaluation.core.models.SystemTestCase",
                result_class="evaluation.core.models.SystemTestResult",
                requires_evaluators=False,
                description="Boundary and error handling tests",
                config={"timeout_seconds": 30}
            )
        })

    def get_config(self, test_type: str) -> TestTypeConfig:
        """Get configuration for a test type.

        Args:
            test_type: Type of test ("golden", "conversation", "system")

        Returns:
            TestTypeConfig for the requested type

        Raises:
            ValueError: If test type is not registered
        """
        if test_type not in self.test_types:
            raise ValueError(
                f"Unknown test type: {test_type}. "
                f"Available types: {list(self.test_types.keys())}"
            )
        return self.test_types[test_type]


# ============================================================================
# Shared Input/Output/Criteria Models
# ============================================================================

class TestInput(BaseModel):
    """Input data for a test case."""
    user_query: str = Field(..., description="User's natural language query")
    context: Dict[str, Any] = Field(..., description="Session context (cif_no, alert_id, etc.)")
    ml_output: Optional[Dict[str, Any]] = Field(None, description="ML model output fixture")
    customer_data: Optional[Dict[str, Any]] = Field(None, description="Customer profile data")
    transaction_data: Optional[List[Dict[str, Any]]] = Field(None, description="Transaction history")
    alert_data: Optional[Dict[str, Any]] = Field(None, description="Alert information")


class ExpectedOutput(BaseModel):
    """Expected output from the agent (ground truth)."""
    typologies_identified: List[str] = Field(
        default_factory=list,
        description="Expected typologies (e.g., ['structuring', 'layering'])"
    )
    red_flags_identified: List[str] = Field(
        default_factory=list,
        description="Expected red flags detected"
    )
    risk_assessment: Optional[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = Field(
        None,
        description="Expected risk level"
    )
    key_facts_mentioned: List[str] = Field(
        default_factory=list,
        description="Key facts that must be mentioned in output"
    )
    recommendations_include: List[str] = Field(
        default_factory=list,
        description="Recommendations that should be provided"
    )
    regulatory_citations: List[str] = Field(
        default_factory=list,
        description="Expected regulatory references (e.g., '31 USC 5324')"
    )
    should_not_include: List[str] = Field(
        default_factory=list,
        description="Things that should NOT appear in output (hallucinations, etc.)"
    )
    disposition: Optional[Literal["CLOSE", "ESCALATE", "FILE_SAR"]] = Field(
        None,
        description="Expected disposition for alert review cases"
    )


class EvaluationCriteria(BaseModel):
    """Criteria for evaluating agent output."""
    must_identify_typology: bool = Field(True, description="Must identify correct typology")
    must_identify_red_flags: bool = Field(True, description="Must detect red flags")
    must_cite_regulations: bool = Field(True, description="Must cite appropriate regulations")
    must_provide_recommendations: bool = Field(True, description="Must provide actionable recommendations")
    must_not_hallucinate: bool = Field(True, description="Must not invent facts")
    must_explain_attribution_chain: bool = Field(False, description="Must explain typology → red flags → features")
    allow_additional_typologies: bool = Field(False, description="Allow identifying additional typologies beyond expected")
    min_key_facts_coverage: float = Field(0.8, description="Minimum % of key facts that must be covered")
    min_passing_score: float = Field(70.0, description="Minimum overall score (0-100) required to pass")


class TestMetadata(BaseModel):
    """Metadata for test cases."""
    created_by: str = Field(..., description="Who created this test case")
    reviewed_by: Optional[str] = Field(None, description="Who reviewed/validated this test case")
    created_date: str = Field(..., description="Creation date (YYYY-MM-DD)")
    version: str = Field("1.0", description="Test case version")
    tags: List[str] = Field(default_factory=list, description="Additional tags for categorization")


# ============================================================================
# Base Test Case and Result Models
# ============================================================================

class BaseTestCase(BaseModel):
    """Base model for all test cases.

    Provides common structure that all test types inherit from.
    """
    test_id: str = Field(..., description="Unique test identifier")
    test_type: str = Field(..., description="Type of test (golden, conversation, system)")
    category: str = Field(..., description="Test category")
    priority: Literal["HIGH", "MEDIUM", "LOW"] = Field(..., description="Test priority")
    description: str = Field(..., description="Brief description of test scenario")

    input: TestInput
    expected_output: ExpectedOutput
    evaluation_criteria: EvaluationCriteria
    metadata: TestMetadata


class BaseTestResult(BaseModel):
    """Base model for all test results.

    Provides common structure that all result types inherit from.
    """
    test_id: str
    test_type: str = Field(..., description="Type of test (golden, conversation, system)")
    status: Literal["PASS", "FAIL", "ERROR"]
    execution_time_seconds: float
    timestamp: datetime = Field(default_factory=datetime.now)
    error_message: Optional[str] = None


# ============================================================================
# Golden Test Models
# ============================================================================

class GoldenTestCase(BaseTestCase):
    """Golden test case for AML domain knowledge tests.

    These are single-turn tests that evaluate the agent's ability to identify
    AML typologies, red flags, and provide compliant analysis.
    """
    test_type: Literal["golden"] = "golden"
    category: Literal["structuring", "layering", "trade_based_ml", "low_risk", "edge_case", "alert_review"]


class GoldenTestResult(BaseTestResult):
    """Result of running a golden test case.

    Includes detailed scoring across multiple dimensions (correctness,
    completeness, hallucination) from specialized evaluators.
    """
    test_type: Literal["golden"] = "golden"

    # Agent output
    agent_output: Dict[str, Any]
    tokens_used: Optional[int] = None

    # Evaluation scores
    correctness_score: float = Field(..., ge=0, le=1, description="0-1 score for correctness")
    completeness_score: float = Field(..., ge=0, le=1, description="0-1 score for completeness")
    hallucination_score: float = Field(..., ge=0, le=1, description="0-1 score (1=no hallucinations)")
    overall_score: float = Field(..., ge=0, le=100, description="Overall quality score 0-100")

    # Detailed results
    typology_matches: Dict[str, bool] = Field(default_factory=dict)
    red_flag_matches: Dict[str, bool] = Field(default_factory=dict)
    key_facts_covered: List[str] = Field(default_factory=list)
    key_facts_missing: List[str] = Field(default_factory=list)
    hallucinations_detected: List[str] = Field(default_factory=list)

    # Pass/fail reasons
    pass_reasons: List[str] = Field(default_factory=list)
    fail_reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ============================================================================
# Conversation Test Models
# ============================================================================

class ExpectedBehavior(BaseModel):
    """Expected behavior for a single conversation turn."""
    routes_to: Optional[str] = Field(None, description="Expected agent to route to")
    fetches_data: Optional[bool] = Field(None, description="Should fetch data")
    response_includes: List[str] = Field(default_factory=list, description="Terms that must appear in response")
    resolves_reference: Optional[Dict[str, str]] = Field(None, description="Reference resolution mapping")
    references_turn_1_data: Optional[bool] = Field(None, description="Should reference data from turn 1")
    cross_turn_synthesis: Optional[bool] = Field(None, description="Should synthesize across turns")


class ConversationTurn(BaseModel):
    """A single turn in a multi-turn conversation."""
    turn_number: int = Field(..., description="Turn number (1-indexed)")
    user_query: str = Field(..., description="User's query for this turn")
    expected_behavior: ExpectedBehavior = Field(
        default_factory=ExpectedBehavior,
        description="Expected behavior for this turn"
    )


class ConversationSuccessCriteria(BaseModel):
    """Success criteria for conversation tests."""
    all_turns_complete: bool = Field(True, description="All turns must complete successfully")
    no_reference_errors: bool = Field(True, description="No reference resolution errors")
    message_history_sufficient: bool = Field(True, description="Message history enables cross-turn synthesis")


class ConversationTestCase(BaseTestCase):
    """Test case for multi-turn conversation tests.

    Tests conversation handling, reference resolution, and cross-turn data synthesis.
    """
    test_type: Literal["conversation"] = "conversation"
    category: Literal["reference_resolution", "data_synthesis", "conversation_flow", "context_retention"]

    turns: List[ConversationTurn] = Field(..., description="Conversation turns")
    success_criteria: ConversationSuccessCriteria = Field(
        default_factory=ConversationSuccessCriteria,
        description="Overall success criteria"
    )


class TurnResult(BaseModel):
    """Result of a single conversation turn."""
    turn_number: int
    query: str
    status: Literal["PASS", "FAIL", "ERROR"]
    final_response: str = ""
    retrieved_data: Optional[Dict[str, Any]] = None
    compliance_analysis: Optional[Any] = None
    intent: Optional[Dict[str, Any]] = None
    messages_count: int = 0
    current_step: str = ""
    validation_details: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class ConversationTestResult(BaseTestResult):
    """Result of running a conversation test case.

    Tracks results across multiple turns and provides methods for
    determining overall success.
    """
    test_type: Literal["conversation"] = "conversation"

    turn_results: List[TurnResult] = Field(default_factory=list, description="Results for each turn")
    final_state: Dict[str, Any] = Field(default_factory=dict, description="Final conversation state (serialized)")

    def is_successful(self) -> bool:
        """Determine if conversation test was successful.

        Returns:
            True if test passed all criteria, False otherwise
        """
        # All turns must pass
        if not all(turn.status == "PASS" for turn in self.turn_results):
            return False

        # Overall status must be PASS
        return self.status == "PASS"

    def get_failure_summary(self) -> Optional[str]:
        """Get summary of why test failed.

        Returns:
            Human-readable failure summary, or None if test passed
        """
        if self.is_successful():
            return None

        failed_turns = [t for t in self.turn_results if t.status != "PASS"]
        if failed_turns:
            turn_numbers = [str(t.turn_number) for t in failed_turns]
            return f"Failed turns: {', '.join(turn_numbers)}"

        if self.error_message:
            return f"Error: {self.error_message}"

        return "Unknown failure reason"


# ============================================================================
# System Test Models
# ============================================================================

class ValidationRule(BaseModel):
    """A validation rule for system tests."""
    rule_name: str = Field(..., description="Name of validation rule")
    description: str = Field(..., description="What this rule checks")
    validation_type: Literal["contains", "not_contains", "regex_match", "custom"] = Field(
        ...,
        description="Type of validation"
    )
    expected_value: Any = Field(..., description="Expected value or pattern")


class SystemTestCase(BaseTestCase):
    """Test case for system behavior tests.

    Tests boundary handling, error handling, and system robustness.
    """
    test_type: Literal["system"] = "system"
    category: Literal["off_topic", "in_scope_general", "boundary", "error_handling"]

    validation_rules: List[ValidationRule] = Field(
        default_factory=list,
        description="Validation rules for this test"
    )


class SystemTestResult(BaseTestResult):
    """Result of running a system test case.

    Provides simple pass/fail validation based on rules.
    """
    test_type: Literal["system"] = "system"

    agent_output: Dict[str, Any] = Field(default_factory=dict)
    validation_results: Dict[str, bool] = Field(
        default_factory=dict,
        description="Results for each validation rule"
    )

    def is_successful(self) -> bool:
        """Determine if system test was successful.

        Returns:
            True if all validation rules passed, False otherwise
        """
        return self.status == "PASS" and all(self.validation_results.values())


# ============================================================================
# Unified Evaluation Report
# ============================================================================

class CategoryStats(BaseModel):
    """Statistics for a test category."""
    total: int
    passed: int
    failed: int
    errors: int
    pass_rate: float = Field(..., ge=0, le=1)


class UnifiedEvaluationReport(BaseModel):
    """Unified report aggregating results from all test types.

    This replaces the separate JSON files that scorecard previously read.
    """
    report_id: str
    run_date: datetime = Field(default_factory=datetime.now)
    test_type: Literal["golden", "conversation", "system", "mixed"] = Field(
        ...,
        description="Type of tests in this report"
    )

    # Summary statistics
    total_cases: int
    passed: int
    failed: int
    errors: int
    pass_rate: float = Field(..., ge=0, le=1)

    # Aggregate metrics (flexible for different test types)
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Test-type-specific metrics"
    )

    # Results by category
    results_by_category: Dict[str, CategoryStats] = Field(default_factory=dict)

    # Individual results (polymorphic)
    test_results: List[Union[GoldenTestResult, ConversationTestResult, SystemTestResult]] = Field(
        default_factory=list
    )

    # Recommendations
    action_items: List[str] = Field(default_factory=list)

    # Metadata
    dataset_path: Optional[str] = None
    execution_time_seconds: Optional[float] = None

    def to_scorecard_format(self) -> Dict[str, Any]:
        """Convert to format compatible with scorecard generator.

        Returns:
            Dictionary in scorecard-compatible format
        """
        return {
            "timestamp": self.run_date.isoformat(),
            "total": self.total_cases,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "pass_rate": self.pass_rate,
            "category_stats": {
                cat: {
                    "total": stats.total,
                    "passed": stats.passed,
                    "failed": stats.failed,
                    "errors": stats.errors,
                    "pass_rate": stats.pass_rate
                }
                for cat, stats in self.results_by_category.items()
            },
            "metrics": self.metrics
        }

    def get_recommendations(self) -> List[str]:
        """Get actionable recommendations based on results.

        Returns:
            List of recommendation strings
        """
        if self.action_items:
            return self.action_items

        # Generate default recommendations
        recommendations = []

        if self.pass_rate < 0.7:
            recommendations.append(
                f"Pass rate {self.pass_rate:.1%} is below 70%. "
                "Review failed test cases and improve agent prompts."
            )

        for category, stats in self.results_by_category.items():
            if stats.pass_rate < 0.7:
                recommendations.append(
                    f"Category '{category}': {stats.pass_rate:.1%} pass rate. "
                    f"{stats.failed} failed, {stats.errors} errors."
                )

        if not recommendations:
            recommendations.append("All tests passing! ✅")

        return recommendations
