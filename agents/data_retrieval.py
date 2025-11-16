"""Data Retrieval Agent - Executes data queries using tools."""

from typing import Dict, Any, List
from langchain.tools import BaseTool

from tools import get_all_tools
from .state import AMLCopilotState, DataRetrievalResult
from config.agent_config import AgentConfig


class DataRetrievalAgent:
    """Data retrieval agent that executes queries using available tools."""

    def __init__(self, config: AgentConfig):
        """Initialize data retrieval agent.
        
        Args:
            config: Agent configuration (currently unused, reserved for future LLM-based retrieval)
        """
        self.config = config
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
            result = tool._run(**args)
            return result
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}

    def __call__(self, state: AMLCopilotState) -> Dict[str, Any]:
        """Execute data retrieval based on intent.

        Args:
            state: Current state

        Returns:
            Updated state with retrieved data
        """
        intent = state.get("intent")

        if not intent:
            return {
                "retrieved_data": {
                    "success": False,
                    "data": {},
                    "tools_used": [],
                    "error": "No intent mapping found"
                },
                "next_agent": "compliance_expert",
                "current_step": "data_retrieval_failed"
            }

        tools_to_use = intent.get("tools_to_use", [])

        if not tools_to_use:
            return {
                "retrieved_data": {
                    "success": False,
                    "data": {},
                    "tools_used": [],
                    "error": "No tools specified in intent"
                },
                "next_agent": "compliance_expert",
                "current_step": "data_retrieval_failed"
            }

        # Execute all tools
        all_data = {}
        tools_used = []
        errors = []

        for tool_spec in tools_to_use:
            # Handle both dict and string formats
            if isinstance(tool_spec, dict):
                tool_name = tool_spec.get("tool", "")
                tool_args = tool_spec.get("args", {})
            else:
                # Simple string tool name - extract args from entities
                tool_name = tool_spec
                tool_args = intent.get("entities", {})

            if not tool_name:
                continue

            # Execute tool
            result = self._execute_tool(tool_name, tool_args)
            tools_used.append(tool_name)

            # Store result
            if "error" in result:
                errors.append(f"{tool_name}: {result['error']}")
            else:
                all_data[tool_name] = result

        # Build retrieval result
        retrieval_result: DataRetrievalResult = {
            "success": len(errors) == 0,
            "data": all_data,
            "tools_used": tools_used,
            "error": "; ".join(errors) if errors else None
        }

        # Determine next step
        next_agent = "compliance_expert" if state["user_query"] else "end"

        return {
            "retrieved_data": retrieval_result,
            "next_agent": next_agent,
            "current_step": "data_retrieved" if retrieval_result["success"] else "data_retrieval_partial",
            "messages": state["messages"] + [
                {
                    "role": "assistant",
                    "content": f"[Data Retrieval] Executed {len(tools_used)} tools. Success: {retrieval_result['success']}",
                    "timestamp": str(state.get("started_at", ""))
                }
            ]
        }


def create_data_retrieval_node(config: AgentConfig):
    """Create data retrieval node for LangGraph.

    Args:
        config: Agent configuration
    
    Returns:
        Data retrieval agent callable
    """
    agent = DataRetrievalAgent(config)
    return agent
