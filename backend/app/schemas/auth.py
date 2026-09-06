# backend/app/schemas/auth.py
"""
Authentication Pydantic schemas.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    """Token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Login request."""
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class UserCreate(BaseModel):
    """User creation request."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    role: str = Field("operator", pattern="^(operator|analyst|admin|viewer)$")
    organization: Optional[str] = None
    department: Optional[str] = None


class UserInDB(BaseModel):
    """User response."""
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    is_admin: bool
    role: str
    organization: Optional[str] = None
    department: Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PasswordChange(BaseModel):
    """Password change request."""
    username: str
    old_password: str
    new_password: str = Field(..., min_length=8)
