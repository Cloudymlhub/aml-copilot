"""Agent configuration models."""

from typing import Optional
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for a single agent.
    
    This model defines the LLM settings and runtime parameters
    for each specialized agent in the AML Copilot system.
    """
    
    model_name: str = Field(
        ..., 
        description="LLM model name (e.g., gpt-4o-mini, gpt-4o)"
    )
    temperature: float = Field(
        0.0, 
        ge=0.0, 
        le=2.0,
        description="Sampling temperature for LLM responses"
    )
    max_retries: int = Field(
        3, 
        ge=1,
        description="Maximum number of retry attempts for failed LLM calls"
    )
    timeout: int = Field(
        60, 
        ge=10,
        description="Timeout in seconds for LLM calls"
    )
    message_history_limit: Optional[int] = Field(
        0,
        description="Number of conversation messages to include (None=ALL, 0=NONE, N=last N)"
    )
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "model_name": "gpt-4o-mini",
                "temperature": 0.0,
                "max_retries": 3,
                "timeout": 60,
                "message_history_limit": 3
            }
        }

class ReviewAgentConfig(AgentConfig):
    max_review_attempts: int = Field(
        3,
        ge=1,
        description="Maximum number of review cycles before forcing completion"
    )

class AgentsConfig(BaseModel):
    """Configuration for all agents in the AML Copilot system.

    This model aggregates the configurations for each specialized agent,
    allowing different models and parameters per agent role.
    """

    coordinator: AgentConfig = Field(
        ...,
        description="Configuration for the Coordinator agent"
    )
    intent_mapper: AgentConfig = Field(
        ...,
        description="Configuration for the Intent Mapper agent"
    )
    data_retrieval: AgentConfig = Field(
        ...,
        description="Configuration for the Data Retrieval agent"
    )
    compliance_expert: AgentConfig = Field(
        ...,
        description="Configuration for the Compliance Expert agent"
    )
    review_expert: ReviewAgentConfig = Field(
        ...,
        description="Configuration for the Review Expert agent"
    )
    aml_alert_reviewer: AgentConfig = Field(
        ...,
        description="Configuration for the AML Alert Reviewer agent"
    )
    
