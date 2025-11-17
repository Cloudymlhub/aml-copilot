"""Agent prompts package - organized by agent."""

from .coordinator_prompt import COORDINATOR_PROMPT
from .intent_mapper_prompt import INTENT_MAPPER_PROMPT
from .data_retrieval_prompt import DATA_RETRIEVAL_PROMPT
from .compliance_expert_prompt import (
    COMPLIANCE_EXPERT_PROMPT,
    RESPONSE_SYNTHESIS_PROMPT
)
from .review_agent_prompt import REVIEW_AGENT_PROMPT, SELF_REVIEW_PROMPT

__all__ = [
    "COORDINATOR_PROMPT",
    "INTENT_MAPPER_PROMPT",
    "DATA_RETRIEVAL_PROMPT",
    "COMPLIANCE_EXPERT_PROMPT",
    "RESPONSE_SYNTHESIS_PROMPT",
    "REVIEW_AGENT_PROMPT",
    "SELF_REVIEW_PROMPT",
]
