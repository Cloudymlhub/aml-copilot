"""Compliance Expert Agent - Provides AML domain expertise and interpretation."""

import json
import logging
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .state import AMLCopilotState, ComplianceAnalysis
from .prompts import COMPLIANCE_EXPERT_PROMPT, RESPONSE_SYNTHESIS_PROMPT
from config.agent_config import AgentConfig
from config.settings import settings


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
            api_key=settings.openai_api_key,
        )
        self.logger = logging.getLogger(__name__)


    def __call__(self, state: AMLCopilotState) -> Dict[str, Any]:
        """Provide compliance expertise and analysis.

        Args:
            state: Current state

        Returns:
            Updated state with compliance analysis and final response
        """
        self.logger.info("ComplianceExpert: invoked for session=%s", state.get("session_id"))
        user_query = state["user_query"]
        retrieved_data = state.get("retrieved_data")
        intent_payload = state.get("intent", {})

        # Format retrieved data for prompt
        if retrieved_data and retrieved_data.get("success"):
            data_str = json.dumps(retrieved_data.get("data", {}), indent=2)
        else:
            data_str = "No data retrieved" if retrieved_data else "No data retrieval attempted"

        intent_str = json.dumps(intent_payload, indent=2)

        def _build_analysis_messages(invalid: bool = False):
            """Construct messages for compliance analysis, with optional retry notice."""
            prefix = "Your last reply was invalid JSON. Respond with JSON only per schema. " if invalid else ""
            human_content = (
                f"{prefix}User query: {user_query}\n"
                f"Intent (if any): {intent_str}\n"
                f"Retrieved data:\n{data_str}"
            )
            return [
                SystemMessage(content=COMPLIANCE_EXPERT_PROMPT),
                HumanMessage(content=human_content)
            ]

        def _parse_json(raw_response):
            try:
                return json.loads(raw_response.content)
            except json.JSONDecodeError:
                return None

        # Primary attempt
        analysis_response = self.llm.invoke(_build_analysis_messages())
        analysis_result = _parse_json(analysis_response)

        # One-time retry if JSON parsing failed
        if analysis_result is None:
            retry_response = self.llm.invoke(_build_analysis_messages(invalid=True))
            analysis_result = _parse_json(retry_response)

        if analysis_result:
            compliance_analysis: ComplianceAnalysis = {
                "analysis": analysis_result.get("analysis", analysis_response.content),
                "risk_assessment": analysis_result.get("risk_assessment"),
                "typologies": analysis_result.get("typologies", []),
                "recommendations": analysis_result.get("recommendations", []),
                "regulatory_references": analysis_result.get("regulatory_references", [])
            }
        else:
            # If not JSON, treat entire response as analysis
            compliance_analysis: ComplianceAnalysis = {
                "analysis": analysis_response.content,
                "risk_assessment": None,
                "typologies": [],
                "recommendations": [],
                "regulatory_references": []
            }

        # Synthesize final response
        synthesis_human = (
            f"User query: {user_query}\n"
            f"Intent: {intent_str}\n"
            f"Retrieved data:\n{data_str}\n"
            f"Compliance analysis:\n{json.dumps(compliance_analysis, indent=2)}"
        )

        # Add review feedback if this is a retry (from ReviewAgent)
        previous_feedback = state.get("review_feedback")
        if previous_feedback:
            synthesis_human += f"\n\nPrevious review feedback (address these issues):\n{previous_feedback}"

        synthesis_messages = [
            SystemMessage(content=RESPONSE_SYNTHESIS_PROMPT),
            HumanMessage(content=synthesis_human)
        ]

        final_response_msg = self.llm.invoke(synthesis_messages)
        final_response = final_response_msg.content

        # Return analysis and response (ReviewAgent will evaluate this)
        return {
            "compliance_analysis": compliance_analysis,
            "final_response": final_response,
            "next_agent": "review_agent",  # Route to review
            "current_step": "compliance_completed",
            "completed": False,  # Not done until review passes
            "messages": state["messages"]  # ReviewAgent will decide if we add to messages
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
