"""AML Copilot multi-agent system.

Main exports:
- AMLCopilot: The main copilot class
- AMLCopilotState: State definition for the graph
- create_aml_copilot_graph: Graph construction function
- BaseAgent: Abstract base class for all agents
- AgentResponse: TypedDict for agent return values
"""

from .copilot import AMLCopilot
from .graph import create_aml_copilot_graph
from .state import (
    AMLCopilotState, 
    IntentMapping, 
    DataRetrievalResult, 
    ComplianceAnalysis,
    AgentResponse,
    get_conversation_context
)
from .base_agent import BaseAgent

__all__ = [
    "AMLCopilot",
    "create_aml_copilot_graph",
    "AMLCopilotState",
    "IntentMapping",
    "DataRetrievalResult",
    "ComplianceAnalysis",
    "BaseAgent",
    "AgentResponse",
    "get_conversation_context",
]
