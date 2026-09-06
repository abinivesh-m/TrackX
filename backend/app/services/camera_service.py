# backend/app/services/camera_service.py
"""
Camera Service - CRUD operations and GIS queries.

Supports both SQLite (basic distance calculations) and PostgreSQL+PostGIS (spatial queries).
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
import math

from app.models.camera import Camera, HAS_POSTGIS
from app.core.database import IS_POSTGIS
from app.schemas.camera import CameraCreate, CameraUpdate

# Conditionally import PostGIS functions
if HAS_POSTGIS:
    from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_GeogFromText


class CameraService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_cameras(self, active_only: bool = False) -> List[Camera]:
        """Get all cameras, optionally only active ones."""
        query = select(Camera)
        if active_only:
            query = query.where(Camera.is_active == True)  # noqa: E712
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_camera_by_id(self, camera_id: str) -> Optional[Camera]:
        """Get a camera by its camera_id."""
        query = select(Camera).where(Camera.camera_id == camera_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_camera(self, camera_data: CameraCreate) -> Camera:
        """Create a new camera."""
        camera = Camera(
            camera_id=camera_data.camera_id,
            name=camera_data.name,
            location=camera_data.location,
            latitude=camera_data.latitude,
            longitude=camera_data.longitude,
            direction=camera_data.direction,
            road=camera_data.road,
            camera_type=camera_data.camera_type,
            is_active=camera_data.is_active,
            metadata_json=camera_data.metadata,
        )
        self.db.add(camera)
        await self.db.commit()
        await self.db.refresh(camera)
        return camera

    async def update_camera(self, camera_id: str, camera_data: CameraUpdate) -> Optional[Camera]:
        """Update camera details."""
        camera = await self.get_camera_by_id(camera_id)
        if not camera:
            return None
        
        for key, value in camera_data.model_dump(exclude_unset=True).items():
            if key == "metadata":
                key = "metadata_json"
            setattr(camera, key, value)
        
        await self.db.commit()
        await self.db.refresh(camera)
        return camera

    async def deactivate_camera(self, camera_id: str) -> bool:
        """Deactivate a camera (soft delete)."""
        camera = await self.get_camera_by_id(camera_id)
        if not camera:
            return False
        camera.is_active = False
        await self.db.commit()
        return True

    async def get_cameras_within_radius(self, latitude: float, longitude: float, radius_km: float = 5) -> List[Camera]:
        """Get cameras within a specified radius."""
        
        if IS_POSTGIS and HAS_POSTGIS:
            # Use PostGIS spatial query for performance
            point = f"POINT({longitude} {latitude})"
            query = (
                select(Camera)
                .where(ST_DWithin(Camera.geom, ST_GeogFromText(point), radius_km * 1000))
                .order_by(ST_Distance(Camera.geom, ST_GeogFromText(point)))
            )
            result = await self.db.execute(query)
            return list(result.scalars().all())
        else:
            # Fallback to Haversine formula for SQLite
            all_cameras = await self.get_all_cameras(active_only=True)
            nearby_cameras = []
            
            for camera in all_cameras:
                distance = self._haversine_distance(
                    latitude, longitude,
                    camera.latitude, camera.longitude
                )
                if distance <= radius_km:
                    camera.distance = distance  # Add distance as temporary attribute
                    nearby_cameras.append(camera)
            
            # Sort by distance
            nearby_cameras.sort(key=lambda c: getattr(c, 'distance', float('inf')))
            return nearby_cameras

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.
        Returns distance in kilometers.
        """
        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Radius of Earth in kilometers
        r = 6371
        return c * r

    async def get_camera_health(self, camera_id: str) -> Dict[str, Any]:
        """Get health metrics for a camera."""
        camera = await self.get_camera_by_id(camera_id)
        if not camera:
            return {"error": "Camera not found"}
        
        # Query observation count
        from app.models.observation import Observation
        obs_count_query = select(func.count(Observation.id)).where(Observation.camera_id == camera_id)
        obs_count_result = await self.db.execute(obs_count_query)
        obs_count = obs_count_result.scalar()
        
        # Get last observation timestamp
        last_obs_query = (
            select(func.max(Observation.timestamp))
            .where(Observation.camera_id == camera_id)
        )
        last_obs_result = await self.db.execute(last_obs_query)
        last_obs = last_obs_result.scalar()
        
        # Calculate uptime/health status
        if last_obs:
            time_since_last = (datetime.now(timezone.utc) - last_obs.replace(tzinfo=timezone.utc)).total_seconds()
            if time_since_last < 60:
                status = "ONLINE"
            elif time_since_last < 300:
                status = "DEGRADED"
            else:
                status = "OFFLINE"
        else:
            status = "NO_DATA"
        
        return {
            "camera_id": camera.camera_id,
            "camera_name": camera.name,
            "location": camera.location,
            "is_active": camera.is_active,
            "last_seen": camera.last_seen,
            "observation_count": obs_count,
            "status": status
        }
