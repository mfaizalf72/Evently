"""
Booking Schemas Module
Pydantic v2 data validation schemas for Booking and Reservation operations.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class BookingItemCreate(BaseModel):
    """Line item requested in a booking."""
    ticket_tier_id: uuid.UUID = Field(..., description="Target ticket tier identifier")
    quantity: int = Field(..., gt=0, le=10, description="Number of tickets requested for this tier (1 to 10)")


class BookingCreate(BaseModel):
    """Customer request payload to book tickets."""
    items: List[BookingItemCreate] = Field(..., min_length=1, description="List of tier allocations requested")
    idempotency_key: Optional[str] = Field(None, max_length=255, description="Unique client key preventing duplicate orders")


class BookingItemResponse(BaseModel):
    """Line item response detailing tier allocation and locked price."""
    id: uuid.UUID = Field(..., description="Unique booking line item identifier")
    ticket_tier_id: uuid.UUID = Field(..., description="Associated ticket tier identifier")
    tier_name: Optional[str] = Field(None, description="Name of the ticket tier")
    quantity: int = Field(..., description="Reserved quantity")
    unit_price: Decimal = Field(..., description="Price charged per ticket")
    subtotal: Decimal = Field(..., description="Line subtotal (quantity * unit_price)")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")

    model_config = ConfigDict(from_attributes=True)


class BookingResponse(BaseModel):
    """Complete booking order response with status, amount, and items."""
    id: uuid.UUID = Field(..., description="Unique booking identifier")
    customer_id: uuid.UUID = Field(..., description="Customer who placed the booking")
    event_id: uuid.UUID = Field(..., description="Target event identifier")
    status: str = Field(..., description="Current booking status (pending, confirmed, cancelled, expired)")
    total_amount: Decimal = Field(..., description="Total order amount")
    idempotency_key: Optional[str] = Field(None, description="Client idempotency key")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp for pending orders")
    items: List[BookingItemResponse] = Field(default_factory=list, description="Ordered ticket items")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")

    model_config = ConfigDict(from_attributes=True)


class BookingListResponse(BaseModel):
    """Paginated envelope for customer or organizer bookings."""
    items: List[BookingResponse] = Field(..., description="List of bookings")
    total: int = Field(..., ge=0, description="Total matching bookings count")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Number of items per page")
    total_pages: int = Field(..., ge=0, description="Total pages available")


class BookingExpirationSweepResponse(BaseModel):
    """Response payload detailing the outcome of an expiration sweep."""
    expired_bookings_count: int = Field(..., description="Number of expired pending bookings transitioned to EXPIRED")
    released_seats_count: int = Field(..., description="Total seats replenished to ticket tier and event capacities")
    message: str = Field(..., description="Summary message")
