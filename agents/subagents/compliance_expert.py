"""Compliance Expert Agent - Provides AML domain expertise and interpretation."""

import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import AMLCopilotState, ComplianceAnalysis, AgentResponse
from agents.base_agent import BaseAgent
from agents.prompts import COMPLIANCE_EXPERT_PROMPT, RESPONSE_SYNTHESIS_PROMPT
from config.agent_config import AgentConfig
from config.settings import settings


class ComplianceExpertAgent(BaseAgent):
    """Compliance expert agent that interprets data and provides AML guidance.
    
    Message History: ALL messages (limit=None)
    Rationale: Needs comprehensive conversation context for thorough compliance
               analysis. Must understand full investigation flow, previous findings,
               and user's complete line of inquiry.
    """

    def __init__(self, config: AgentConfig):
        """Initialize compliance expert agent.

        Args:
            config: Agent configuration with model settings and history limit
        """
        super().__init__(config)  # Initialize BaseAgent
        self.llm = ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            max_retries=config.max_retries,
            timeout=config.timeout,
            api_key=settings.openai_api_key,
        )


    def __call__(self, state: AMLCopilotState) -> AgentResponse:
        """Provide compliance expertise and analysis.

        Args:
            state: Current state

        Returns:
            AgentResponse with compliance analysis and final response
        """
        self.log_agent_start(state)
        
        user_query = state["user_query"]
        retrieved_data = state.get("retrieved_data")
        intent_payload = state.get("intent", {})
        
        # Get formatted conversation history for comprehensive analysis (ALL messages)
        history_context = self.get_conversation_history(state, formatted=True)

        # Format retrieved data for prompt
        if retrieved_data and retrieved_data.get("success"):
            data_str = json.dumps(retrieved_data.get("data", {}), indent=2)
        else:
            data_str = "No data retrieved" if retrieved_data else "No data retrieval attempted"

        intent_str = json.dumps(intent_payload, indent=2)

        def _build_analysis_messages(invalid: bool = False):
            """Construct messages for compliance analysis, with conversation history and optional retry notice."""
            prefix = "Your last reply was invalid JSON. Respond with JSON only per schema. " if invalid else ""

            # Include full conversation history for comprehensive compliance analysis
            context_section = f"{history_context}\n\n" if history_context else ""

            human_content = (
                f"{prefix}{context_section}"
                f"Current query: {user_query}\n"
                f"Intent (if any): {intent_str}\n"
                f"Retrieved data:\n{data_str}"
            )
            return [
                SystemMessage(content=COMPLIANCE_EXPERT_PROMPT),
                HumanMessage(content=human_content)
            ]

        # Use shared JSON parsing with automatic retry from BaseAgent
        analysis_result, analysis_response = self._invoke_with_json_retry(
            self.llm,
            _build_analysis_messages
        )

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
