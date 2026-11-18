"""
Ticket Tier Schemas Module
Pydantic v2 data validation schemas for TicketTier operations.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TicketTierBase(BaseModel):
    """Common ticket tier attributes."""
    name: str = Field(..., min_length=2, max_length=100, description="Ticket tier name (e.g. VIP, General, Early Bird)")
    description: Optional[str] = Field(None, max_length=2000, description="Tier perks, inclusions, or restrictions")
    price: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), description="Ticket price for this tier")
    total_capacity: int = Field(..., gt=0, description="Number of seats allocated to this tier")

    @field_validator("name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Tier name cannot be empty or whitespace only.")
        return v_stripped


class TicketTierCreate(TicketTierBase):
    """Schema for adding a ticket tier to an event."""
    pass


class TicketTierUpdate(BaseModel):
    """Schema for updating an existing ticket tier."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    price: Optional[Decimal] = Field(None, ge=Decimal("0.00"))
    total_capacity: Optional[int] = Field(None, gt=0)

    @field_validator("name")
    @classmethod
    def strip_whitespace_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_stripped = v.strip()
            if not v_stripped:
                raise ValueError("Tier name cannot be empty or whitespace only.")
            return v_stripped
        return v


class TicketTierResponse(TicketTierBase):
    """Public ticket tier response schema."""
    id: uuid.UUID = Field(..., description="Unique tier identifier")
    event_id: uuid.UUID = Field(..., description="Associated event identifier")
    available_capacity: int = Field(..., ge=0, description="Remaining seats available for booking in this tier")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")

    model_config = ConfigDict(from_attributes=True)


class TicketTierListResponse(BaseModel):
    """Envelope schema for listing all tiers belonging to an event."""
    items: List[TicketTierResponse] = Field(..., description="List of ticket tiers")
    total: int = Field(..., ge=0, description="Total count of tiers")
    total_allocated_capacity: int = Field(..., ge=0, description="Total seats allocated across all tiers")
    event_total_capacity: int = Field(..., ge=0, description="Total capacity limit of the parent event")
