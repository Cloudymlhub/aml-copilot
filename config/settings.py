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
    redis_db: int = 0
    redis_password: Optional[str] = None

    # LLM settings
    openai_api_key: str
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.1

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


# Global settings instance
settings = Settings()
