"""Compliance report data models."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ReportModel(BaseModel):
    """Compliance report (SAR, STR, internal)."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    report_id: str
    alert_id: Optional[int]

    # Report details
    report_type: str
    title: Optional[str]
    content: str
    summary: Optional[str]

    # Status and workflow
    status: Optional[str]
    created_by: str
    reviewed_by: Optional[str]
    approved_by: Optional[str]

    # Metadata
    created_date: Optional[datetime]
    submitted_date: Optional[datetime]
    filed_date: Optional[datetime]


class ReportCreate(BaseModel):
    """Model for creating a new report."""

    report_id: str
    alert_id: Optional[int] = None
    report_type: str
    title: Optional[str] = None
    content: str
    created_by: str
    status: str = "draft"


class ReportUpdate(BaseModel):
    """Model for updating report information."""

    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None
    reviewed_by: Optional[str] = None
    approved_by: Optional[str] = None
