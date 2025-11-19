"""Review Agent - Quality assurance for compliance responses."""

import json
import logging
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import AMLCopilotState
from ..prompts import REVIEW_AGENT_PROMPT
from config.agent_config import AgentConfig, ReviewAgentConfig
from config.settings import settings


class ReviewAgent:
    """Dedicated QA agent that evaluates compliance expert outputs."""

    def __init__(self, config: ReviewAgentConfig):
        """Initialize review agent.

        Args:
            config: Agent configuration with model settings
            max_review_attempts: Maximum number of review cycles before forcing completion
        """
        self.config = config
        self.llm = ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            max_retries=config.max_retries,
            timeout=config.timeout,
            api_key=settings.openai_api_key,
        )
        self.max_review_attempts = config.max_review_attempts
        self.logger = logging.getLogger(__name__)

    def __call__(self, state: AMLCopilotState) -> Dict[str, Any]:
        """Review compliance expert output and determine next steps.

        Args:
            state: Current state with compliance_analysis and final_response

        Returns:
            Updated state with review results and routing decision
        """
        self.logger.info("ReviewAgent: invoked for session=%s attempt=%s", state.get("session_id"), state.get("review_attempts", 0))
        user_query = state["user_query"]
        final_response = state.get("final_response", "")
        compliance_analysis = state.get("compliance_analysis", {})
        retrieved_data = state.get("retrieved_data", {})
        review_attempts = state.get("review_attempts", 0) or 0

        # Check if we've exceeded max attempts
        if review_attempts >= self.max_review_attempts:
            return {
                "review_status": "passed",  # Force pass to avoid infinite loop
                "review_feedback": f"Max review attempts ({self.max_review_attempts}) reached. Proceeding with current response.",
                "review_agent_id": self.config.model_name,
                "review_attempts": review_attempts,
                "next_agent": "end",
                "current_step": "review_max_attempts",
                "completed": True,
                "messages": state["messages"] + [
                    {
                        "role": "assistant",
                        "content": final_response,
                        "timestamp": str(state.get("started_at", ""))
                    }
                ]
            }

        # Format context for review
        retrieved_data_str = json.dumps(retrieved_data.get("data", {}) if retrieved_data else {}, indent=2)
        analysis_str = json.dumps(compliance_analysis, indent=2)

        def _build_messages(invalid: bool = False):
            """Construct system/human messages with optional retry notice."""
            prefix = "Your last reply was invalid JSON. Respond with JSON only per schema. " if invalid else ""
            human_content = (
                f"{prefix}Original user query: {user_query}\n"
                f"Generated response: {final_response}\n"
                f"Compliance analysis (internal): {analysis_str}\n"
                f"Retrieved data: {retrieved_data_str}"
            )
            return [
                SystemMessage(content=REVIEW_AGENT_PROMPT),
                HumanMessage(content=human_content)
            ]

        def _parse_json(raw_response):
            try:
                return json.loads(raw_response.content)
            except json.JSONDecodeError:
                return None

        review_response = self.llm.invoke(_build_messages())
        review_result = _parse_json(review_response)

        if review_result is None:
            retry_response = self.llm.invoke(_build_messages(invalid=True))
            review_result = _parse_json(retry_response)

        if review_result:
            review_status = review_result.get("review_status", "passed")
            review_feedback = review_result.get("review_feedback", "Review completed.")
            additional_query = review_result.get("additional_query")
            confidence = review_result.get("confidence", 1.0)
        else:
            # Fail-safe: if we can't parse, pass the review
            review_status = "passed"
            review_feedback = "Review completed (unable to parse structured output)."
            additional_query = None
            confidence = 0.8

        # Determine routing based on review status
        if review_status == "passed":
            return {
                "review_status": review_status,
                "review_feedback": review_feedback,
                "review_agent_id": self.config.model_name,
                "review_attempts": review_attempts + 1,
                "next_agent": "end",
                "current_step": "review_passed",
                "completed": True,
                "messages": state["messages"] + [
                    {
                        "role": "assistant",
                        "content": final_response,
                        "timestamp": str(state.get("started_at", ""))
                    }
                ]
            }
        elif review_status == "needs_data":
            return {
                "review_status": review_status,
                "review_feedback": review_feedback,
                "additional_query": additional_query,
                "review_agent_id": self.config.model_name,
                "review_attempts": review_attempts + 1,
                "next_agent": "intent_mapper",  # Get more data
                "current_step": "review_needs_data",
                "completed": False,
                "messages": state["messages"]
            }
        elif review_status == "needs_refinement":
            return {
                "review_status": review_status,
                "review_feedback": review_feedback,
                "review_agent_id": self.config.model_name,
                "review_attempts": review_attempts + 1,
                "next_agent": "compliance_expert",  # Retry analysis
                "current_step": "review_needs_refinement",
                "completed": False,
                "messages": state["messages"]
            }
        elif review_status == "needs_clarification":
            return {
                "review_status": review_status,
                "review_feedback": review_feedback,
                "additional_query": additional_query,
                "review_agent_id": self.config.model_name,
                "review_attempts": review_attempts + 1,
                "next_agent": "coordinator",  # Ask user for clarification
                "current_step": "review_needs_clarification",
                "completed": False,
                "messages": state["messages"]
            }
        elif review_status == "human_review":
            return {
                "review_status": review_status,
                "review_feedback": review_feedback,
                "review_agent_id": self.config.model_name,
                "review_attempts": review_attempts + 1,
                "next_agent": "end",  # Interrupt for human review
                "current_step": "review_human_required",
                "completed": False,
                "messages": state["messages"]
            }
        else:
            # Unknown status, default to pass
            return {
                "review_status": "passed",
                "review_feedback": f"Unknown review status: {review_status}. Defaulting to pass.",
                "review_agent_id": self.config.model_name,
                "review_attempts": review_attempts + 1,
                "next_agent": "end",
                "current_step": "review_completed",
                "completed": True,
                "messages": state["messages"] + [
                    {
                        "role": "assistant",
                        "content": final_response,
                        "timestamp": str(state.get("started_at", ""))
                    }
                ]
            }


def create_review_agent_node(config: ReviewAgentConfig):
    """Create review agent node for LangGraph.

    Args:
        config: Agent configuration

    Returns:
        Review agent callable
    """
    agent = ReviewAgent(config)
    return agent
