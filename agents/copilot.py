from agents.graph import create_aml_copilot_graph
from agents.state import AMLCopilotState
from config.agent_config import AgentsConfig

from datetime import datetime
from typing import Any, Dict, List, Optional


class AMLCopilot:
    """AML Copilot multi-agent system.

    Uses dependency injection for the checkpointer to enable better testing
    and configuration management.
    """

    def __init__(
        self,
        agents_config: AgentsConfig,
        checkpointer: Optional[Any] = None
    ):
        """Initialize AML Copilot with agent configurations.

        Args:
            agents_config: Configuration for all agents
            checkpointer: Optional checkpointer instance (e.g., RedisSaver, PostgresSaver)
                         for state persistence. If None, conversations won't persist.
        """
        # Store config and checkpointer
        self.config = agents_config
        self.checkpointer = checkpointer

        # Create graph with config and optional checkpointer
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
        """Process a user query through the multi-agent system with session continuation.

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
            # A session for the chat is defined by the session_id (context in the UI)
            # and the user_id which is the cif_no they are looking into.
            # Change the signature to not pass context, just take the cif_no directly, it will always 
            # be required to continue a session.
            cif_no = context.get("cif_no")
            if cif_no is None:
                raise ValueError("cif_no must be provided in context for session continuation")

            thread_id = f"{session_id}_{cif_no}"
            config = {"configurable": {"thread_id": thread_id}}
        else:
            config = None

        # Load previous state from checkpoint if available
        previous_state = None
        if config:
            try:
                checkpoint = self.graph.get_state(config)
                if checkpoint and checkpoint.values:
                    previous_state = checkpoint.values
            except Exception as e:
                # If checkpoint doesn't exist yet, that's fine - new session
                pass

        # Build new user message
        new_message = {
            "role": "user",
            "content": user_query,
            "timestamp": datetime.now().isoformat()
        }

        # Initialize state
        if previous_state:
            # Continue existing conversation
            initial_state: AMLCopilotState = {
                "messages": previous_state.get("messages", []) + [new_message],
                "user_query": user_query,
                "context": context or previous_state.get("context", {}),  # Use provided context or preserve previous
                "next_agent": "coordinator",  # Always restart from coordinator
                "current_step": "initialized",
                "intent": None,  # Clear intent for new query
                "retrieved_data": None,  # Clear retrieved data for new query
                "compliance_analysis": None,  # Clear analysis for new query
                "final_response": None,
                "review_status": None,  # Clear review status
                "review_feedback": None,
                "additional_query": None,
                "review_agent_id": None,
                "review_attempts": 0,
                "session_id": session_id or previous_state.get("session_id", f"session_{datetime.now().timestamp()}"),
                "started_at": previous_state.get("started_at", datetime.now().isoformat()),  # Preserve original session start
                "completed": False
            }
        else:
            # New conversation
            initial_state: AMLCopilotState = {
                "messages": [new_message],
                "user_query": user_query,
                "context": context or {},
                "next_agent": "coordinator",
                "current_step": "initialized",
                "intent": None,
                "retrieved_data": None,
                "compliance_analysis": None,
                "final_response": None,
                "review_status": None,
                "review_feedback": None,
                "additional_query": None,
                "review_agent_id": None,
                "review_attempts": 0,
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

    def get_conversation_history(
        self,
        user_id: str,
        session_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get conversation history for a session.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            List of messages in the conversation, or None if session doesn't exist
        """
        if not self.checkpointer:
            return None

        thread_id = f"{user_id}_{session_id}"
        config = {"configurable": {"thread_id": thread_id}}

        try:
            checkpoint = self.graph.get_state(config)
            if checkpoint and checkpoint.values:
                return checkpoint.values.get("messages", [])
        except Exception:
            pass

        return None

    def clear_session(
        self,
        user_id: str,
        session_id: str
    ) -> bool:
        """Clear/delete a session from checkpoint storage.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            True if session was cleared, False otherwise
        """
        if not self.checkpointer:
            return False

        thread_id = f"{user_id}_{session_id}"

        try:
            # Delete from Redis using the checkpointer's connection
            # RedisSaver stores checkpoints with a specific key pattern
            import redis
            from config.settings import settings

            r = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db_checkpoints
            )

            # Delete all keys for this thread
            pattern = f"*{thread_id}*"
            keys = r.keys(pattern)
            if keys:
                r.delete(*keys)
                return True
        except Exception as e:
            print(f"Error clearing session: {e}")

        return False

    def get_session_info(
        self,
        user_id: str,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get metadata about a session.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Dictionary with session metadata (started_at, message_count, context)
        """
        if not self.checkpointer:
            return None

        thread_id = f"{user_id}_{session_id}"
        config = {"configurable": {"thread_id": thread_id}}

        try:
            checkpoint = self.graph.get_state(config)
            if checkpoint and checkpoint.values:
                state = checkpoint.values
                return {
                    "session_id": session_id,
                    "user_id": user_id,
                    "started_at": state.get("started_at"),
                    "message_count": len(state.get("messages", [])),
                    "context": state.get("context", {}),
                    "last_updated": checkpoint.metadata.get("ts") if checkpoint.metadata else None,
                }
        except Exception:
            pass

        return None