"""LangGraph workflow for AML Copilot multi-agent system."""

from typing import Optional
from langgraph.graph import StateGraph, END

from .state import AMLCopilotState
from .subagents import (
    create_coordinator_node,
    create_intent_mapper_node,
    create_data_retrieval_node,
    create_compliance_expert_node,
    create_review_agent_node,
    create_aml_alert_reviewer_node,
)
from config.agent_config import AgentsConfig
from config.settings import settings


def route_after_coordinator(state: AMLCopilotState) -> str:
    """Route after coordinator decision.

    Args:
        state: Current state

    Returns:
        Next node name
    """
    next_agent = state.get("next_agent", "intent_mapper")

    if next_agent == "end":
        return END
    elif next_agent == "aml_alert_reviewer":
        return "aml_alert_reviewer"
    elif next_agent == "compliance_expert":
        return "compliance_expert"
    else:
        return "intent_mapper"


def route_after_data_retrieval(state: AMLCopilotState) -> str:
    """Route after data retrieval.

    Routes to the appropriate analyzer based on workflow:
    - Copilot mode → compliance_expert
    - Autonomous mode (alert reviewer requested data) → aml_alert_reviewer

    Args:
        state: Current state

    Returns:
        Next node name: "compliance_expert" | "aml_alert_reviewer" | END
    """
    next_agent = state.get("next_agent", "compliance_expert")

    if next_agent == "end":
        return END
    elif next_agent == "aml_alert_reviewer":
        # Data was requested by alert reviewer - route back to it
        return "aml_alert_reviewer"
    else:
        # Default: copilot mode - route to compliance expert
        return "compliance_expert"


def route_after_compliance_expert(state: AMLCopilotState) -> str:
    """Route after compliance expert to review agent.

    Args:
        state: Current state

    Returns:
        Next node name: always "review_agent"
    """
    # Compliance expert always routes to review agent
    return "review_agent"


def route_after_alert_reviewer(state: AMLCopilotState) -> str:
    """Route after AML alert reviewer based on data needs.

    The alert reviewer can autonomously request data by routing to intent_mapper.
    This enables progressive investigation without user interaction.

    Args:
        state: Current state

    Returns:
        Next node name: "intent_mapper" | "aml_alert_reviewer" | END
    """
    next_agent = state.get("next_agent", "end")

    if next_agent == "intent_mapper":
        # Alert reviewer needs data - route to intent mapper
        return "intent_mapper"
    elif next_agent == "aml_alert_reviewer":
        # After data retrieval, route back to alert reviewer for analysis
        return "aml_alert_reviewer"
    else:
        # Analysis complete or error - end
        return END


