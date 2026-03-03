"""LangGraph state schema for AML Copilot multi-agent system.

DESIGN DECISION: TypedDict vs Pydantic BaseModel
=================================================

This module uses TypedDict instead of Pydantic BaseModel for state management.

Rationale:
----------
1. **LangGraph Compatibility**: LangGraph works natively with plain dictionaries.
   TypedDict provides type hints without runtime overhead or serialization complexity.

2. **Partial Updates**: Agents return partial state updates via AgentResponse (total=False).
   This pattern is natural with dictionaries but awkward with Pydantic models.

3. **Performance**: No serialization/deserialization overhead. State updates are
   simple dictionary merges.

4. **Flexibility**: LangGraph's state management expects mutable dictionaries.
   Pydantic models are designed for immutability and validation.

Contrast with Evaluation Framework:
------------------------------------
The evaluation framework (evaluation/core/models.py) DOES use Pydantic BaseModel
because:
- Test cases benefit from validation at load time
- Results benefit from methods (is_successful(), to_scorecard_format())
- No LangGraph integration required
- Evaluation data is serialized to JSON for reporting

Summary:
--------
TypedDict for agent state (runtime efficiency, LangGraph native)
Pydantic for test data (validation, methods, reporting)
"""

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


# ============================================================================
# ML Model Output Types (Phase 5 - Adaptive Review System)
# ============================================================================

class DailyRiskScore(TypedDict):
    """Daily risk score for trend analysis."""
    date: str  # ISO date string
    risk_score: float  # Risk score (0.0-1.0)


class FeatureContribution(TypedDict):
    """Individual feature contribution to a red flag."""
    feature: str  # Feature name (e.g., "txn_count_near_threshold")
    value: Any  # Feature value (can be int, float, str, etc.)
    importance: float  # Feature importance score (0.0-1.0)


class RedFlagDetail(TypedDict):
    """Detailed red flag with contributing features."""
    red_flag: str  # Red flag name (e.g., "transactions_below_threshold")
    score: float  # Confidence score (0.0-1.0)
    contributing_features: List[FeatureContribution]  # Features that triggered this red flag


class MLModelOutput(TypedDict):
    """ML model outputs for compliance analysis.

    This structure captures the complete attribution chain:
    Typology → Red Flags → Features

    The Compliance Expert Agent interprets these pre-computed outputs
    rather than computing features itself.
    """
    # Daily risk trend
    daily_risk_scores: Optional[List[DailyRiskScore]]  # Time series of risk scores

    # Pre-computed feature values
    feature_values: Dict[str, Any]  # Raw feature values (e.g., {"txn_count_last_30d": 47})

    # Red flag confidence scores
    red_flag_scores: Dict[str, float]  # Red flag name → confidence score

    # Typology assessments
    most_likely_typology: Optional[str]  # Top typology (e.g., "structuring")
    typology_likelihoods: Dict[str, float]  # Typology name → likelihood score

    # Attribution chain (explains WHY the model flagged this)
    typology_red_flags: Dict[str, List[RedFlagDetail]]  # Typology → Red flags → Features


class AMLCopilotState(TypedDict, total=False):
    """State for AML Copilot multi-agent system.

    This state is shared across all agents in the LangGraph workflow.

    ALL FIELDS ARE OPTIONAL (total=False) to support LangSmith invocation
    with minimal state. Agents must use .get() for safe state access.

    Note: user_query is DEPRECATED. Use get_user_query(state) to extract
    from messages instead.
    """
    # Conversation
    messages: List[Message]
    
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

    # ML Model Output (Phase 5)
    ml_model_output: Optional[MLModelOutput]  # Pre-computed ML features and scores

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


# ============================================================================
# Agent Response Types
# ============================================================================

