"""LangGraph workflow for AML Copilot multi-agent system."""

from datetime import datetime
from typing import Dict, Any
from langgraph.graph import StateGraph, END

from .state import AMLCopilotState
from .coordinator import create_coordinator_node
from .intent_mapper import create_intent_mapper_node
from .data_retrieval import create_data_retrieval_node
from .compliance_expert import create_compliance_expert_node


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
    elif next_agent == "compliance_expert":
        return "compliance_expert"
    else:
        return "intent_mapper"


def route_after_data_retrieval(state: AMLCopilotState) -> str:
    """Route after data retrieval.

    Args:
        state: Current state

    Returns:
        Next node name
    """
    next_agent = state.get("next_agent", "compliance_expert")

    if next_agent == "end":
        return END
    else:
        return "compliance_expert"


def route_after_compliance_expert(state: AMLCopilotState) -> str:
    """Route after compliance expert.

    Args:
        state: Current state

    Returns:
        Next node name (usually END)
    """
    return END


def create_aml_copilot_graph() -> StateGraph:
    """Create the AML Copilot multi-agent graph.

    Graph flow:
        START
          ↓
        coordinator (decides routing)
          ↓
        ├─→ intent_mapper → data_retrieval → compliance_expert → END
        └─→ compliance_expert → END

    Returns:
        Compiled LangGraph StateGraph
    """
    # Create state graph
    workflow = StateGraph(AMLCopilotState)

    # Add nodes
    workflow.add_node("coordinator", create_coordinator_node())
    workflow.add_node("intent_mapper", create_intent_mapper_node())
    workflow.add_node("data_retrieval", create_data_retrieval_node())
    workflow.add_node("compliance_expert", create_compliance_expert_node())

    # Set entry point
    workflow.set_entry_point("coordinator")

    # Add conditional edges
    workflow.add_conditional_edges(
        "coordinator",
        route_after_coordinator,
        {
            "intent_mapper": "intent_mapper",
            "compliance_expert": "compliance_expert",
            END: END
        }
    )

    # Intent mapper always goes to data retrieval
    workflow.add_edge("intent_mapper", "data_retrieval")

    # Data retrieval routes to compliance expert or END
    workflow.add_conditional_edges(
        "data_retrieval",
        route_after_data_retrieval,
        {
            "compliance_expert": "compliance_expert",
            END: END
        }
    )

    # Compliance expert always ends
    workflow.add_conditional_edges(
        "compliance_expert",
        route_after_compliance_expert,
        {
            END: END
        }
    )

    # Compile graph
    return workflow.compile()


class AMLCopilot:
    """AML Copilot multi-agent system."""

    def __init__(self):
        """Initialize AML Copilot."""
        self.graph = create_aml_copilot_graph()

    def query(self, user_query: str, session_id: str = None) -> Dict[str, Any]:
        """Process a user query through the multi-agent system.

        Args:
            user_query: User's natural language query
            session_id: Optional session ID for tracking

        Returns:
            Final response with analysis
        """
        # Initialize state
        initial_state: AMLCopilotState = {
            "messages": [
                {
                    "role": "user",
                    "content": user_query,
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "user_query": user_query,
            "next_agent": "coordinator",
            "current_step": "initialized",
            "intent": None,
            "retrieved_data": None,
            "compliance_analysis": None,
            "final_response": None,
            "session_id": session_id or f"session_{datetime.now().timestamp()}",
            "started_at": datetime.now().isoformat(),
            "completed": False
        }

        # Run the graph
        final_state = self.graph.invoke(initial_state)

        return {
            "response": final_state.get("final_response", "Unable to process query"),
            "compliance_analysis": final_state.get("compliance_analysis"),
            "retrieved_data": final_state.get("retrieved_data"),
            "messages": final_state.get("messages", []),
            "session_id": final_state.get("session_id"),
        }

    async def aquery(self, user_query: str, session_id: str = None) -> Dict[str, Any]:
        """Async version of query method.

        Args:
            user_query: User's natural language query
            session_id: Optional session ID for tracking

        Returns:
            Final response with analysis
        """
        # Initialize state
        initial_state: AMLCopilotState = {
            "messages": [
                {
                    "role": "user",
                    "content": user_query,
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "user_query": user_query,
            "next_agent": "coordinator",
            "current_step": "initialized",
            "intent": None,
            "retrieved_data": None,
            "compliance_analysis": None,
            "final_response": None,
            "session_id": session_id or f"session_{datetime.now().timestamp()}",
            "started_at": datetime.now().isoformat(),
            "completed": False
        }

        # Run the graph asynchronously
        final_state = await self.graph.ainvoke(initial_state)

        return {
            "response": final_state.get("final_response", "Unable to process query"),
            "compliance_analysis": final_state.get("compliance_analysis"),
            "retrieved_data": final_state.get("retrieved_data"),
            "messages": final_state.get("messages", []),
            "session_id": final_state.get("session_id"),
        }
