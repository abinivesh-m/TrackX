# backend/app/schemas/user.py
"""
User management Pydantic schemas (admin).
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class UserCreateAdmin(BaseModel):
    """Admin user creation."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    role: str = Field("operator", pattern="^(operator|analyst|admin|viewer)$")
    is_active: bool = True
    is_admin: bool = False
    organization: Optional[str] = None
    department: Optional[str] = None
    allowed_cameras: List[str] = []


class UserUpdateAdmin(BaseModel):
    """Admin user update."""
    full_name: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(operator|analyst|admin|viewer)$")
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    organization: Optional[str] = None
    department: Optional[str] = None
    allowed_cameras: Optional[List[str]] = None


class UserInDBAdmin(BaseModel):
    """Admin user response."""
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: str
    is_active: bool
    is_admin: bool
    organization: Optional[str] = None
    department: Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
