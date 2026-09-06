# backend/app/services/alert_service.py
"""
Alert Service - generate, list, manage alerts.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.models.alert import Alert
from app.models.observation import Observation
from app.models.camera import Camera


class AlertService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_alert(
        self,
        alert_type: str,
        severity: str,
        plate_text: str,
        camera_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        description: Optional[str] = None,
        confidence: Optional[float] = None,
        similarity: Optional[float] = None,
        evidence: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """Create a new alert."""
        alert = Alert(
            alert_id=f"ALT-{uuid.uuid4().hex[:12].upper()}",
            alert_type=alert_type,
            severity=severity,
            plate_text=plate_text,
            normalized_plate=plate_text.replace(" ", "").upper(),
            camera_id=camera_id,
            timestamp=timestamp or datetime.now(timezone.utc),
            description=description,
            confidence=confidence,
            similarity=similarity,
            evidence_json=evidence or {},
            status="OPEN"
        )
        
        self.db.add(alert)
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def get_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        plate: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Alert]:
        """Get alerts with optional filters."""
        query = select(Alert)
        
        if status:
            query = query.where(Alert.status == status)
        if severity:
            query = query.where(Alert.severity == severity)
        if alert_type:
            query = query.where(Alert.alert_type == alert_type)
        if plate:
            normalized = plate.replace(" ", "").upper()
            query = query.where(Alert.normalized_plate == normalized)
        if start_time:
            query = query.where(Alert.timestamp >= start_time)
        if end_time:
            query = query.where(Alert.timestamp <= end_time)
        
        query = query.order_by(Alert.timestamp.desc()).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_alert_by_id(self, alert_id: str) -> Optional[Alert]:
        """Get a single alert by its ID."""
        query = select(Alert).where(Alert.alert_id == alert_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def resolve_alert(self, alert_id: str, resolved_by: str, notes: str = "") -> bool:
        """Resolve an alert."""
        alert = await self.get_alert_by_id(alert_id)
        if not alert:
            return False
        
        alert.status = "RESOLVED"
        alert.resolved_by = resolved_by
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolution_notes = notes
        
        await self.db.commit()
        return True

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        alert = await self.get_alert_by_id(alert_id)
        if not alert:
            return False
        
        alert.status = "ACKNOWLEDGED"
        await self.db.commit()
        return True

    async def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics for dashboard."""
        # Total alerts
        total_query = select(func.count(Alert.id))
        total_result = await self.db.execute(total_query)
        total = total_result.scalar()
        
        # Open alerts
        open_query = select(func.count(Alert.id)).where(Alert.status == "OPEN")
        open_result = await self.db.execute(open_query)
        open_count = open_result.scalar()
        
        # High severity
        high_query = select(func.count(Alert.id)).where(
            and_(Alert.severity == "HIGH", Alert.status == "OPEN")
        )
        high_result = await self.db.execute(high_query)
        high_count = high_result.scalar()
        
        # By type
        type_query = select(Alert.alert_type, func.count(Alert.id)).group_by(Alert.alert_type)
        type_result = await self.db.execute(type_query)
        by_type = {row.alert_type: row.count for row in type_result.all()}
        
        return {
            "total_alerts": total,
            "open_alerts": open_count,
            "high_severity_open": high_count,
            "alerts_by_type": by_type
        }

    async def generate_alerts_from_observations(
        self, observation: Observation
    ) -> List[Alert]:
        """
        Check a new observation against watchlist and generate alerts.
        This is called by the ingestion pipeline.
        """
        alerts = []
        
        # Check watchlist
        from app.models.vehicle import Vehicle
        normalized = observation.normalized_plate
        if normalized:
            vehicle_query = select(Vehicle).where(Vehicle.normalized_plate == normalized)
            vehicle_result = await self.db.execute(vehicle_query)
            vehicle = vehicle_result.scalar_one_or_none()
            
            if vehicle and vehicle.watchlist_status in ("BLOCKLISTED", "REVIEW"):
                alert = await self.create_alert(
                    alert_type="BLACKLIST_MATCH",
                    severity="HIGH" if vehicle.watchlist_status == "BLOCKLISTED" else "MEDIUM",
                    plate_text=observation.plate_text or normalized,
                    camera_id=observation.camera_id,
                    timestamp=observation.timestamp,
                    description=f"Vehicle matches watchlist entry: {vehicle.watchlist_reason or vehicle.watchlist_status}",
                    confidence=observation.confidence,
                    similarity=0.99,
                    evidence={
                        "observation_id": observation.id,
                        "annotated_output": observation.annotated_output,
                        "plate_crop_path": observation.plate_crop_path,
                        "source_file": observation.source_file
                    }
                )
                alerts.append(alert)
        
        return alerts
