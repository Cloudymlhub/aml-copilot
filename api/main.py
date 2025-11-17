"""FastAPI application for AML Copilot."""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from agents import AMLCopilot
from config.settings import settings
from db.manager import db_manager
from db.services.cache_service import cache_service
from tools.registry import get_tool_descriptions
from .models import (
    QueryRequest,
    QueryResponse,
    ComplianceAnalysisResponse,
    HealthResponse,
    ErrorResponse
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global agent instance
copilot = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    global copilot

    # Startup
    logger.info("Starting AML Copilot API...")
    try:
        # Get agent configurations from settings
        agents_config = settings.get_agents_config()
        logger.info(f"✓ Agent configurations loaded:")
        logger.info(f"  - Coordinator: {agents_config.coordinator.model_name}")
        logger.info(f"  - Intent Mapper: {agents_config.intent_mapper.model_name}")
        logger.info(f"  - Data Retrieval: No LLM")
        logger.info(f"  - Compliance Expert: {agents_config.compliance_expert.model_name}")
        
        # Initialize AML Copilot with configs
        # Note: Checkpointing disabled by default (requires Redis with RedisJSON)
        copilot = AMLCopilot(agents_config=agents_config, enable_checkpointing=False)
        logger.info("✓ AML Copilot agent initialized")
        logger.info("⚠️  Checkpointing disabled - conversations will not persist")
    except Exception as e:
        logger.error(f"✗ Failed to initialize agent: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down AML Copilot API...")
    # Close database connections
    db_manager.close_all()
    logger.info("✓ Database connections closed")


# Create FastAPI app
app = FastAPI(
    title="AML Copilot API",
    description="Multi-agent AML compliance assistant with data retrieval and expert analysis",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "message": "AML Copilot API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check"
)
async def health_check():
    """Check health of API and dependencies."""

    # Check database
    db_status = "healthy"
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        logger.error(f"Database health check failed: {e}")

    # Check Redis
    redis_status = "healthy" if cache_service.health_check() else "unhealthy"

    # Check agent
    agent_status = "healthy" if copilot is not None else "unhealthy"

    overall_status = "healthy" if all([
        db_status == "healthy",
        redis_status == "healthy",
        agent_status == "healthy"
    ]) else "degraded"

    return HealthResponse(
        status=overall_status,
        version="0.1.0",
        database=db_status,
        redis=redis_status,
        agents=agent_status
    )


@app.post(
    "/api/query",
    response_model=QueryResponse,
    tags=["Query"],
    summary="Query the AML Copilot",
    responses={
        200: {"description": "Successful query"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def query_copilot(request: QueryRequest):
    """
    Query the AML Copilot with a natural language question.

    The copilot will:
    1. Route the query to appropriate agents
    2. Retrieve data if needed
    3. Provide compliance analysis and recommendations

    **Examples:**
    - "What is the risk score for customer C000001?"
    - "Show me high-risk transactions for customer C000001"
    - "What is structuring?"
    - "Analyze customer C000001 for AML risk"
    """

    if not copilot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AML Copilot agent not initialized"
        )

    try:
        logger.info(f"Processing query for customer {request.context.cif_no}: {request.query[:100]}...")

        # Query the agent with context
        result = copilot.query(
            user_query=request.query,
            context=request.context.dict(),
            session_id=request.session_id,
            user_id=request.user_id
        )

        # Build response
        response = QueryResponse(
            response=result.get("response", "Unable to process query"),
            session_id=request.session_id,  # Use request session_id
            compliance_analysis=None,
            retrieved_data=None
        )

        # Add compliance analysis if available
        if result.get("compliance_analysis"):
            analysis = result["compliance_analysis"]
            response.compliance_analysis = ComplianceAnalysisResponse(
                analysis=analysis.get("analysis", ""),
                risk_assessment=analysis.get("risk_assessment"),
                typologies=analysis.get("typologies", []),
                recommendations=analysis.get("recommendations", []),
                regulatory_references=analysis.get("regulatory_references", [])
            )

        # Add retrieved data if available
        if result.get("retrieved_data") and result["retrieved_data"].get("success"):
            response.retrieved_data = result["retrieved_data"].get("data")

        logger.info(f"Query processed successfully: {request.session_id or 'no-session'}")
        return response

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )


@app.get(
    "/api/tools",
    tags=["Info"],
    summary="List available tools"
)
async def list_tools():
    """List all available tools for data retrieval."""

    try:
        return get_tool_descriptions()
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing tools: {str(e)}"
        )


@app.post(
    "/api/cache/clear",
    tags=["Cache"],
    summary="Clear Redis cache"
)
async def clear_cache():
    """Clear the Redis cache."""
    try:
        cache_service.flush_all()
        logger.info("Cache cleared successfully")
        return {"status": "success", "message": "Cache cleared"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing cache: {str(e)}"
        )


@app.get(
    "/api/sessions/{user_id}/{session_id}/history",
    tags=["Sessions"],
    summary="Get conversation history"
)
async def get_conversation_history(user_id: str, session_id: str):
    """
    Get the conversation history for a specific session.

    Returns all messages exchanged in the conversation, allowing
    users to review past interactions.
    """
    if not copilot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AML Copilot agent not initialized"
        )

    try:
        history = copilot.get_conversation_history(user_id, session_id)

        if history is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {user_id}/{session_id}"
            )

        return {
            "user_id": user_id,
            "session_id": session_id,
            "messages": history,
            "message_count": len(history)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting conversation history: {str(e)}"
        )


@app.get(
    "/api/sessions/{user_id}/{session_id}",
    tags=["Sessions"],
    summary="Get session info"
)
async def get_session_info(user_id: str, session_id: str):
    """
    Get metadata about a session.

    Returns information like when the session started, how many
    messages have been exchanged, and the current context.
    """
    if not copilot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AML Copilot agent not initialized"
        )

    try:
        info = copilot.get_session_info(user_id, session_id)

        if info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {user_id}/{session_id}"
            )

        return info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting session info: {str(e)}"
        )


@app.delete(
    "/api/sessions/{user_id}/{session_id}",
    tags=["Sessions"],
    summary="Clear/delete a session"
)
async def clear_session(user_id: str, session_id: str):
    """
    Clear/delete a session and all its conversation history.

    This is useful for:
    - Starting a fresh investigation
    - Cleaning up test sessions
    - Privacy/GDPR compliance
    """
    if not copilot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AML Copilot agent not initialized"
        )

    try:
        cleared = copilot.clear_session(user_id, session_id)

        if not cleared:
            logger.warning(f"Session not found or could not be cleared: {user_id}/{session_id}")

        return {
            "status": "success" if cleared else "not_found",
            "message": f"Session cleared: {user_id}/{session_id}" if cleared else "Session not found",
            "user_id": user_id,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing session: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
