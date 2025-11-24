"""Coordinator Agent - Routes queries to appropriate specialized agents."""

import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from agents.prompts.coordinator_prompt import COORDINATOR_PROMPT
from agents.state import AMLCopilotState, AgentResponse
from agents.base_agent import BaseAgent
from config.agent_config import AgentConfig
from config.settings import settings


class CoordinatorAgent(BaseAgent):
    """Coordinator agent that routes queries to specialized agents.
    
    Message History: Last 3 messages (limit=3)
    Rationale: Needs basic continuity detection for follow-up queries
               like "show me more" or "what about...", but doesn't need
               deep conversation context for routing decisions.
    """

    def __init__(self, config: AgentConfig):
        """Initialize coordinator agent.

        Args:
            config: Agent configuration with model settings and history limit
        """
        super().__init__(config)  # Initialize BaseAgent
        self.llm = ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            max_retries=config.max_retries,
            timeout=config.timeout,
            api_key=settings.openai_api_key,
        )

    def __call__(self, state: AMLCopilotState) -> AgentResponse:
        """Route the query to appropriate agent.

        Args:
            state: Current state

        Returns:
            AgentResponse with routing decision
        """
        self.log_agent_start(state)
        
        user_query = state["user_query"]
        history_context = self.get_conversation_history(state, formatted=True)  # Get formatted string

        def _build_messages(invalid: bool = False):
            """Construct system/human messages with optional retry notice and conversation context."""
            human_prefix = "Your last reply was invalid JSON. Respond with JSON only per schema. " if invalid else ""
            
            # Include conversation history if available (for continuity detection)
            context_section = f"\n\n{history_context}\n" if history_context else ""
            
            human_content = f"{human_prefix}{context_section}User query: {user_query}"
            return [
                SystemMessage(content=COORDINATOR_PROMPT),
                HumanMessage(content=human_content)
            ]

        def _parse_response(raw_response):
            try:
                return json.loads(raw_response.content)
            except json.JSONDecodeError:
                return None

        # Primary attempt
        response = self.llm.invoke(_build_messages())
        result = _parse_response(response)

        # One-time retry if JSON parsing failed
        if result is None:
            self.logger.warning("Coordinator: invalid JSON, retrying once")
            retry_response = self.llm.invoke(_build_messages(invalid=True))
            result = _parse_response(retry_response)

        try:
            if result is None:
                raise json.JSONDecodeError("Invalid JSON from coordinator", "", 0)

            in_scope = result.get("in_scope", True)
            
            # Handle out-of-scope or partially-related queries
            if in_scope == False or in_scope == "partial":
                guidance_msg = result.get("guidance_message", 
                    "I'm an AML compliance assistant. I can help with questions related to anti-money laundering, customer due diligence, transaction monitoring, and financial crimes compliance.")
                
                return {
                    "next_agent": "end",
                    "current_step": "out_of_scope" if in_scope == False else "needs_refinement",
                    "completed": True,
                    "final_response": guidance_msg,
                    "messages": self._append_message(state, guidance_msg)
                }

            # In-scope query: normal routing
            next_agent = result.get("next_agent", "intent_mapper")
            query_type = result.get("query_type", "data_query")
            reasoning = result.get("reasoning", "")

            # Update state
            return {
                "next_agent": next_agent,
                "current_step": "coordinator_complete",
                "messages": self._append_message(
                    state, 
                    f"[Coordinator] Query type: {query_type}. Routing to: {next_agent}. Reason: {reasoning}"
                )
            }
        except json.JSONDecodeError:
            # Fallback routing
            return {
                "next_agent": "intent_mapper",
                "current_step": "coordinator_complete",
                "messages": self._append_message(
                    state,
                    "[Coordinator] Using default routing to intent_mapper"
                )
            }


def create_coordinator_node(config: AgentConfig):
    """Create coordinator node for LangGraph.

    Args:
        config: Agent configuration
    
    Returns:
        Coordinator agent callable
    """
    agent = CoordinatorAgent(config)
    return agent
