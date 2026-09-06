# backend/app/schemas/alert.py
"""
Alert Pydantic schemas.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any
from datetime import datetime


class AlertBase(BaseModel):
    """Base alert schema."""
    alert_type: str
    severity: str = Field("MEDIUM", pattern="^(LOW|MEDIUM|HIGH)$")
    plate_text: str
    camera_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    description: Optional[str] = None
    confidence: Optional[float] = None
    similarity: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = None


class AlertCreate(AlertBase):
    """Alert creation request."""
    pass


class AlertUpdate(BaseModel):
    """Alert update request."""
    status: Optional[str] = Field(None, pattern="^(OPEN|ACKNOWLEDGED|RESOLVED)$")
    resolution_notes: Optional[str] = None
    resolved_by: Optional[str] = None


class AlertResponse(AlertBase):
    """Alert response."""
    id: int
    alert_id: str
    normalized_plate: str
    status: str
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
