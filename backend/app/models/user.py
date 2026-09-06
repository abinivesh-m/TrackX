# backend/app/models/user.py
"""
User model for authentication and RBAC.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, JSON

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    
    # Roles
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    role = Column(String(20), default="operator")  # operator, analyst, admin, viewer
    
    # Organization
    organization = Column(String(100))
    department = Column(String(100))
    
    # Access Control
    permissions = Column(JSON, default={})
    allowed_cameras = Column(JSON, default=[])  # Empty = all cameras
    
    # Security
    last_login = Column(DateTime)
    failed_login_attempts = Column(Integer, default=0)
    password_changed_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"
