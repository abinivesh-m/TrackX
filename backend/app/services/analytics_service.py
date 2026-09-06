# backend/app/services/analytics_service.py
"""
Analytics Service - traffic density, OD patterns, congestion, speed.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observation import Observation
from app.models.camera import Camera
from app.models.vehicle import Vehicle


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_vehicle_counts_per_camera(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get vehicle counts for each camera."""
        query = (
            select(Observation.camera_id, func.count(Observation.id).label("count"))
            .group_by(Observation.camera_id)
        )
        
        if start_time:
            query = query.where(Observation.timestamp >= start_time)
        if end_time:
            query = query.where(Observation.timestamp <= end_time)
        
        result = await self.db.execute(query)
        counts = result.all()
        
        # Include camera names
        camera_query = select(Camera.camera_id, Camera.name, Camera.location)
        camera_result = await self.db.execute(camera_query)
        cameras = {row.camera_id: row for row in camera_result.all()}
        
        return [
            {
                "camera_id": row.camera_id,
                "camera_name": cameras.get(row.camera_id).name if row.camera_id in cameras else row.camera_id,
                "location": cameras.get(row.camera_id).location if row.camera_id in cameras else "Unknown",
                "vehicle_count": row.count
            }
            for row in counts
        ]

    async def get_hourly_density(
        self, camera_id: Optional[str] = None, hours: int = 24
    ) -> Dict[str, Any]:
        """Get hourly vehicle density for a camera or all cameras."""
        end_time = datetime.now(tz=timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        
        # Use date_trunc to group by hour
        from sqlalchemy import cast, Date, Time
        hour_expr = func.date_trunc('hour', Observation.timestamp)
        
        query = (
            select(
                hour_expr.label("hour"),
                Observation.camera_id,
                func.count(Observation.id).label("count")
            )
            .where(Observation.timestamp.between(start_time, end_time))
            .group_by(hour_expr, Observation.camera_id)
            .order_by(hour_expr)
        )
        
        if camera_id:
            query = query.where(Observation.camera_id == camera_id)
        
        result = await self.db.execute(query)
        
        # Reformat for frontend
        data = []
        for row in result.all():
            data.append({
                "hour": row.hour.strftime("%Y-%m-%d %H:00"),
                "camera_id": row.camera_id,
                "count": row.count
            })
        
        # Also compute total per hour
        totals = {}
        for item in data:
            hour = item["hour"]
            if hour not in totals:
                totals[hour] = 0
            totals[hour] += item["count"]
        
        return {
            "hourly_data": data,
            "hourly_totals": [{"hour": h, "count": c} for h, c in sorted(totals.items())]
        }

    async def get_origin_destination_patterns(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get origin-destination patterns by tracking vehicles across cameras."""
        # Get observations grouped by normalized_plate
        query = select(
            Observation.normalized_plate,
            Observation.camera_id,
            Observation.timestamp
        )
        
        if start_time:
            query = query.where(Observation.timestamp >= start_time)
        if end_time:
            query = query.where(Observation.timestamp <= end_time)
        
        result = await self.db.execute(query)
        observations = result.all()
        
        # Group by plate
        vehicle_sequences = {}
        for obs in observations:
            plate = obs.normalized_plate
            if not plate:
                continue
            if plate not in vehicle_sequences:
                vehicle_sequences[plate] = []
            vehicle_sequences[plate].append({
                "camera_id": obs.camera_id,
                "timestamp": obs.timestamp
            })
        
        # Build OD pairs
        od_pairs = {}
        for plate, seq in vehicle_sequences.items():
            # Sort by timestamp
            seq.sort(key=lambda x: x["timestamp"])
            
            # For each consecutive camera transition
            for i in range(len(seq) - 1):
                if seq[i]["camera_id"] == seq[i+1]["camera_id"]:
                    continue
                
                origin = seq[i]["camera_id"]
                dest = seq[i+1]["camera_id"]
                pair = f"{origin} -> {dest}"
                
                if pair not in od_pairs:
                    od_pairs[pair] = {
                        "origin": origin,
                        "destination": dest,
                        "count": 0,
                        "vehicles": set(),
                        "avg_travel_time": []
                    }
                
                od_pairs[pair]["count"] += 1
                od_pairs[pair]["vehicles"].add(plate)
                
                # Calculate travel time
                travel_time = (seq[i+1]["timestamp"] - seq[i]["timestamp"]).total_seconds()
                if 0 < travel_time < 3600:  # Ignore unrealistic times
                    od_pairs[pair]["avg_travel_time"].append(travel_time)
        
        # Format output
        output = []
        for pair, data in od_pairs.items():
            avg_time = sum(data["avg_travel_time"]) / len(data["avg_travel_time"]) if data["avg_travel_time"] else None
            output.append({
                "route": pair,
                "origin": data["origin"],
                "destination": data["destination"],
                "vehicle_count": data["count"],
                "unique_vehicles": len(data["vehicles"]),
                "average_travel_time_seconds": avg_time,
                "average_travel_time_minutes": round(avg_time / 60, 1) if avg_time else None
            })
        
        output.sort(key=lambda x: x["vehicle_count"], reverse=True)
        return output

    async def get_congestion_hotspots(
        self, threshold_percentile: float = 75.0
    ) -> List[Dict[str, Any]]:
        """Identify congested cameras based on vehicle counts."""
        counts = await self.get_vehicle_counts_per_camera()
        
        if not counts:
            return []
        
        # Calculate percentile threshold
        values = [c["vehicle_count"] for c in counts]
        values.sort()
        index = int(len(values) * threshold_percentile / 100)
        threshold = values[min(index, len(values) - 1)]
        
        hotspots = [
            {**c, "is_hotspot": c["vehicle_count"] >= threshold}
            for c in counts
        ]
        
        return hotspots

    async def get_traffic_heatmap_data(self) -> List[Dict[str, float]]:
        """Get data for traffic heatmap visualization."""
        counts = await self.get_vehicle_counts_per_camera()
        
        # Include camera coordinates
        heatmap_data = []
        for c in counts:
            cam_query = select(Camera).where(Camera.camera_id == c["camera_id"])
            cam_result = await self.db.execute(cam_query)
            cam = cam_result.scalar_one_or_none()
            
            if cam:
                heatmap_data.append({
                    "latitude": cam.latitude,
                    "longitude": cam.longitude,
                    "intensity": c["vehicle_count"]
                })
        
        return heatmap_data
