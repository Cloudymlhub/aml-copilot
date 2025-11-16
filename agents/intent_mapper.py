"""Intent Mapping Agent - Maps natural language to data queries."""

import json
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .state import AMLCopilotState, IntentMapping
from .prompts import INTENT_MAPPER_PROMPT
from config.agent_config import AgentConfig


class IntentMappingAgent:
    """Intent mapping agent that converts natural language to structured queries."""

    def __init__(self, config: AgentConfig):
        """Initialize intent mapping agent.

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
        """Map user query to structured intent.

        Args:
            state: Current state

        Returns:
            Updated state with intent mapping
        """
        user_query = state["user_query"]
        
        # Get CIF from context (no longer extracted from query!)
        context = state.get("context", {})
        cif_no = context.get("cif_no")
        
        if not cif_no:
            return {
                "intent": None,
                "next_agent": "end",
                "error": "Missing cif_no in context",
                "messages": state["messages"] + [
                    {
                        "role": "assistant",
                        "content": "[Intent Mapper] Error: No customer ID provided in context",
                        "timestamp": str(state.get("started_at", ""))
                    }
                ]
            }

        # Create prompt
        prompt = INTENT_MAPPER_PROMPT.format(user_query=user_query)

        # Get intent mapping from LLM
        messages = [
            SystemMessage(content="You are an intent mapping agent. Respond ONLY with valid JSON."),
            HumanMessage(content=prompt)
        ]

        response = self.llm.invoke(messages)

        try:
            # Parse JSON response
            result = json.loads(response.content)

            # Add CIF from context to entities
            if "entities" not in result:
                result["entities"] = {}
            result["entities"]["cif_no"] = cif_no

            # Create intent mapping
            intent: IntentMapping = {
                "intent_type": result.get("intent_type", "data_query"),
                "entities": result.get("entities", {}),
                "feature_groups": result.get("feature_groups", []),
                "tools_to_use": result.get("tools_to_use", []),
                "confidence": result.get("confidence", 0.8)
            }

            # Update state
            return {
                "intent": intent,
                "next_agent": "data_retrieval",
                "current_step": "intent_mapped",
                "messages": state["messages"] + [
                    {
                        "role": "assistant",
                        "content": f"[Intent Mapper] Identified: {intent['intent_type']}. Tools: {[t.get('tool', t) if isinstance(t, dict) else t for t in intent['tools_to_use']]}",
                        "timestamp": str(state.get("started_at", ""))
                    }
                ]
            }
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback intent
            intent: IntentMapping = {
                "intent_type": "data_query",
                "entities": {"cif_no": cif_no} if cif_no else {},
                "feature_groups": ["basic"],
                "tools_to_use": [{"tool": "get_customer_basic_info", "args": {"cif_no": cif_no}}] if cif_no else [],
                "confidence": 0.5
            }

            return {
                "intent": intent,
                "next_agent": "data_retrieval",
                "current_step": "intent_mapped",
                "messages": state["messages"] + [
                    {
                        "role": "assistant",
                        "content": f"[Intent Mapper] Using fallback intent. Error: {str(e)}",
                        "timestamp": str(state.get("started_at", ""))
                    }
                ]
            }


def create_intent_mapper_node(config: AgentConfig):
    """Create intent mapper node for LangGraph.

    Args:
        config: Agent configuration
    
    Returns:
        Intent mapper agent callable
    """
    agent = IntentMappingAgent(config)
    return agent
