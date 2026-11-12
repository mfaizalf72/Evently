"""
Health Check Schemas
Data contracts for application health and status monitoring.
"""

from datetime import datetime, timezone
from typing import Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall system status (e.g. ok, degraded)")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Active environment name")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the health check",
    )
    database: Dict[str, Any] = Field(
        ..., description="Database connectivity and diagnostic details"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "version": "0.1.0",
                "environment": "development",
                "timestamp": "2026-11-12T08:30:00Z",
                "database": {
                    "status": "healthy",
                    "database": "connected"
                }
            }
        }
    }
