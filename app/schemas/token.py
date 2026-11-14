"""
Token Schemas Module
Pydantic contracts for JWT authentication responses and token payloads.
"""

from typing import Optional
from pydantic import BaseModel, Field


class Token(BaseModel):
    """Schema returned upon successful authentication containing JWT tokens."""
    access_token: str = Field(..., description="Signed JWT access token")
    refresh_token: str = Field(..., description="Signed JWT refresh token")
    token_type: str = Field(default="bearer", description="Token scheme (Bearer)")
    expires_in: int = Field(..., description="Access token expiration period in seconds")


class TokenPayload(BaseModel):
    """Internal decoded JWT claims payload."""
    sub: str = Field(..., description="Subject identifier (user UUID)")
    role: str = Field(..., description="User role at the time of token issuance")
    type: str = Field(..., description="Token type (access or refresh)")
    exp: int = Field(..., description="Expiration epoch timestamp")
    iat: Optional[int] = Field(None, description="Issued-at epoch timestamp")


class RefreshTokenRequest(BaseModel):
    """Request payload to obtain a new access token."""
    refresh_token: str = Field(..., description="Valid unexpired refresh token")
