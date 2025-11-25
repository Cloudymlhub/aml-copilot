"""Tool registry for all AML compliance data retrieval tools."""

from typing import List
from langchain.tools import BaseTool

from .customer_tools import CustomerDataTools
from .transaction_tools import TransactionDataTools
from .alert_tools import AlertDataTools
from .ml_output_tools import get_ml_risk_assessment, get_feature_importance


def get_all_tools() -> List[BaseTool]:
    """Get all data retrieval tools for AML compliance.

    Returns:
        List of LangChain tools for:
        - Customer data retrieval (8 tools)
        - Transaction data retrieval (4 tools)
        - Alert data retrieval (5 tools)
        - ML model output retrieval (2 tools)

    Note: These tools return FACTUAL data only, with no interpretation.
    All database access uses dependency injection via the service layer.
    The Compliance Expert agent handles all AML analysis and interpretation.
    """
    tools = []

    # Customer data tools
    tools.extend(CustomerDataTools.get_tools())

    # Transaction data tools
    tools.extend(TransactionDataTools.get_tools())

    # Alert data tools
    tools.extend(AlertDataTools.get_tools())

    # ML model output tools (Phase 5)
    tools.append(get_ml_risk_assessment)
    tools.append(get_feature_importance)

    return tools


def get_tools_by_category(category: str) -> List[BaseTool]:
    """Get tools for a specific category.

    Args:
        category: One of 'customer', 'transaction', 'alert', 'ml_output'

    Returns:
        List of tools for the specified category
    """
    if category == "customer":
        return CustomerDataTools.get_tools()
    elif category == "transaction":
        return TransactionDataTools.get_tools()
    elif category == "alert":
        return AlertDataTools.get_tools()
    elif category == "ml_output":
        return [get_ml_risk_assessment, get_feature_importance]
    else:
        raise ValueError(f"Unknown category: {category}. Must be 'customer', 'transaction', 'alert', or 'ml_output'")


def get_tool_descriptions() -> dict:
    """Get descriptions of all available tools organized by category.

    Returns:
        Dictionary with tool categories and their descriptions
    """
    ml_tools = [get_ml_risk_assessment, get_feature_importance]

    return {
        "customer_tools": {
            "count": len(CustomerDataTools.get_tools()),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description.split("\n")[0],  # First line only
                }
                for tool in CustomerDataTools.get_tools()
            ],
        },
        "transaction_tools": {
            "count": len(TransactionDataTools.get_tools()),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description.split("\n")[0],
                }
                for tool in TransactionDataTools.get_tools()
            ],
        },
        "alert_tools": {
            "count": len(AlertDataTools.get_tools()),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description.split("\n")[0],
                }
                for tool in AlertDataTools.get_tools()
            ],
        },
        "ml_output_tools": {
            "count": len(ml_tools),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description.split("\n")[0],
                }
                for tool in ml_tools
            ],
        },
    }
