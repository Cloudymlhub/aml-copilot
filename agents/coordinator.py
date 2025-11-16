"""Coordinator Agent - Routes queries to appropriate specialized agents."""

import json
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .state import AMLCopilotState
from .prompts import COORDINATOR_PROMPT
from config.agent_config import AgentConfig


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
        )

    def __call__(self, state: AMLCopilotState) -> Dict[str, Any]:
        """Route the query to appropriate agent.

        Args:
            state: Current state

        Returns:
            Updated state with routing decision
        """
        user_query = state["user_query"]

        # Create prompt
        prompt = COORDINATOR_PROMPT.format(user_query=user_query)

        # Get routing decision from LLM
        messages = [
            SystemMessage(content="You are a coordinator agent. Respond ONLY with valid JSON."),
            HumanMessage(content=prompt)
        ]

        response = self.llm.invoke(messages)

        try:
            # Parse JSON response
            result = json.loads(response.content)

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
