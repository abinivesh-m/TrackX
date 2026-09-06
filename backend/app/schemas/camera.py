# backend/app/schemas/camera.py
"""
Pydantic schemas for Camera.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class CameraBase(BaseModel):
    camera_id: str = Field(..., max_length=20)
    name: str = Field(..., max_length=100)
    location: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    direction: Optional[str] = None
    road: Optional[str] = None
    camera_type: str = "CCTV"
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    direction: Optional[str] = None
    road: Optional[str] = None
    camera_type: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class CameraInDB(CameraBase):
    id: int
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CameraResponse(CameraInDB):
    """Camera response with computed properties."""
    observation_count: Optional[int] = None
    recent_observations: Optional[list] = None
    distance_to_user: Optional[float] = None
