"""API request and response models."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QueryContext(BaseModel):
    """Context for a query - provides known information about the investigation.
    
    This replaces fragile entity extraction from user queries. The UI/frontend
    should always provide the customer being investigated.
    """
    
    cif_no: str = Field(
        ..., 
        description="Customer ID (CIF number) - always required",
        min_length=1
    )
    alert_id: Optional[str] = Field(
        None, 
        description="Alert ID if query is in context of reviewing an alert"
    )
    investigation_id: Optional[str] = Field(
        None,
        description="Investigation ID for tracking multi-session investigations"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "cif_no": "C000001",
                "alert_id": "ALT12345",
                "investigation_id": "INV789"
            }
        }


class QueryRequest(BaseModel):
    """Request model for querying the AML Copilot."""

    query: str = Field(..., description="Natural language query", min_length=1)
    context: QueryContext = Field(..., description="Query context (customer, alert, etc.)")
    user_id: str = Field(..., description="User ID")  # TODO: Extract from JWT in Phase 6
    session_id: str = Field(..., description="Session ID for conversation tracking")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the customer's risk score?",
                "context": {
                    "cif_no": "C000001",
                    "alert_id": "ALT12345"
                },
                "user_id": "jane_doe",
                "session_id": "investigation_abc123"
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
