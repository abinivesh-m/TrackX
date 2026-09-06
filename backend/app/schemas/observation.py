# backend/app/schemas/observation.py
"""
Observation Pydantic schemas.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ObservationBase(BaseModel):
    """Base observation schema."""
    plate_text: Optional[str] = None
    normalized_plate: Optional[str] = None
    camera_id: str
    timestamp: datetime
    vehicle_type: Optional[str] = None
    confidence: Optional[float] = None
    vehicle_bbox: Optional[List[int]] = None
    plate_bbox: Optional[List[int]] = None
    source_file: Optional[str] = None
    frame_index: Optional[int] = None


class ObservationCreate(ObservationBase):
    """Observation creation request."""
    pass


class ObservationResponse(ObservationBase):
    """Observation response."""
    id: int
    raw_plate_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    plate_status: Optional[str] = None
    vehicle_confidence: Optional[float] = None
    plate_confidence: Optional[float] = None
    data_source: Optional[str] = None
    track_id: Optional[str] = None
    global_id: Optional[int] = None
    match_score: Optional[float] = None
    annotated_output: Optional[str] = None
    plate_crop_path: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ObservationListResponse(BaseModel):
    """List of observations response."""
    total: int
    items: List[ObservationResponse]
