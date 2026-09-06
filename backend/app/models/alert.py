# backend/app/models/alert.py
"""
Alert model - stores all generated alerts.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func, JSON

from app.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(50), unique=True, index=True)
    
    # Alert Type & Details
    alert_type = Column(String(50), index=True)  # BLACKLIST_MATCH, IMPOSSIBLE_TRAVEL, ROUTE_ANOMALY, REPEATED_CAMERA
    severity = Column(String(20), index=True)  # HIGH, MEDIUM, LOW
    
    # Vehicle Information
    plate_text = Column(String(30), index=True)
    normalized_plate = Column(String(30), index=True)
    vehicle_type = Column(String(30))
    
    # Camera & Evidence
    camera_id = Column(String(20))
    timestamp = Column(DateTime, index=True)
    evidence_json = Column(JSON)  # Paths to evidence frames, observation IDs
    
    # Alert Details
    description = Column(String(1000))
    confidence = Column(Float)
    similarity = Column(Float)
    
    # Resolution
    status = Column(String(20), default="OPEN", index=True)  # OPEN, ACKNOWLEDGED, RESOLVED
    resolved_by = Column(String(100))
    resolved_at = Column(DateTime)
    resolution_notes = Column(String(1000))
    
    # Metadata
    metadata_json = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Alert(id={self.alert_id}, type={self.alert_type}, severity={self.severity})>"
