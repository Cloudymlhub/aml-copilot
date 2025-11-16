"""API request and response models."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for querying the AML Copilot."""

    query: str = Field(..., description="Natural language query", min_length=1)
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation tracking")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the risk score for customer C000001?",
                "session_id": "session_123"
            }
        }


class ComplianceAnalysisResponse(BaseModel):
    """Compliance analysis from the expert agent."""

    analysis: str
    risk_assessment: Optional[str] = None
    typologies: List[str] = []
    recommendations: List[str] = []
    regulatory_references: List[str] = []


class QueryResponse(BaseModel):
    """Response model for AML Copilot queries."""

    response: str = Field(..., description="Final response to user query")
    session_id: str = Field(..., description="Session ID for tracking")
    compliance_analysis: Optional[ComplianceAnalysisResponse] = Field(
        None,
        description="Detailed compliance analysis if available"
    )
    retrieved_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Retrieved data from database (if applicable)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "response": "Customer C000001 has a risk score of 27.15 (LOW risk)...",
                "session_id": "session_123",
                "compliance_analysis": {
                    "analysis": "Customer presents low AML risk...",
                    "risk_assessment": "LOW",
                    "typologies": [],
                    "recommendations": ["Continue standard monitoring"],
                    "regulatory_references": []
                }
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    database: str
    redis: str
    agents: str


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Internal server error",
                "detail": "Database connection failed"
            }
        }
