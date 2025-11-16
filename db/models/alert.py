"""AML alert data models."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AlertModel(BaseModel):
    """AML alert with investigation tracking."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    alert_id: str
    customer_id: int

    # Alert details
    alert_type: str
    alert_date: datetime
    severity: str
    status: str

    # Investigation
    assigned_to: Optional[str]
    description: Optional[str]
    investigation_notes: Optional[str]

    # Model information
    triggered_by_model: Optional[str]
    model_confidence: Optional[float]
    feature_importance: Optional[str]

    # Metadata
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    closed_at: Optional[datetime]


class AlertCreate(BaseModel):
    """Model for creating a new alert."""

    alert_id: str
    customer_id: int
    alert_type: str
    alert_date: datetime
    severity: str
    status: str = "open"
    description: Optional[str] = None
    triggered_by_model: Optional[str] = None
    model_confidence: Optional[float] = None


class AlertUpdate(BaseModel):
    """Model for updating alert information."""

    status: Optional[str] = None
    assigned_to: Optional[str] = None
    investigation_notes: Optional[str] = None
    severity: Optional[str] = None
