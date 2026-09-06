# backend/app/models/observation.py
"""
Observation model - stores every vehicle detection event.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, func, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class Observation(Base):
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, index=True)
    
    # Vehicle Identification
    plate_text = Column(String(30), index=True)
    normalized_plate = Column(String(30), index=True)
    raw_plate_text = Column(String(30))
    ocr_confidence = Column(Float)
    plate_status = Column(String(30), default="detected")
    
    # Vehicle Properties
    vehicle_type = Column(String(30))
    vehicle_color = Column(String(30))
    vehicle_make = Column(String(50))
    vehicle_model = Column(String(50))
    appearance_vector = Column(JSON)  # Re-ID embedding
    
    # Detection Metadata
    camera_id = Column(String(20), ForeignKey("cameras.camera_id"), index=True)
    timestamp = Column(DateTime, index=True)
    confidence = Column(Float)
    vehicle_bbox = Column(JSON)  # [x1, y1, x2, y2]
    vehicle_confidence = Column(Float)
    plate_bbox = Column(JSON)  # [x1, y1, x2, y2]
    plate_confidence = Column(Float)
    
    # Source Information
    source_file = Column(String(500))
    source_type = Column(String(20))  # "image", "video", "rtsp"
    frame_index = Column(Integer)
    data_source = Column(String(30), default="REAL_INFERENCE")  # REAL_INFERENCE or SYNTHETIC_DEMO
    
    # Track & Fusion
    track_id = Column(String(50), index=True)
    global_id = Column(Integer, index=True)  # Assigned by trajectory engine
    match_score = Column(Float)
    match_breakdown = Column(JSON)
    
    # Evidence
    annotated_output = Column(String(500))
    plate_crop_path = Column(String(500))
    evidence_thumbnail = Column(String(500))
    
    # Metadata
    metadata_json = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    camera = relationship("Camera", back_populates="observations")

    def __repr__(self):
        return f"<Observation(id={self.id}, plate={self.normalized_plate}, camera={self.camera_id})>"
