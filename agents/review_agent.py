"""Review Agent - Quality assurance for compliance responses."""

import json
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .state import AMLCopilotState
from .prompts import REVIEW_AGENT_PROMPT
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

    def __call__(self, state: AMLCopilotState) -> Dict[str, Any]:
        """Review compliance expert output and determine next steps.

        Args:
            state: Current state with compliance_analysis and final_response

        Returns:
            Updated state with review results and routing decision
        """
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

        # Create review prompt
        prompt = REVIEW_AGENT_PROMPT.format(
            user_query=user_query,
            final_response=final_response,
            compliance_analysis=analysis_str,
            retrieved_data=retrieved_data_str
        )

        messages = [
            SystemMessage(content="You are a QA reviewer for AML compliance responses. Be thorough and objective."),
            HumanMessage(content=prompt)
        ]

        review_response = self.llm.invoke(messages)

        try:
            review_result = json.loads(review_response.content)
            review_status = review_result.get("review_status", "passed")
            review_feedback = review_result.get("review_feedback", "Review completed.")
            additional_query = review_result.get("additional_query")
            confidence = review_result.get("confidence", 1.0)
        except json.JSONDecodeError:
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
