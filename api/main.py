"""FastAPI application entrypoint for AML Copilot."""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.copilot import AMLCopilot
from config.settings import settings
from db.manager import db_manager
from api.routers import health, copilot

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_checkpointer(redis_url: str) -> Optional[any]:
    """Factory function to create a Redis checkpointer.

    Args:
        redis_url: Redis connection URL (e.g., "redis://localhost:6379/1")

    Returns:
        RedisSaver instance if successful, None otherwise
    """
    try:
        from langgraph.checkpoint.redis import RedisSaver

        checkpointer = RedisSaver(redis_url)
        logger.info("✓ Redis checkpointing enabled")
        return checkpointer
    except Exception as e:
        logger.warning("⚠️  Checkpointing disabled: %s", e)
        logger.warning("   Conversation history will not persist across sessions")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for the API."""
    logger.info("Starting AML Copilot API...")
    try:
        # Load agent configurations
        agents_config = settings.get_agents_config()
        logger.info("✓ Agent configurations loaded:")
        logger.info("  - Coordinator: %s", agents_config.coordinator.model_name)
        logger.info("  - Intent Mapper: %s", agents_config.intent_mapper.model_name)
        logger.info("  - Data Retrieval: No LLM")
        logger.info("  - Compliance Expert: %s", agents_config.compliance_expert.model_name)

        # Create checkpointer if enabled
        checkpointer = None
        if settings.enable_redis_checkpointing:
            checkpointer = create_checkpointer(settings.checkpoint_redis_url)

        # Initialize copilot with dependency injection
        app.state.copilot = AMLCopilot(
            agents_config=agents_config,
            checkpointer=checkpointer
        )
        logger.info("✓ AML Copilot agent initialized")

        if not checkpointer:
            logger.info("⚠️  Checkpointing disabled - conversations will not persist")
    except Exception as exc:
        logger.error("✗ Failed to initialize agent: %s", exc)
        raise

    yield

    logger.info("Shutting down AML Copilot API...")
    db_manager.close_all_connections()
    logger.info("✓ Database connections closed")


app = FastAPI(
    title="AML Copilot API",
    description="Multi-agent AML compliance assistant with data retrieval and expert analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(copilot.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
