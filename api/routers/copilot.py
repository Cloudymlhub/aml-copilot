"""Copilot-related API routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status

from db.services.cache_service import cache_service
from tools.registry import get_tool_descriptions
from agents.copilot import AMLCopilot
from api.models import (
    QueryRequest,
    QueryResponse,
    ComplianceAnalysisResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Copilot"])


def require_copilot(request: Request) -> AMLCopilot:
    copilot = getattr(request.app.state, "copilot", None)
    if not copilot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AML Copilot agent not initialized",
        )
    return copilot


@router.post(
    "/api/query",
    response_model=QueryResponse,
    summary="Query the AML Copilot",
    responses={
        200: {"description": "Successful query"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def query_copilot(request: QueryRequest, copilot: AMLCopilot = Depends(require_copilot)):
    """
    Query the AML Copilot with a natural language question.

    The copilot will:
    1. Route the query to appropriate agents
    2. Retrieve data if needed
    3. Provide compliance analysis and recommendations
    """
    try:
        logger.info("Processing query for customer %s", request.context.cif_no)

        result = copilot.query(
            user_query=request.query,
            context=request.context.model_dump(),
            session_id=request.session_id,
            user_id=request.user_id,
        )

        response = QueryResponse(
            response=result.get("response", "Unable to process query"),
            session_id=request.session_id,
            compliance_analysis=None,
            retrieved_data=None,
        )

        if result.get("compliance_analysis"):
            analysis = result["compliance_analysis"]
            response.compliance_analysis = ComplianceAnalysisResponse(
                analysis=analysis.get("analysis", ""),
                risk_assessment=analysis.get("risk_assessment"),
                typologies=analysis.get("typologies", []),
                recommendations=analysis.get("recommendations", []),
                regulatory_references=analysis.get("regulatory_references", []),
            )

        if result.get("retrieved_data") and result["retrieved_data"].get("success"):
            response.retrieved_data = result["retrieved_data"].get("data")

        logger.info("Query processed successfully: %s", request.session_id or "no-session")
        return response

    except Exception as exc:
        logger.error("Error processing query: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(exc)}",
        )


@router.get(
    "/api/tools",
    summary="List available tools",
)
async def list_tools():
    """List all available tools for data retrieval."""
    try:
        return get_tool_descriptions()
    except Exception as exc:
        logger.error("Error listing tools: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing tools: {str(exc)}",
        )


@router.post(
    "/api/cache/clear",
    summary="Clear Redis cache",
)
async def clear_cache():
    """Clear the Redis cache."""
    try:
        cache_service.flush_all()
        logger.info("Cache cleared successfully")
        return {"status": "success", "message": "Cache cleared"}
    except Exception as exc:
        logger.error("Error clearing cache: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing cache: {str(exc)}",
        )


@router.get(
    "/api/sessions/{user_id}/{session_id}/history",
    summary="Get conversation history",
)
async def get_conversation_history(
    user_id: str,
    session_id: str,
    copilot: AMLCopilot = Depends(require_copilot),
):
    """
    Get the conversation history for a specific session.
    """
    try:
        history = copilot.get_conversation_history(user_id, session_id)

        if history is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {user_id}/{session_id}",
            )

        return {
            "user_id": user_id,
            "session_id": session_id,
            "messages": history,
            "message_count": len(history),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error getting conversation history: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting conversation history: {str(exc)}",
        )


@router.get(
    "/api/sessions/{user_id}/{session_id}",
    summary="Get session info",
)
async def get_session_info(
    user_id: str,
    session_id: str,
    copilot: AMLCopilot = Depends(require_copilot),
):
    """
    Get metadata about a session.
    """
    try:
        info = copilot.get_session_info(user_id, session_id)

        if info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {user_id}/{session_id}",
            )

        return info
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error getting session info: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting session info: {str(exc)}",
        )


@router.delete(
    "/api/sessions/{user_id}/{session_id}",
    summary="Clear/delete a session",
)
async def clear_session(
    user_id: str,
    session_id: str,
    copilot: AMLCopilot = Depends(require_copilot),
):
    """
    Clear/delete a session and all its conversation history.
    """
    try:
        cleared = copilot.clear_session(user_id, session_id)

        if not cleared:
            logger.warning("Session not found or could not be cleared: %s/%s", user_id, session_id)

        return {
            "status": "success" if cleared else "not_found",
            "message": f"Session cleared: {user_id}/{session_id}" if cleared else "Session not found",
            "user_id": user_id,
            "session_id": session_id,
        }
    except Exception as exc:
        logger.error("Error clearing session: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing session: {str(exc)}",
        )
