# backend/app/models/vehicle.py
"""
Vehicle Registry model.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func, JSON

from app.core.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String(30), unique=True, index=True, nullable=False)
    normalized_plate = Column(String(30), unique=True, index=True, nullable=False)
    state_code = Column(String(2))
    rto_code = Column(Integer)
    
    # Vehicle Attributes
    vehicle_type = Column(String(30))
    vehicle_make = Column(String(50))
    vehicle_model = Column(String(50))
    vehicle_color = Column(String(30))
    fuel_type = Column(String(20))
    registration_status = Column(String(20), default="VALID")
    
    # Watchlist
    watchlist_status = Column(String(20), default="CLEAR")
    watchlist_reason = Column(String(500))
    
    # Owner Information
    owner_name = Column(String(100))
    owner_address = Column(String(500))
    owner_phone = Column(String(20))
    
    # Insurance & Compliance
    insurance_expiry = Column(DateTime)
    puc_expiry = Column(DateTime)
    fitness_expiry = Column(DateTime)
    
    # Appearance Signature (aggregated from observations)
    typical_appearance = Column(JSON, default={})
    
    # Source
    data_source = Column(String(30), default="MANUAL")
    source_agency = Column(String(100))
    
    # Timestamps
    first_seen = Column(DateTime)
    last_seen = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Metadata
    metadata_json = Column("metadata", JSON, default=dict)

    def __repr__(self):
        return f"<Vehicle(id={self.id}, plate={self.plate_number})>"
