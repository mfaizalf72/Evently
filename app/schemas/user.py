"""
User Schemas Module
Pydantic v2 data validation contracts for User and Authentication operations.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRole(str, Enum):
    """Supported user roles in Evently."""
    ORGANIZER = "organizer"
    CUSTOMER = "customer"
    ADMIN = "admin"


class UserBase(BaseModel):
    """Base user attributes."""
    email: EmailStr = Field(..., description="User's unique email address")
    full_name: str = Field(..., min_length=2, max_length=255, description="Full display name")
    role: UserRole = Field(default=UserRole.CUSTOMER, description="Role assigning system privileges")

    @field_validator("full_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Full name cannot be empty.")
        return v_stripped


class UserCreate(UserBase):
    """Schema for registering a new user."""
    password: str = Field(..., min_length=8, max_length=128, description="Plaintext password (min 8 characters)")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v


class UserLogin(BaseModel):
    """Schema for logging in."""
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password")


class UserResponse(UserBase):
    """Public user response schema omitting sensitive fields like password hashes."""
    id: uuid.UUID = Field(..., description="Unique user identifier")
    is_active: bool = Field(..., description="Whether user account is active")
    created_at: datetime = Field(..., description="Account creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last account update timestamp (UTC)")

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """Schema for updating user details."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
