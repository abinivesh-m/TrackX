# backend/app/services/audit_service.py
"""
Audit Service - for government-grade compliance logging.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.models.audit_log import AuditLog


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_audit_log(
        self,
        user_id: int,
        username: str,
        user_role: str,
        action: str,
        resource: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        result: str = "SUCCESS",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AuditLog:
        """Create a new audit log entry."""
        audit_log = AuditLog(
            log_id=f"AUD-{uuid.uuid4().hex[:12].upper()}",
            user_id=user_id,
            username=username,
            user_role=user_role,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details or {},
            result=result,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc)
        )
        
        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)
        return audit_log

    async def get_audit_logs(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        result: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """Get audit logs with optional filters."""
        query = select(AuditLog)
        
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if username:
            query = query.where(AuditLog.username == username)
        if action:
            query = query.where(AuditLog.action == action)
        if resource:
            query = query.where(AuditLog.resource == resource)
        if result:
            query = query.where(AuditLog.result == result)
        if start_time:
            query = query.where(AuditLog.timestamp >= start_time)
        if end_time:
            query = query.where(AuditLog.timestamp <= end_time)
        
        query = query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_audit_stats(self) -> Dict[str, Any]:
        """Get audit statistics for dashboard."""
        # Total logs
        total_query = select(func.count(AuditLog.id))
        total_result = await self.db.execute(total_query)
        total = total_result.scalar()
        
        # By action
        action_query = select(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action)
        action_result = await self.db.execute(action_query)
        by_action = {row.action: row.count for row in action_result.all()}
        
        # By result
        result_query = select(AuditLog.result, func.count(AuditLog.id)).group_by(AuditLog.result)
        result_result = await self.db.execute(result_query)
        by_result = {row.result: row.count for row in result_result.all()}
        
        return {
            "total_logs": total,
            "logs_by_action": by_action,
            "logs_by_result": by_result
        }
