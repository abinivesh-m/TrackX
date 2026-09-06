# backend/app/models/camera.py
"""
Camera model with PostGIS geometry support.

Supports both SQLite (lat/long columns) and PostgreSQL+PostGIS (geometry column).
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base, IS_POSTGIS

# Conditionally import PostGIS types
if IS_POSTGIS:
    from geoalchemy2 import Geometry
    HAS_POSTGIS = True
else:
    HAS_POSTGIS = False
    # Create a dummy Geometry class for SQLite compatibility
    class Geometry:
        def __init__(self, *args, **kwargs):
            pass


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    location = Column(String(200))
    latitude = Column(Float, nullable=False)  # Always stored for compatibility
    longitude = Column(Float, nullable=False)  # Always stored for compatibility
    
    # PostGIS geometry column (only used in PostgreSQL+PostGIS)
    if HAS_POSTGIS:
        geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    
    direction = Column(String(50))
    road = Column(String(100))
    camera_type = Column(String(50), default="CCTV")
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=func.now())
    metadata_json = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    observations = relationship("Observation", back_populates="camera")

    def __repr__(self):
        return f"<Camera(camera_id={self.camera_id}, name={self.name})>"
    
    def to_dict(self):
        """Convert camera to dictionary for API responses."""
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "name": self.name,
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "direction": self.direction,
            "road": self.road,
            "camera_type": self.camera_type,
            "is_active": self.is_active,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "metadata": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
