"""Configuration settings for AML Copilot."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
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
    redis_db: int = 0  # Deprecated - use redis_db_cache or redis_db_checkpoints
    redis_db_cache: int = 0  # For data caching
    redis_db_checkpoints: int = 1  # For LangGraph state persistence
    redis_password: Optional[str] = None

    # LLM settings
    openai_api_key: str
    llm_model: str = "gpt-4"  # Deprecated - use per-agent settings
    llm_temperature: float = 0.1  # Deprecated - use per-agent settings

    # Per-agent LLM configurations
    coordinator_model: str = "gpt-4o-mini"
    coordinator_temperature: float = 0.0
    coordinator_max_retries: int = 3
    coordinator_timeout: int = 60
    
    intent_mapper_model: str = "gpt-4o-mini"
    intent_mapper_temperature: float = 0.0
    intent_mapper_max_retries: int = 3
    intent_mapper_timeout: int = 60
    
    data_retrieval_model: str = "gpt-4o-mini"
    data_retrieval_temperature: float = 0.0
    data_retrieval_max_retries: int = 3
    data_retrieval_timeout: int = 60
    
    compliance_expert_model: str = "gpt-4o"  # More powerful for compliance analysis
    compliance_expert_temperature: float = 0.1
    compliance_expert_max_retries: int = 3
    compliance_expert_timeout: int = 120  # More time for complex analysis

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
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    def get_agents_config(self):
        """Build agents configuration from settings.
        
        Returns:
            AgentsConfig: Configuration for all agents
        """
        from config.agent_config import AgentsConfig, AgentConfig
        
        return AgentsConfig(
            coordinator=AgentConfig(
                model_name=self.coordinator_model,
                temperature=self.coordinator_temperature,
                max_retries=self.coordinator_max_retries,
                timeout=self.coordinator_timeout,
            ),
            intent_mapper=AgentConfig(
                model_name=self.intent_mapper_model,
                temperature=self.intent_mapper_temperature,
                max_retries=self.intent_mapper_max_retries,
                timeout=self.intent_mapper_timeout,
            ),
            data_retrieval=AgentConfig(
                model_name=self.data_retrieval_model,
                temperature=self.data_retrieval_temperature,
                max_retries=self.data_retrieval_max_retries,
                timeout=self.data_retrieval_timeout,
            ),
            compliance_expert=AgentConfig(
                model_name=self.compliance_expert_model,
                temperature=self.compliance_expert_temperature,
                max_retries=self.compliance_expert_max_retries,
                timeout=self.compliance_expert_timeout,
            ),
        )


# Global settings instance
settings = Settings()
