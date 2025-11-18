"""LangGraph state schema for AML Copilot multi-agent system."""

from typing import TypedDict, List, Dict, Any, Optional, Literal
from datetime import datetime


class Message(TypedDict):
    """Message in the conversation."""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str


class IntentMapping(TypedDict):
    """Intent mapping result from Intent Mapping Agent."""
    intent_type: str  # "data_query", "compliance_question", "procedural_guidance", "report_generation"
    entities: Dict[str, Any]  # Extracted entities (cif_no, date_range, alert_id, etc.)
    feature_groups: List[str]  # Which feature groups to query (basic, transaction_features, etc.)
    tools_to_use: List[str]  # Specific tools to invoke
    confidence: float  # Confidence score


class DataRetrievalResult(TypedDict):
    """Data retrieval result from Data Retrieval Agent."""
    success: bool
    data: Dict[str, Any]  # Retrieved data
    tools_used: List[str]  # Tools that were invoked
    error: Optional[str]  # Error message if any
    errors: Optional[List[Dict[str, Any]]]  # Per-tool error details


class ComplianceAnalysis(TypedDict):
    """Compliance analysis from Compliance Expert Agent."""
    analysis: str  # Main analysis text
    risk_assessment: Optional[str]  # Risk assessment if applicable
    typologies: List[str]  # Matched AML typologies
    recommendations: List[str]  # Recommended actions
    regulatory_references: List[str]  # Relevant regulations/guidelines


class AMLCopilotState(TypedDict):
    """State for AML Copilot multi-agent system.

    This state is shared across all agents in the LangGraph workflow.
    """
    # Conversation
    messages: List[Message]
    user_query: str
    
    # Context (NEW in Phase 2)
    context: Dict[str, Any]  # Contains cif_no, alert_id, investigation_id

    # Routing
    next_agent: str  # Which agent to route to next
    current_step: str  # Current step in workflow

    # Intent Mapping
    intent: Optional[IntentMapping]

    # Data Retrieval
    retrieved_data: Optional[DataRetrievalResult]

    # Compliance Analysis
    compliance_analysis: Optional[ComplianceAnalysis]

    # Final Response
    final_response: Optional[str]
    
    # Review System (NEW in Phase 4)
    review_status: Optional[Literal["passed", "needs_data", "needs_refinement", "needs_clarification", "human_review"]]
    review_feedback: Optional[str]  # Detailed review comments
    additional_query: Optional[str]  # Natural language request for missing data or clarification
    review_agent_id: Optional[str]  # Which model/agent performed review
    review_attempts: Optional[int]  # Number of review iterations

    # Metadata
    session_id: str
    started_at: str
    completed: bool