def create_aml_copilot_graph(agents_config: AgentsConfig, checkpointer=None):
    """Create the AML Copilot multi-agent graph.

    Args:
        agents_config: Configuration for all agents
        checkpointer: Optional checkpointer for state persistence

    Graph flow:
        START
          ↓
        coordinator (decides routing)
          ↓
        ├─→ intent_mapper → data_retrieval → compliance_expert → review_agent → END
        ├─→ compliance_expert → review_agent → END
        └─→ aml_alert_reviewer ←──────────────┐
                  ↓                             │
            (needs data?)                       │
                  ↓                             │
            intent_mapper → data_retrieval ────┘
                  ↓
                END

    Returns:
        Compiled LangGraph CompiledStateGraph
    """
    # Create state graph
    workflow = StateGraph(AMLCopilotState)

    # Add nodes with configs
    workflow.add_node("coordinator", create_coordinator_node(agents_config.coordinator))
    workflow.add_node("intent_mapper", create_intent_mapper_node(agents_config.intent_mapper))
    workflow.add_node("data_retrieval", create_data_retrieval_node(agents_config.data_retrieval))
    workflow.add_node("compliance_expert", create_compliance_expert_node(agents_config.compliance_expert))
    workflow.add_node("review_agent", create_review_agent_node(agents_config.review_expert))
    workflow.add_node("aml_alert_reviewer", create_aml_alert_reviewer_node(agents_config.aml_alert_reviewer))

    # Set entry point
    workflow.set_entry_point("coordinator")

    # Define routing function that has access to agents_config
    def route_after_review(state: AMLCopilotState) -> str:
        """Route after review agent based on review outcome.

        Args:
            state: Current state

        Returns:
            Next node name: "intent_mapper" | "compliance_expert" | "coordinator" | END
        """
        review_status = state.get("review_status", "passed")
        review_attempts = state.get("review_attempts", 0) or 0

        # Max attempts exceeded - return to user
        if review_attempts >= agents_config.review_expert.max_review_attempts:
            return END

        # Review passed - complete
        if review_status == "passed":
            return END

        # Needs additional data - route to intent mapper with additional_query
        if review_status == "needs_data":
            return "intent_mapper"

        # Needs refinement - route back to compliance expert
        if review_status == "needs_refinement":
            return "compliance_expert"

        # Needs clarification - route to coordinator (which will end and ask user)
        if review_status == "needs_clarification":
            return END  # Return clarification message to user

        # Human review required - end for human intervention
        if review_status == "human_review":
            return END

        # Default: end
        return END

    # Add conditional edges
    workflow.add_conditional_edges(
        "coordinator",
        route_after_coordinator,
        {
            "intent_mapper": "intent_mapper",
            "compliance_expert": "compliance_expert",
            "aml_alert_reviewer": "aml_alert_reviewer",
            END: END
        }
    )

    # AML alert reviewer routes based on data needs
    # AUTONOMOUS DATA REQUEST LOOP: Alert reviewer can request data autonomously
    # - Needs data → intent_mapper → data_retrieval → aml_alert_reviewer (loop)
    # - Analysis complete → END
    # Loop prevention: max_attempts check in alert reviewer prevents infinite loops
    workflow.add_conditional_edges(
        "aml_alert_reviewer",
        route_after_alert_reviewer,
        {
            "intent_mapper": "intent_mapper",  # Needs data
            "aml_alert_reviewer": "aml_alert_reviewer",  # After data retrieval
            END: END  # Analysis complete
        }
    )

    # Intent mapper routes to data retrieval or can end early
    workflow.add_conditional_edges(
        "intent_mapper",
        lambda state: END if state.get("next_agent") == "end" else "data_retrieval",
        {
            "data_retrieval": "data_retrieval",
            END: END
        }
    )

    # Data retrieval routes based on who requested the data
    # - Copilot mode → compliance_expert
    # - Autonomous mode (alert reviewer) → aml_alert_reviewer
    workflow.add_conditional_edges(
        "data_retrieval",
        route_after_data_retrieval,
        {
            "compliance_expert": "compliance_expert",  # Copilot mode
            "aml_alert_reviewer": "aml_alert_reviewer",  # Autonomous mode
            END: END
        }
    )

    # Compliance expert always routes to review agent
    workflow.add_conditional_edges(
        "compliance_expert",
        route_after_compliance_expert,
        {
            "review_agent": "review_agent"
        }
    )

    # Review agent routes based on review outcome
    # REVIEW LOOP MECHANISM: The review agent can route back to earlier agents for refinement
    # - "needs_data" → intent_mapper → data_retrieval → compliance_expert → review_agent (loop)
    # - "needs_refinement" → compliance_expert → review_agent (loop)
    # Loop prevention: max_review_attempts check in route_after_review() forces END after N attempts
    # This ensures quality while preventing infinite loops
    workflow.add_conditional_edges(
        "review_agent",
        route_after_review,
        {
            "intent_mapper": "intent_mapper",  # Needs more data
            "compliance_expert": "compliance_expert",  # Needs refinement
            END: END  # Passed, needs clarification, or human review
        }
    )

    # Compile graph with optional checkpointer
    return workflow.compile(checkpointer=checkpointer)


