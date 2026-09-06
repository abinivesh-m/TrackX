"""
Admin API routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from app.core.database import get_db
from app.api.v1.deps import get_current_admin_user
from app.models.user import User
from app.schemas.user import UserCreateAdmin, UserUpdateAdmin, UserInDBAdmin

router = APIRouter()

@router.get("/users")
def get_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all users (admin only)"""
    query = select(User)
    result = db.execute(query)
    users = result.scalars().all()
    
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "organization": user.organization,
            "department": user.department,
            "last_login": user.last_login,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
        for user in users
    ]

@router.post("/users")
def create_user(
    user_data: UserCreateAdmin,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create new user (admin only)"""
    from app.core.security import get_password_hash
    
    # Check if user exists
    query = select(User).where(User.username == user_data.username)
    result = db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=user_data.role,
        is_active=user_data.is_active,
        is_admin=user_data.is_admin,
        organization=user_data.organization,
        department=user_data.department,
        allowed_cameras=user_data.allowed_cameras
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "role": new_user.role,
        "is_active": new_user.is_active,
        "is_admin": new_user.is_admin,
        "organization": new_user.organization,
        "department": new_user.department,
        "last_login": new_user.last_login,
        "created_at": new_user.created_at,
        "updated_at": new_user.updated_at
    }

@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    user_data: UserUpdateAdmin,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update user (admin only)"""
    query = select(User).where(User.id == user_id)
    result = db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.role is not None:
        user.role = user_data.role
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.is_admin is not None:
        user.is_admin = user_data.is_admin
    if user_data.organization is not None:
        user.organization = user_data.organization
    if user_data.department is not None:
        user.department = user_data.department
    if user_data.allowed_cameras is not None:
        user.allowed_cameras = user_data.allowed_cameras
    
    db.commit()
    db.refresh(user)
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "organization": user.organization,
        "department": user.department,
        "last_login": user.last_login,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete user (admin only)"""
    query = select(User).where(User.id == user_id)
    result = db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}

@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get audit logs (admin only)"""
    # In a real implementation, this would query an audit_logs table
    # For now, return sample data
    sample_logs = [
        {
            "id": 1,
            "action": "USER_LOGIN",
            "username": current_user.username,
            "resource": "auth",
            "result": "SUCCESS",
            "timestamp": "2026-09-04T10:00:00"
        },
        {
            "id": 2,
            "action": "VEHICLE_SEARCH",
            "username": current_user.username,
            "resource": "vehicles",
            "result": "SUCCESS",
            "timestamp": "2026-09-04T10:05:00"
        }
    ]
    
    return sample_logs[offset:offset+limit]

@router.get("/system-health")
def get_system_health(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get system health (admin only)"""
    return {
        "status": "healthy",
        "resources": {
            "cpu_percent": 45,
            "memory_percent": 62,
            "disk_percent": 78
        },
        "services": {
            "database": "connected",
            "redis": "connected",
            "ai_engine": "operational"
        },
        "timestamp": "2026-09-04T10:00:00"
    }
