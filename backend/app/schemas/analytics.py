# backend/app/schemas/analytics.py
"""
Analytics Pydantic schemas.
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class VehicleCountResponse(BaseModel):
    """Vehicle count per camera."""
    camera_id: str
    camera_name: Optional[str] = None
    location: Optional[str] = None
    vehicle_count: int


class HourlyDensityResponse(BaseModel):
    """Hourly density response."""
    hourly_data: List[Dict[str, Any]]
    hourly_totals: List[Dict[str, Any]]


class ODPatternResponse(BaseModel):
    """Origin-destination pattern."""
    route: str
    origin: str
    destination: str
    vehicle_count: int
    unique_vehicles: int
    average_travel_time_seconds: Optional[float] = None
    average_travel_time_minutes: Optional[float] = None


class CongestionHotspotResponse(BaseModel):
    """Congestion hotspot."""
    camera_id: str
    camera_name: Optional[str] = None
    location: Optional[str] = None
    vehicle_count: int
    is_hotspot: bool


class HeatmapDataResponse(BaseModel):
    """Heatmap data point."""
    latitude: float
    longitude: float
    intensity: int
