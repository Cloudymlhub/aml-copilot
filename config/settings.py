"""Configuration settings for AML Copilot."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class CustomBaseSettings(BaseSettings):
    """Custom base settings to enable case-insensitive environment variable loading."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        case_sensitive=False,
        extra="ignore",
    )

class Settings(CustomBaseSettings):
    """Application settings loaded from environment variables."""

    # Database settings
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "aml_compliance"
    database_user: str = "postgres"
    database_password: str = "postgres"

    # Redis settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db_cache: int = 0  # For data caching
    redis_db_checkpoints: int = 1  # For LangGraph state persistence
    redis_password: Optional[str] = None
    enable_redis_checkpointing: bool = True  # Enable state persistence across sessions

    # LLM settings
    openai_api_key: str
    llm_model: str = "gpt-4"  # Deprecated - use per-agent settings
    llm_temperature: float = 0.1  # Deprecated - use per-agent settings

    # LangSmith settings (observability and tracing)
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "aml-copilot"
    langsmith_tracing_enabled: bool = True  # Enable automatic tracing
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # Per-agent LLM configurations
    coordinator_model: str = "gpt-4o-mini"
    coordinator_temperature: float = 0.0
    coordinator_max_retries: int = 3
    coordinator_timeout: int = 60
    
    intent_mapper_model: str = "gpt-4o-mini"
    intent_mapper_temperature: float = 0.0
    intent_mapper_max_retries: int = 3
    intent_mapper_timeout: int = 60
    
    compliance_expert_model: str = "gpt-4o"  # More powerful for compliance analysis
    compliance_expert_temperature: float = 0.1
    compliance_expert_max_retries: int = 3
    compliance_expert_timeout: int = 120  # More time for complex analysis
    
    review_expert_model: str = "gpt-4o"  # More powerful for compliance analysis
    review_expert_temperature: float = 0.1
    review_expert_max_retries: int = 3
    review_expert_timeout: int = 120  # More time for complex analysis
    # Review system settings
    max_review_attempts: int = 3  # Maximum number of review cycles before forcing completion

    aml_alert_reviewer_model: str = "gpt-4o"  # Powerful model for alert review and SAR generation
    aml_alert_reviewer_temperature: float = 0.0  # Deterministic for compliance decisions
    aml_alert_reviewer_max_retries: int = 3
    aml_alert_reviewer_timeout: int = 120  # Complex analysis needs time

    # Agent settings
    max_agent_iterations: int = 10
    agent_timeout: int = 300  # seconds

    # Cache settings
    cache_ttl: int = 3600  # seconds (1 hour)
    enable_caching: bool = True

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return (
            f"postgresql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db_cache}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db_cache}"
    
    @property
    def checkpoint_redis_url(self) -> str:
        """Construct Redis connection URL for checkpoints."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db_checkpoints}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db_checkpoints}"
    
    def get_agents_config(self):
        """Build agents configuration from settings.

        Returns:
            AgentsConfig: Configuration for all agents
        """
        from config.agent_config import AgentsConfig, AgentConfig, ReviewAgentConfig

        return AgentsConfig(
            coordinator=AgentConfig(
                model_name=self.coordinator_model,
                temperature=self.coordinator_temperature,
                max_retries=self.coordinator_max_retries,
                timeout=self.coordinator_timeout,
                message_history_limit=3,  # Last 3 messages - basic continuity detection
            ),
            intent_mapper=AgentConfig(
                model_name=self.intent_mapper_model,
                temperature=self.intent_mapper_temperature,
                max_retries=self.intent_mapper_max_retries,
                timeout=self.intent_mapper_timeout,
                message_history_limit=10,  # Last 10 messages - reference resolution
            ),
            data_retrieval=AgentConfig(
                model_name="gpt-4o-mini",  # Not used (pure executor)
                temperature=0.0,
                max_retries=3,
                timeout=60,
                message_history_limit=0,  # NO history - pure executor
            ),
            compliance_expert=AgentConfig(
                model_name=self.compliance_expert_model,
                temperature=self.compliance_expert_temperature,
                max_retries=self.compliance_expert_max_retries,
                timeout=self.compliance_expert_timeout,
                message_history_limit=None,  # ALL messages - comprehensive analysis
            ),
            review_expert=ReviewAgentConfig(
                model_name=self.review_expert_model,  # Uses same model as review Expert
                temperature=self.review_expert_temperature,
                max_retries=self.review_expert_max_retries,
                timeout=self.review_expert_timeout,
                max_review_attempts=self.max_review_attempts,
                message_history_limit=None,  # ALL messages - quality assurance needs everything
            ),
            aml_alert_reviewer=AgentConfig(
                model_name=self.aml_alert_reviewer_model,
                temperature=self.aml_alert_reviewer_temperature,
                max_retries=self.aml_alert_reviewer_max_retries,
                timeout=self.aml_alert_reviewer_timeout,
                message_history_limit=None,  # ALL messages - full investigation context needed
            ),
        )


# Global settings instance
settings = Settings()
