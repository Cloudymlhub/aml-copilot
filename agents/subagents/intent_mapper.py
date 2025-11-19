"""Intent Mapping Agent - Maps natural language to data queries."""

import json
import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from agents.prompts.intent_mapper_prompt import INTENT_MAPPER_PROMPT
from agents.state import AMLCopilotState
from tools import get_all_tools
from config.agent_config import AgentConfig
from config.settings import settings


class IntentMappingAgent:
    """Intent mapping agent that converts natural language to structured queries.

    Uses OpenAI function calling (bind_tools) to ensure schema-aware tool selection.
    The agent sees actual tool schemas, preventing hallucination of tool names/args.

    Architecture:
    - Planner: This agent (Intent Mapper) - selects tools via function calling
    - Executor: Data Retrieval Agent - executes the selected tools

    This maintains clean separation between planning and execution.
    """

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
            api_key=settings.openai_api_key,
        )
        self.logger = logging.getLogger(__name__)

        # Load all available tools from registry
        self.available_tools = get_all_tools()
        self.valid_tool_names = {tool.name for tool in self.available_tools}

        # Bind tools to LLM for function calling (schema-aware planning)
        # Note: This does NOT execute tools, only enables the LLM to see their schemas
        self.llm_with_tools = self.llm.bind_tools(self.available_tools)

    def __call__(self, state: AMLCopilotState) -> Dict[str, Any]:
        """Map user query to structured intent using function calling.

        Uses OpenAI function calling to select tools with schema validation.
        The LLM can only propose tools that exist and with correct argument types.

        Args:
            state: Current state

        Returns:
            Updated state with intent mapping
        """
        self.logger.info("IntentMapper: invoked for session=%s", state.get("session_id"))
        # Check if this is a replanning request from Review Agent
        additional_query = state.get("additional_query")
        if additional_query:
            # Use additional_query for replanning
            user_query = additional_query
        else:
            user_query = state["user_query"]

        # Get CIF from context (required for all queries)
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

        # Create messages for function calling
        # Tools are automatically described via bind_tools()
        messages = [
            SystemMessage(content=INTENT_MAPPER_PROMPT.format(cif_no=cif_no)),
            HumanMessage(content=f"User query: {user_query}")
        ]

        try:
            # Invoke LLM with bound tools (function calling)
            response = self.llm_with_tools.invoke(messages)

            # Check if LLM provided tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Extract tool calls (validated by OpenAI against tool schemas)
                tools_to_use = [
                    {
                        "tool": tool_call["name"],
                        "args": tool_call["args"]
                    }
                    for tool_call in response.tool_calls
                ]

                # Validate tool names (should always pass with bind_tools, but safety check)
                for tool_spec in tools_to_use:
                    if tool_spec["tool"] not in self.valid_tool_names:
                        raise ValueError(
                            f"Invalid tool '{tool_spec['tool']}'. "
                            f"Available tools: {self.valid_tool_names}"
                        )

                # Infer feature groups from tools selected
                feature_groups = self._infer_feature_groups(tools_to_use)

                # Create intent mapping
                intent: IntentMapping = {
                    "intent_type": "data_query",
                    "entities": {"cif_no": cif_no},
                    "feature_groups": feature_groups,
                    "tools_to_use": tools_to_use,
                    "confidence": 0.95  # Higher confidence with schema validation
                }

                # Update state
                return {
                    "intent": intent,
                    "next_agent": "data_retrieval",
                    "current_step": "intent_mapped",
                    "additional_query": None,  # Clear additional_query after processing
                    "messages": state["messages"] + [
                        {
                            "role": "assistant",
                            "content": f"[Intent Mapper] Selected {len(tools_to_use)} tool(s): {[t['tool'] for t in tools_to_use]}",
                            "timestamp": str(state.get("started_at", ""))
                        }
                    ]
                }

            else:
                # No tool calls - LLM responded with text (likely asking for clarification)
                clarification_message = response.content or "Could you please provide more specific details about your request?"

                return {
                    "review_status": "needs_clarification",
                    "additional_query": clarification_message,
                    "next_agent": "end",  # Return to user for clarification/guidance
                    "current_step": "intent_needs_clarification",
                    "final_response": clarification_message,
                    "completed": False,
                    "messages": state["messages"] + [
                        {
                            "role": "assistant",
                            "content": clarification_message,
                            "timestamp": str(state.get("started_at", ""))
                        }
                    ]
                }

        except Exception as e:
            # Fallback intent on any error
            intent: IntentMapping = {
                "intent_type": "data_query",
                "entities": {"cif_no": cif_no},
                "feature_groups": ["basic"],
                "tools_to_use": [{"tool": "get_customer_basic_info", "args": {"cif_no": cif_no}}],
                "confidence": 0.5
            }

            return {
                "intent": intent,
                "next_agent": "data_retrieval",
                "current_step": "intent_mapped",
                "additional_query": None,  # Clear additional_query after processing
                "messages": state["messages"] + [
                    {
                        "role": "assistant",
                        "content": f"[Intent Mapper] Using fallback intent due to error: {str(e)}",
                        "timestamp": str(state.get("started_at", ""))
                    }
                ]
            }

    def _infer_feature_groups(self, tools_to_use: list) -> list:
        """Infer feature groups from selected tools.

        Args:
            tools_to_use: List of tool specifications

        Returns:
            List of feature group names
        """
        feature_groups = set()

        for tool_spec in tools_to_use:
            tool_name = tool_spec["tool"]

            # Map tools to feature groups
            if "basic" in tool_name or tool_name == "search_customers_by_name":
                feature_groups.add("basic")
            if "transaction" in tool_name:
                feature_groups.add("transaction_features")
            if "risk" in tool_name or "high_risk" in tool_name:
                feature_groups.add("risk_features")
            if "behavioral" in tool_name:
                feature_groups.add("behavioral_features")
            if "network" in tool_name:
                feature_groups.add("network_features")
            if "knowledge_graph" in tool_name:
                feature_groups.add("knowledge_graph")
            if "alert" in tool_name:
                feature_groups.add("alerts")
            if "full_profile" in tool_name:
                feature_groups.update(["basic", "transaction_features", "risk_features",
                                      "behavioral_features", "network_features", "knowledge_graph"])

        return list(feature_groups) if feature_groups else ["basic"]


def create_intent_mapper_node(config: AgentConfig):
    """Create intent mapper node for LangGraph.

    Args:
        config: Agent configuration
    
    Returns:
        Intent mapper agent callable
    """
    agent = IntentMappingAgent(config)
    return agent
