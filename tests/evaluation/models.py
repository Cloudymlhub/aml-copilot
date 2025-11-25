"""Data models for agent evaluation and golden test cases."""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


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


class GoldenTestCase(BaseModel):
    """Complete golden test case with input, expected output, and evaluation criteria."""
    test_id: str = Field(..., description="Unique test identifier (e.g., STRUCT_001)")
    category: Literal["structuring", "layering", "trade_based_ml", "low_risk", "edge_case", "alert_review"] = Field(
        ...,
        description="Test case category"
    )
    priority: Literal["HIGH", "MEDIUM", "LOW"] = Field(..., description="Test priority")
    description: str = Field(..., description="Brief description of test scenario")

    input: TestInput
    expected_output: ExpectedOutput
    evaluation_criteria: EvaluationCriteria

    # Metadata
    created_by: str = Field(..., description="Who created this test case")
    reviewed_by: Optional[str] = Field(None, description="Who reviewed/validated this test case")
    created_date: str = Field(..., description="Creation date (YYYY-MM-DD)")
    version: str = Field("1.0", description="Test case version")
    tags: List[str] = Field(default_factory=list, description="Additional tags for categorization")


class TestResult(BaseModel):
    """Result of running a single test case."""
    test_id: str
    status: Literal["PASS", "FAIL", "ERROR"]

    # Agent output
    agent_output: Dict[str, Any]
    execution_time_seconds: float
    tokens_used: Optional[int] = None

    # Evaluation results
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

    timestamp: datetime = Field(default_factory=datetime.now)


class EvaluationReport(BaseModel):
    """Comprehensive report of evaluation run."""
    report_id: str
    run_date: datetime = Field(default_factory=datetime.now)
    version: str = Field(..., description="System version being tested")
    baseline_version: Optional[str] = Field(None, description="Baseline version for comparison")

    # Summary statistics
    total_cases: int
    passed: int
    failed: int
    errors: int
    pass_rate: float = Field(..., ge=0, le=1)

    # Aggregate metrics
    avg_correctness_score: float
    avg_completeness_score: float
    avg_hallucination_score: float
    avg_overall_score: float

    # By category
    results_by_category: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Individual results
    test_results: List[TestResult]

    # Regressions (if baseline provided)
    regressions_detected: List[str] = Field(default_factory=list)
    improvements_detected: List[str] = Field(default_factory=list)

    # Recommendations
    action_items: List[str] = Field(default_factory=list)


class BaselineSnapshot(BaseModel):
    """Snapshot of test results for baseline comparison."""
    version: str
    snapshot_date: datetime
    total_cases: int

    # Store results by test_id for easy comparison
    results: Dict[str, TestResult] = Field(
        default_factory=dict,
        description="test_id -> TestResult mapping"
    )

    # Aggregate metrics
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Overall metrics (pass_rate, avg_scores, etc.)"
    )
