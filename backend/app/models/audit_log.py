# backend/app/models/audit_log.py
"""
Audit Log model - for government-grade compliance.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func, JSON

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(String(50), unique=True, index=True)
    
    # Actor
    user_id = Column(Integer, index=True)
    username = Column(String(50), index=True)
    user_role = Column(String(20))
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    
    # Action
    action = Column(String(50), index=True)  # CREATE, READ, UPDATE, DELETE, LOGIN, SEARCH
    resource = Column(String(100))
    resource_id = Column(String(50))
    details = Column(JSON, default={})
    result = Column(String(20), default="SUCCESS")  # SUCCESS, FAILURE, DENIED
    
    # Timestamp
    timestamp = Column(DateTime, default=func.now(), index=True)
    
    # Additional Context
    request_id = Column(String(50))
    session_id = Column(String(50))

    def __repr__(self):
        return f"<AuditLog(id={self.log_id}, action={self.action}, user={self.username})>"
