"""Pydantic schemas for road network endpoints."""

from typing import Optional
from pydantic import BaseModel, Field


class RoadNetworkCreate(BaseModel):
    """Schema for creating a road network connection."""
    camera_a: str = Field(..., description="First camera ID")
    camera_b: str = Field(..., description="Second camera ID")
    distance_km: float = Field(..., gt=0, description="Distance in kilometers")
    speed_limit_kmph: int = Field(..., gt=0, description="Speed limit in km/h")
    road_type: Optional[str] = Field(None, description="Type of road (arterial, highway, urban, etc.)")
    traffic_condition: Optional[str] = Field(None, description="Typical traffic condition (light, moderate, heavy)")
    lanes: Optional[int] = Field(None, description="Number of lanes")
    has_traffic_lights: Optional[bool] = Field(None, description="Whether road has traffic lights")
    typical_travel_time_min: Optional[float] = Field(None, description="Typical travel time in minutes")


class RoadNetworkResponse(RoadNetworkCreate):
    """Response schema for road network connections."""
    id: int


class RoadNetworkUpdate(BaseModel):
    """Schema for updating a road network connection."""
    distance_km: Optional[float] = Field(None, gt=0)
    speed_limit_kmph: Optional[int] = Field(None, gt=0)
    road_type: Optional[str] = None
    traffic_condition: Optional[str] = None
    lanes: Optional[int] = None
    has_traffic_lights: Optional[bool] = None
    typical_travel_time_min: Optional[float] = None
