"""
Pydantic schemas for Authentication and Authorization DTOs in UNDOX.
Uses Pydantic v2 conventions.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    """Supported authorization roles."""
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class UserRegisterRequest(BaseModel):
    """Payload to register a new user account."""
    username: str = Field(..., min_length=3, max_length=64, description="Unique username")
    email: str = Field(
        ...,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Valid unique email address",
    )
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")
    role: Optional[UserRole] = Field(default=UserRole.VIEWER, description="Assigned role")


class UserLoginRequest(BaseModel):
    """Payload to authenticate with username and password."""
    username: str = Field(..., description="User's username")
    password: str = Field(..., description="User's password")


class TokenResponse(BaseModel):
    """Response containing JWT access token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiry duration in seconds")
    user_id: UUID
    username: str
    role: str


class UserResponse(BaseModel):
    """User profile response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
