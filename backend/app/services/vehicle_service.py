# backend/app/services/vehicle_service.py
"""
Vehicle Service - search, trajectory reconstruction, and registry management.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vehicle import Vehicle
from app.models.observation import Observation
from app.models.camera import Camera
from app.models.alert import Alert
from app.schemas.vehicle import (
    VehicleCreate, VehicleUpdate, VehicleInDB,
    TrajectoryResponse, ObservationPoint, VehicleSearchResponse
)


class VehicleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_vehicle(
        self,
        plate: str,
        camera_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        include_trajectory: bool = True
    ) -> Dict[str, Any]:
        """
        Search for a vehicle by plate number with optional filters.
        Returns vehicle info + trajectory if found.
        """
        # Normalize plate for searching
        normalized = plate.replace(" ", "").upper()
        
        # 1. Get vehicle from registry
        vehicle_query = select(Vehicle).where(
            or_(
                Vehicle.normalized_plate == normalized,
                Vehicle.plate_number == plate,
                Vehicle.plate_number.ilike(f"%{plate}%")
            )
        )
        vehicle_result = await self.db.execute(vehicle_query)
        vehicle = vehicle_result.scalar_one_or_none()
        
        # 2. Get observations for this vehicle
        obs_query = select(Observation).where(
            or_(
                Observation.normalized_plate == normalized,
                Observation.plate_text == plate,
                Observation.plate_text.ilike(f"%{plate}%")
            )
        )
        
        # Apply filters
        if camera_id:
            obs_query = obs_query.where(Observation.camera_id == camera_id)
        if start_time:
            obs_query = obs_query.where(Observation.timestamp >= start_time)
        if end_time:
            obs_query = obs_query.where(Observation.timestamp <= end_time)
        
        obs_query = obs_query.order_by(Observation.timestamp.asc())
        obs_result = await self.db.execute(obs_query)
        observations = list(obs_result.scalars().all())
        
        # 3. Build response
        if not observations:
            return {
                "vehicle_found": vehicle is not None,
                "observations": [],
                "trajectory": None,
                "message": "No observations found for this vehicle"
            }
        
        # Build trajectory
        trajectory = await self._build_trajectory(observations, normalized)
        
        return {
            "vehicle_found": True,
            "vehicle": VehicleInDB.model_validate(vehicle) if vehicle else None,
            "observations": [
                self._obs_to_dict(o) for o in observations
            ],
            "trajectory": trajectory
        }
    
    async def _build_trajectory(
        self, observations: List[Observation], plate: str
    ) -> TrajectoryResponse:
        """Build a complete trajectory from a list of observations."""
        # Group observations by camera
        camera_hits = {}
        for obs in observations:
            if obs.camera_id not in camera_hits:
                camera_hits[obs.camera_id] = []
            camera_hits[obs.camera_id].append(obs)
        
        # Build trajectory points (one per camera hit, pick highest confidence)
        trajectory_points = []
        for camera_id, cam_obs in camera_hits.items():
            # Get camera info
            cam_query = select(Camera).where(Camera.camera_id == camera_id)
            cam_result = await self.db.execute(cam_query)
            cam = cam_result.scalar_one_or_none()
            
            # Pick best observation (highest confidence)
            best_obs = max(cam_obs, key=lambda o: o.confidence or 0)
            
            trajectory_points.append(
                ObservationPoint(
                    observation_id=best_obs.id,
                    camera_id=camera_id,
                    camera_name=cam.name if cam else camera_id,
                    location=cam.location if cam else "Unknown",
                    latitude=cam.latitude if cam else 0,
                    longitude=cam.longitude if cam else 0,
                    timestamp=best_obs.timestamp,
                    plate_text=best_obs.plate_text or best_obs.normalized_plate or plate,
                    confidence=best_obs.confidence or 0,
                    vehicle_type=best_obs.vehicle_type or "Unknown",
                    vehicle_bbox=best_obs.vehicle_bbox or [0,0,0,0],
                    plate_bbox=best_obs.plate_bbox,
                    annotated_output=best_obs.annotated_output,
                    plate_crop_path=best_obs.plate_crop_path,
                    match_score=best_obs.match_score
                )
            )
        
        # Sort by timestamp
        trajectory_points.sort(key=lambda p: p.timestamp)
        
        # Calculate summary stats
        first_seen = trajectory_points[0].timestamp
        last_seen = trajectory_points[-1].timestamp
        total_journey = last_seen - first_seen
        
        # Calculate route path
        route_path = " -> ".join([p.camera_id for p in trajectory_points])
        
        # Calculate average speed (if multiple cameras)
        avg_speed = None
        if len(trajectory_points) >= 2:
            total_distance = 0
            for i in range(len(trajectory_points) - 1):
                p1 = trajectory_points[i]
                p2 = trajectory_points[i + 1]
                # Use haversine formula
                import math
                lat1, lon1 = p1.latitude, p1.longitude
                lat2, lon2 = p2.latitude, p2.longitude
                R = 6371  # Earth's radius in km
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                distance = R * c
                total_distance += distance
            
            if total_journey.total_seconds() > 0:
                avg_speed = (total_distance / (total_journey.total_seconds() / 3600))
        
        # Check watchlist status
        watchlist = "CLEAR"
        risk = "NORMAL"
        if trajectory_points:
            alert_query = select(Alert).where(
                Alert.normalized_plate == plate,
                Alert.status == "OPEN"
            ).order_by(Alert.created_at.desc())
            alert_result = await self.db.execute(alert_query)
            alerts = list(alert_result.scalars().all())
            if alerts:
                if any(a.severity == "HIGH" for a in alerts):
                    watchlist = "BLACKLISTED"
                    risk = "HIGH"
                else:
                    watchlist = "REVIEW"
                    risk = "MEDIUM"
        
        return TrajectoryResponse(
            plate_text=plate,
            vehicle_found=True,
            observation_count=len(observations),
            camera_count=len(camera_hits),
            first_seen=first_seen,
            last_seen=last_seen,
            total_journey_time=str(total_journey),
            average_speed=round(avg_speed, 2) if avg_speed else None,
            route_path=route_path,
            trajectory_points=trajectory_points,
            watchlist_status=watchlist,
            risk_level=risk
        )
    
    def _obs_to_dict(self, obs: Observation) -> Dict[str, Any]:
        """Convert observation to dict."""
        return {
            "id": obs.id,
            "plate_text": obs.plate_text,
            "normalized_plate": obs.normalized_plate,
            "raw_plate_text": obs.raw_plate_text,
            "camera_id": obs.camera_id,
            "timestamp": obs.timestamp,
            "confidence": obs.confidence,
            "vehicle_type": obs.vehicle_type,
            "vehicle_bbox": obs.vehicle_bbox,
            "plate_bbox": obs.plate_bbox,
            "ocr_confidence": obs.ocr_confidence,
            "annotated_output": obs.annotated_output,
            "plate_crop_path": obs.plate_crop_path,
            "source_file": obs.source_file,
            "frame_index": obs.frame_index,
        }
    
    async def get_vehicle_registry(self, plate: str) -> Optional[Vehicle]:
        """Get vehicle from registry."""
        normalized = plate.replace(" ", "").upper()
        query = select(Vehicle).where(Vehicle.normalized_plate == normalized)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def add_to_watchlist(self, plate: str, severity: str = "MEDIUM", reason: str = "") -> Vehicle:
        """Add vehicle to watchlist/blacklist."""
        vehicle = await self.get_vehicle_registry(plate)
        if not vehicle:
            vehicle = Vehicle(
                plate_number=plate,
                normalized_plate=plate.replace(" ", "").upper(),
                watchlist_status="REVIEW"
            )
            self.db.add(vehicle)
        
        if severity == "HIGH":
            vehicle.watchlist_status = "BLOCKLISTED"
        else:
            vehicle.watchlist_status = "REVIEW"
        vehicle.watchlist_reason = reason
        
        await self.db.commit()
        await self.db.refresh(vehicle)
        return vehicle
    
    async def remove_from_watchlist(self, plate: str) -> bool:
        """Remove vehicle from watchlist."""
        vehicle = await self.get_vehicle_registry(plate)
        if not vehicle:
            return False
        vehicle.watchlist_status = "CLEAR"
        vehicle.watchlist_reason = None
        await self.db.commit()
        return True
