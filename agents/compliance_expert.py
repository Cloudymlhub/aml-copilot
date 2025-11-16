"""Compliance Expert Agent - Provides AML domain expertise and interpretation."""

import json
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .state import AMLCopilotState, ComplianceAnalysis
from .prompts import COMPLIANCE_EXPERT_PROMPT, RESPONSE_SYNTHESIS_PROMPT
from config.agent_config import AgentConfig


class ComplianceExpertAgent:
    """Compliance expert agent that interprets data and provides AML guidance."""

    def __init__(self, config: AgentConfig):
        """Initialize compliance expert agent.

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
        """Provide compliance expertise and analysis.

        Args:
            state: Current state

        Returns:
            Updated state with compliance analysis and final response
        """
        user_query = state["user_query"]
        retrieved_data = state.get("retrieved_data")

        # Format retrieved data for prompt
        if retrieved_data and retrieved_data.get("success"):
            data_str = json.dumps(retrieved_data.get("data", {}), indent=2)
        else:
            data_str = "No data retrieved" if retrieved_data else "No data retrieval attempted"

        # Create prompt
        prompt = COMPLIANCE_EXPERT_PROMPT.format(
            user_query=user_query,
            retrieved_data=data_str
        )

        # Get compliance analysis from LLM
        messages = [
            SystemMessage(content="You are an AML compliance expert. Provide thorough, accurate analysis."),
            HumanMessage(content=prompt)
        ]

        response = self.llm.invoke(messages)

        try:
            # Try to parse JSON response
            result = json.loads(response.content)

            compliance_analysis: ComplianceAnalysis = {
                "analysis": result.get("analysis", response.content),
                "risk_assessment": result.get("risk_assessment"),
                "typologies": result.get("typologies", []),
                "recommendations": result.get("recommendations", []),
                "regulatory_references": result.get("regulatory_references", [])
            }
        except json.JSONDecodeError:
            # If not JSON, treat entire response as analysis
            compliance_analysis: ComplianceAnalysis = {
                "analysis": response.content,
                "risk_assessment": None,
                "typologies": [],
                "recommendations": [],
                "regulatory_references": []
            }

        # Synthesize final response
        synthesis_prompt = RESPONSE_SYNTHESIS_PROMPT.format(
            user_query=user_query,
            intent=json.dumps(state.get("intent", {}), indent=2),
            retrieved_data=data_str,
            compliance_analysis=json.dumps(compliance_analysis, indent=2)
        )

        synthesis_messages = [
            SystemMessage(content="You are synthesizing a final response for the user. Be clear and professional."),
            HumanMessage(content=synthesis_prompt)
        ]

        final_response_msg = self.llm.invoke(synthesis_messages)
        final_response = final_response_msg.content

        return {
            "compliance_analysis": compliance_analysis,
            "final_response": final_response,
            "next_agent": "end",
            "current_step": "completed",
            "completed": True,
            "messages": state["messages"] + [
                {
                    "role": "assistant",
                    "content": final_response,
                    "timestamp": str(state.get("started_at", ""))
                }
            ]
        }


def create_compliance_expert_node(config: AgentConfig):
    """Create compliance expert node for LangGraph.

    Args:
        config: Agent configuration
    
    Returns:
        Compliance expert agent callable
    """
    agent = ComplianceExpertAgent(config)
    return agent
