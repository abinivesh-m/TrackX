"""Road network model for camera connectivity."""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from backend.app.core.database import Base


class RoadNetwork(Base):
    """Represents a road connection between two cameras."""
    __tablename__ = "road_network"
    __table_args__ = (
        UniqueConstraint('camera_a', 'camera_b', name='uq_road_connection'),
        Index('ix_road_network_camera_a', 'camera_a'),
        Index('ix_road_network_camera_b', 'camera_b'),
    )

    id = Column(Integer, primary_key=True, index=True)
    camera_a = Column(String, nullable=False)
    camera_b = Column(String, nullable=False)
    distance_km = Column(Float, nullable=False)
    speed_limit_kmph = Column(Integer, nullable=False)
    road_type = Column(String, nullable=True)  # "arterial", "highway", "urban", etc.
    traffic_condition = Column(String, nullable=True)  # "light", "moderate", "heavy"
    lanes = Column(Integer, nullable=True)
    has_traffic_lights = Column(Boolean, nullable=True)
    typical_travel_time_min = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        """Convert to dict for API responses."""
        return {
            'id': self.id,
            'camera_a': self.camera_a,
            'camera_b': self.camera_b,
            'distance_km': self.distance_km,
            'speed_limit_kmph': self.speed_limit_kmph,
            'road_type': self.road_type,
            'traffic_condition': self.traffic_condition,
            'lanes': self.lanes,
            'has_traffic_lights': self.has_traffic_lights,
            'typical_travel_time_min': self.typical_travel_time_min,
        }
