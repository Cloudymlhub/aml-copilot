"""LangGraph workflow for AML Copilot multi-agent system."""

from datetime import datetime
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

from .state import AMLCopilotState
from .coordinator import create_coordinator_node
from .intent_mapper import create_intent_mapper_node
from .data_retrieval import create_data_retrieval_node
from .compliance_expert import create_compliance_expert_node
from .review_agent import create_review_agent_node
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
    """Route after compliance expert to review agent.

    Args:
        state: Current state

    Returns:
        Next node name: always "review_agent"
    """
    # Compliance expert always routes to review agent
    return "review_agent"


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
    if review_attempts >= settings.max_review_attempts:
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
        ├─→ intent_mapper → data_retrieval → compliance_expert → END
        └─→ compliance_expert → END

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
    workflow.add_node("review_agent", create_review_agent_node(agents_config.compliance_expert))  # Use same config as compliance expert

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

    # Compliance expert always routes to review agent
    workflow.add_conditional_edges(
        "compliance_expert",
        route_after_compliance_expert,
        {
            "review_agent": "review_agent"
        }
    )

    # Review agent routes based on review outcome
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


class AMLCopilot:
    """AML Copilot multi-agent system."""

    def __init__(self, agents_config: AgentsConfig):
        """Initialize AML Copilot with agent configurations.
        
        Args:
            agents_config: Configuration for all agents
        """
        from config.settings import settings
        
        # Store config
        self.config = agents_config
        
        # Create RedisSaver checkpointer for chat continuity
        from langgraph.checkpoint.redis import RedisSaver
        
        self.checkpointer = RedisSaver.from_conn_info(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db_checkpoints,
        )
        
        # Create graph with config and checkpointer
        self.graph = create_aml_copilot_graph(
            agents_config=agents_config,
            checkpointer=self.checkpointer
        )

    def query(
        self, 
        user_query: str, 
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a user query through the multi-agent system.

        Args:
            user_query: User's natural language query
            context: Optional context (cif_no, alert_id, etc.) - will be required in Phase 2
            session_id: Session ID for conversation tracking
            user_id: User ID for conversation tracking

        Returns:
            Final response with analysis
        """
        # Create thread_id for Redis checkpointer
        if self.checkpointer and user_id and session_id:
            thread_id = f"{user_id}_{session_id}"
            config = {"configurable": {"thread_id": thread_id}}
        else:
            config = None
        
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
            "context": context or {},  # NEW: Include context in state
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

        # Run the graph with checkpointing (if available)
        if config:
            final_state = self.graph.invoke(initial_state, config=config)
        else:
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
