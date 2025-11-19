"""Health and root endpoints."""

import logging
from fastapi import APIRouter, Request

from db.manager import db_manager
from db.services.cache_service import cache_service
from api.models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "message": "AML Copilot API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health_check(request: Request):
    """Check health of API and dependencies."""
    # Check database
    db_status = "healthy"
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"
        logger.error("Database health check failed: %s", exc)

    # Check Redis
    redis_status = "healthy" if cache_service.health_check() else "unhealthy"

    # Check agent
    agent_instance = getattr(request.app.state, "copilot", None)
    agent_status = "healthy" if agent_instance is not None else "unhealthy"

    overall_status = "healthy" if all(
        [
            db_status == "healthy",
            redis_status == "healthy",
            agent_status == "healthy",
        ]
    ) else "degraded"

    return HealthResponse(
        status=overall_status,
        version="0.1.0",
        database=db_status,
        redis=redis_status,
        agents=agent_status,
    )
