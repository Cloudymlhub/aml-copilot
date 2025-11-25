"""Agent prompts package - organized by agent.

Prompts are now modular, with reusable components in the components/ subdirectory.
This allows for:
- Independent maintenance of red flag catalogs, typology libraries, etc.
- Domain expert review of specific components
- Sharing components across multiple agents
- Easy testing with different component versions
"""

from .coordinator_prompt import COORDINATOR_PROMPT
from .intent_mapper_prompt import INTENT_MAPPER_PROMPT
from .data_retrieval_prompt import DATA_RETRIEVAL_PROMPT
from .compliance_expert_prompt import (
    COMPLIANCE_EXPERT_PROMPT,
    RESPONSE_SYNTHESIS_PROMPT,
    build_compliance_expert_prompt
)
from .review_agent_prompt import REVIEW_AGENT_PROMPT, SELF_REVIEW_PROMPT
from .aml_alert_reviewer_prompt import (
    ALERT_REVIEW_PROMPT,
    SAR_NARRATIVE_PROMPT,
    TRANSACTION_PATTERN_ANALYSIS_PROMPT,
    build_alert_review_prompt,
    build_transaction_pattern_analysis_prompt
)

__all__ = [
    "COORDINATOR_PROMPT",
    "INTENT_MAPPER_PROMPT",
    "DATA_RETRIEVAL_PROMPT",
    "COMPLIANCE_EXPERT_PROMPT",
    "RESPONSE_SYNTHESIS_PROMPT",
    "build_compliance_expert_prompt",
    "REVIEW_AGENT_PROMPT",
    "SELF_REVIEW_PROMPT",
    "ALERT_REVIEW_PROMPT",
    "SAR_NARRATIVE_PROMPT",
    "TRANSACTION_PATTERN_ANALYSIS_PROMPT",
    "build_alert_review_prompt",
    "build_transaction_pattern_analysis_prompt",
]