class AgentResponse(TypedDict, total=False):
    """Standardized return type for agent __call__ methods.
    
    Agents return a dictionary that LangGraph merges into the global state.
    This TypedDict defines the allowed fields agents can update.
    
    Design rationale:
    - Type safety: Ensures agents only update valid state fields
    - Documentation: Clear contract for what agents can return
    - IDE support: Auto-completion for return values
    - Validation: Can catch errors at development time
    
    Usage:
        def __call__(self, state: AMLCopilotState) -> AgentResponse:
            return {
                "next_agent": "data_retrieval",
                "intent": intent_mapping,
                "messages": updated_messages
            }
    
    Note: total=False means all fields are optional - agents only
    return the fields they want to update.
    """
    # Routing
    next_agent: str
    current_step: str

    # Conversation
    messages: List[Message]

    # Context
    context: Dict[str, Any]
    
    # Intent Mapping
    intent: Optional[IntentMapping]
    
    # Data Retrieval
    retrieved_data: Optional[DataRetrievalResult]
    #TODO 
    # used_retrieved_data: Optional[DataRetrievalResult] = ["A", "B"]
    # # Keep top n of them in a queue limited to a config set N last used data
    # all_used_retrieved_data: Optional[DataRetrievalResult] = []
    # Compliance Analysis

    # Have a history compacter, an agent that summarizes after the chat reaches max length
    # of chat, and store the summary in the state for future reference.

    compliance_analysis: Optional[ComplianceAnalysis]

    # ML Model Output
    ml_model_output: Optional[MLModelOutput]

    # Final Response
    final_response: Optional[str]
    
    # Review System
    review_status: Optional[Literal["passed", "needs_data", "needs_refinement", "needs_clarification", "human_review"]]
    review_feedback: Optional[str]
    additional_query: Optional[str]
    review_agent_id: Optional[str]
    review_attempts: Optional[int]
    
    # Metadata
    completed: bool
    
    # Error handling
    error: Optional[str]


# ============================================================================
# Message Access Control
# ============================================================================

def get_conversation_context(
    state: AMLCopilotState, 
    message_history_limit: Optional[int]
) -> List[Message]:
    """Extract conversation messages based on history limit.
    
    Implements intuitive access control pattern:
    - None: ALL messages (no limit)
    - 0: NO messages (empty list)
    - N > 0: Last N messages
    
    This function centralizes message slicing logic to ensure consistency
    across agents. Each agent declares its needs via config, and this
    function enforces the limit.
    
    Args:
        state: Current AML Copilot state
        message_history_limit: How many messages to return
            - None: Return all messages (comprehensive analysis)
            - 0: Return empty list (pure executors)
            - N: Return last N messages (contextual awareness)
        
    Returns:
        Filtered list of messages according to limit
        
    Examples:
        >>> # Compliance Expert: needs ALL messages
        >>> messages = get_conversation_context(state, None)
        >>> 
        >>> # Data Retrieval: needs NO messages (pure executor)
        >>> messages = get_conversation_context(state, 0)
        >>> 
        >>> # Coordinator: needs last 3 messages (basic continuity)
        >>> messages = get_conversation_context(state, 3)
        >>> 
        >>> # Intent Mapper: needs last 10 messages (reference resolution)
        >>> messages = get_conversation_context(state, 10)
    """
    all_messages = state.get("messages", [])
    
    # None means ALL messages
    if message_history_limit is None:
        return all_messages
    
    # 0 means NO messages
    if message_history_limit == 0:
        return []
    
    # N means last N messages (or all if fewer than N)
    if message_history_limit > 0:
        return all_messages[-message_history_limit:] if len(all_messages) > message_history_limit else all_messages
    
    # Negative numbers: treat as 0 (defensive)
    return []


def get_user_query(state: AMLCopilotState) -> str:
    """Extract user query from messages.

    Modern LangGraph pattern: user query is always extracted from the
    messages list, not from a separate user_query field.

    Args:
        state: Current state

    Returns:
        User query string (may be empty if no user messages)

    Examples:
        >>> # Extract from messages (modern pattern)
        >>> state = {
        ...     "messages": [
        ...         {"role": "user", "content": "What are structuring red flags?", ...}
        ...     ]
        ... }
        >>> query = get_user_query(state)
        >>> # "What are structuring red flags?"

        >>> # No user messages
        >>> query = get_user_query({"messages": []})
        >>> # ""
    """
    # Extract from messages (last user message)
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")

    return ""

