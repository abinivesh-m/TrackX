# backend/app/schemas/vehicle.py
"""
Pydantic schemas for Vehicle and Trajectory.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class VehicleBase(BaseModel):
    plate_number: str = Field(..., max_length=30)
    state_code: Optional[str] = None
    rto_code: Optional[int] = None
    vehicle_type: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_color: Optional[str] = None


class VehicleCreate(VehicleBase):
    watchlist_status: str = "CLEAR"
    watchlist_reason: Optional[str] = None


class VehicleUpdate(BaseModel):
    vehicle_type: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_color: Optional[str] = None
    watchlist_status: Optional[str] = None
    watchlist_reason: Optional[str] = None
    owner_name: Optional[str] = None
    owner_address: Optional[str] = None
    owner_phone: Optional[str] = None
    insurance_expiry: Optional[datetime] = None
    puc_expiry: Optional[datetime] = None


class VehicleInDB(VehicleBase):
    id: int
    normalized_plate: str
    registration_status: str
    watchlist_status: str
    watchlist_reason: Optional[str] = None
    owner_name: Optional[str] = None
    owner_address: Optional[str] = None
    owner_phone: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ObservationPoint(BaseModel):
    """A single observation along a vehicle's trajectory."""
    observation_id: int
    camera_id: str
    camera_name: str
    location: str
    latitude: float
    longitude: float
    timestamp: datetime
    plate_text: str
    confidence: float
    vehicle_type: str
    vehicle_bbox: List[int]
    plate_bbox: Optional[List[int]] = None
    annotated_output: Optional[str] = None
    plate_crop_path: Optional[str] = None
    match_score: Optional[float] = None


class TrajectoryResponse(BaseModel):
    """Complete trajectory for a searched vehicle."""
    plate_text: str
    vehicle_found: bool = True
    observation_count: int
    camera_count: int
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    total_journey_time: Optional[str] = None
    average_speed: Optional[float] = None
    route_path: str
    trajectory_points: List[ObservationPoint]
    watchlist_status: str = "CLEAR"
    risk_level: str = "NORMAL"


class VehicleSearchResponse(BaseModel):
    """Search results for vehicle query."""
    vehicles: List[VehicleInDB]
    total_count: int
    has_trajectory: bool
    trajectory: Optional[TrajectoryResponse] = None
