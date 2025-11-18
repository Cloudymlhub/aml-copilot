"""Coordinator Agent - Routes queries to appropriate specialized agents."""

import json
import logging
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .state import AMLCopilotState
from .prompts import COORDINATOR_PROMPT
from config.agent_config import AgentConfig
from config.settings import settings


class CoordinatorAgent:
    """Coordinator agent that routes queries to specialized agents."""

    def __init__(self, config: AgentConfig):
        """Initialize coordinator agent.

        Args:
            config: Agent configuration with model settings
        """
        self.config = config
        self.llm = ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            max_retries=config.max_retries,
            timeout=config.timeout,
            api_key=settings.openai_api_key,
        )
        self.logger = logging.getLogger(__name__)

    def __call__(self, state: AMLCopilotState) -> Dict[str, Any]:
        """Route the query to appropriate agent.

        Args:
            state: Current state

        Returns:
            Updated state with routing decision
        """
        user_query = state["user_query"]
        self.logger.info("Coordinator: invoked for session=%s", state.get("session_id"))

        def _build_messages(invalid: bool = False):
            """Construct system/human messages with optional retry notice."""
            human_prefix = "Your last reply was invalid JSON. Respond with JSON only per schema. " if invalid else ""
            human_content = f"{human_prefix}User query: {user_query}"
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
                    "messages": state["messages"] + [
                        {
                            "role": "assistant",
                            "content": guidance_msg,
                            "timestamp": str(state.get("started_at", ""))
                        }
                    ]
                }

            # In-scope query: normal routing
            next_agent = result.get("next_agent", "intent_mapper")
            query_type = result.get("query_type", "data_query")
            reasoning = result.get("reasoning", "")

            # Update state
            return {
                "next_agent": next_agent,
                "current_step": "coordinator_complete",
                "messages": state["messages"] + [
                    {
                        "role": "assistant",
                        "content": f"[Coordinator] Query type: {query_type}. Routing to: {next_agent}. Reason: {reasoning}",
                        "timestamp": str(state.get("started_at", ""))
                    }
                ]
            }
        except json.JSONDecodeError:
            # Fallback routing
            return {
                "next_agent": "intent_mapper",
                "current_step": "coordinator_complete",
                "messages": state["messages"] + [
                    {
                        "role": "assistant",
                        "content": "[Coordinator] Using default routing to intent_mapper",
                        "timestamp": str(state.get("started_at", ""))
                    }
                ]
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
