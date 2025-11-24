"""Data Retrieval Agent - Executes data queries using tools."""

import inspect
import logging
from typing import Dict, Any

from langchain.tools import BaseTool

from agents.base_agent import BaseAgent
from agents.state import AMLCopilotState, DataRetrievalResult, AgentResponse
from config.agent_config import AgentConfig
from tools import get_all_tools


class DataRetrievalAgent(BaseAgent):
    """Data retrieval agent that executes queries using available tools.
    
    Message History: NONE (limit=0)
    Rationale: Pure executor that doesn't use LLMs or need conversation context.
               Simply executes tools based on intent mapper's structured output.
    """

    def __init__(self, config: AgentConfig):
        """Initialize data retrieval agent.
        
        Args:
            config: Agent configuration (limit should be 0 for data retrieval)
        """
        super().__init__(config)  # Initialize BaseAgent
        
        # Load all tools
        self.tools = get_all_tools()
        self.tool_map = {tool.name: tool for tool in self.tools}

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool with arguments.

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            Tool execution result
        """
        if tool_name not in self.tool_map:
            return {"error": f"Tool '{tool_name}' not found"}

        tool = self.tool_map[tool_name]

        try:
            # Execute tool
            self.logger.info("DataRetrieval: executing tool %s with args keys=%s", tool_name, list(args.keys()))
            result = tool._run(**args)
            return result
        except Exception as e:
            self.logger.exception("DataRetrieval: tool %s failed", tool_name)
            return {"error": f"Tool execution failed: {str(e)}"}

    def __call__(self, state: AMLCopilotState) -> AgentResponse:
        """Execute data retrieval based on intent.

        Args:
            state: Current state

        Returns:
            AgentResponse with retrieved data and routing decision
        """
        self.log_agent_start(state)
        intent = state.get("intent")

        if not intent:
            retrieval_result: DataRetrievalResult = {
                "success": False,
                "data": {},
                "tools_used": [],
                "error": "No intent mapping found",
                "errors": None
            }
            return {
                "retrieved_data": retrieval_result,
                "next_agent": "compliance_expert",
                "current_step": "data_retrieval_failed"
            }

        tools_to_use = intent.get("tools_to_use", [])

        if not tools_to_use:
            retrieval_result: DataRetrievalResult = {
                "success": False,
                "data": {},
                "tools_used": [],
                "error": "No tools specified in intent",
                "errors": None
            }
            return {
                "retrieved_data": retrieval_result,
                "next_agent": "compliance_expert",
                "current_step": "data_retrieval_failed"
            }

        # Execute all tools
        all_data = {}
        tools_used = []
        errors = []
        error_details = []

        for tool_spec in tools_to_use:
            # Handle both dict and string formats
            if isinstance(tool_spec, dict):
                tool_name = tool_spec.get("tool", "")
                tool_args = tool_spec.get("args", {}) or {}
            else:
                # Simple string tool name - extract args from entities
                tool_name = tool_spec
                tool_args = intent.get("entities", {})

            if not tool_name:
                continue

            # Validate required args against tool signature
            tool = self.tool_map.get(tool_name)
            required_params = []
            if tool:
                sig = inspect.signature(tool._run)
                required_params = [
                    name
                    for name, param in sig.parameters.items()
                    if name != "self"
                    and param.default is inspect._empty
                    and param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
                ]

            missing_params = [p for p in required_params if p not in tool_args]
            if missing_params:
                msg = f"Missing required args for {tool_name}: {', '.join(missing_params)}"
                errors.append(f"{tool_name}: {msg}")
                error_details.append({"tool": tool_name, "error": msg})
                self.logger.warning("DataRetrieval: skipping tool %s due to missing args: %s", tool_name, missing_params)
                continue

            # Execute tool
            result = self._execute_tool(tool_name, tool_args)
            tools_used.append(tool_name)

            # Store result
            if "error" in result:
                errors.append(f"{tool_name}: {result['error']}")
                error_details.append({"tool": tool_name, "error": result["error"]})
            else:
                all_data[tool_name] = result

        # Build retrieval result
        retrieval_result: DataRetrievalResult = {
            "success": len(errors) == 0,
            "data": all_data,
            "tools_used": tools_used,
            "error": "; ".join(errors) if errors else None,
            "errors": error_details if error_details else None
        }

        # Determine next step
        next_agent = "compliance_expert" if state["user_query"] else "end"

        return {
            "retrieved_data": retrieval_result,
            "next_agent": next_agent,
            "current_step": "data_retrieved" if retrieval_result["success"] else "data_retrieval_partial",
            "messages": self._append_message(
                state, 
                f"[Data Retrieval] Executed {len(tools_used)} tools. Success: {retrieval_result['success']}"
            )
        }


def create_data_retrieval_node(config: AgentConfig):
    """Create data retrieval node for LangGraph.

    Args:
        config: Agent configuration (should have message_history_limit=0)
    
    Returns:
        Data retrieval agent callable
    """
    agent = DataRetrievalAgent(config)
    return agent
