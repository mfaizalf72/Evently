"""
Event Schemas Module
Pydantic v2 data validation schemas for Event operations.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventBase(BaseModel):
    """Common event attributes shared across create, update, and response schemas."""
    title: str = Field(..., min_length=3, max_length=255, description="Event title")
    description: Optional[str] = Field(None, max_length=5000, description="Detailed event description")
    location: str = Field(..., min_length=2, max_length=255, description="Physical venue or online URL")
    start_time: datetime = Field(..., description="Event start time (UTC)")
    end_time: datetime = Field(..., description="Event end time (UTC)")
    total_capacity: int = Field(..., gt=0, description="Total seating capacity (must be greater than 0)")
    price: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), description="Ticket price per seat")
    is_published: bool = Field(default=False, description="Whether the event is published for booking")

    @field_validator("title", "location")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Field cannot be empty or whitespace only.")
        return v_stripped


class EventCreate(EventBase):
    """Schema for event creation requests."""
    @model_validator(mode="after")
    def validate_event_dates(self) -> "EventCreate":
        if self.end_time <= self.start_time:
            raise ValueError("Event end_time must be strictly after start_time.")
        return self


class EventUpdate(BaseModel):
    """Schema for partial or complete event update requests."""
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    location: Optional[str] = Field(None, min_length=2, max_length=255)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_capacity: Optional[int] = Field(None, gt=0)
    price: Optional[Decimal] = Field(None, ge=Decimal("0.00"))
    is_published: Optional[bool] = None

    @field_validator("title", "location")
    @classmethod
    def strip_whitespace_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_stripped = v.strip()
            if not v_stripped:
                raise ValueError("Field cannot be empty or whitespace only.")
            return v_stripped
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> "EventUpdate":
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("Event end_time must be strictly after start_time.")
        return self


class EventResponse(EventBase):
    """Schema for returning event details to clients."""
    id: uuid.UUID = Field(..., description="Unique event identifier")
    organizer_id: Optional[uuid.UUID] = Field(None, description="Organizer user identifier")
    available_capacity: int = Field(..., ge=0, description="Seats currently available for booking")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")

    model_config = ConfigDict(from_attributes=True)


class EventListResponse(BaseModel):
    """Paginated envelope for event listings."""
    items: List[EventResponse] = Field(..., description="List of events on the current page")
    total: int = Field(..., ge=0, description="Total count of matching events")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Number of items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class EventFilterParams(BaseModel):
    """Query parameter model for filtering and paginating events."""
    title: Optional[str] = None
    location: Optional[str] = None
    is_published: Optional[bool] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    min_price: Optional[Decimal] = Field(None, ge=Decimal("0.00"))
    max_price: Optional[Decimal] = Field(None, ge=Decimal("0.00"))
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
