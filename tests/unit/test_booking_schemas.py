"""
Unit Tests for Booking Pydantic Schemas
Validates order item quantities, min items constraints, and schema invariants.
"""

import uuid
import pytest
from pydantic import ValidationError

from app.schemas.booking import BookingCreate, BookingItemCreate


def test_valid_booking_create():
    """Verify that valid booking payload passes schema validation."""
    tier_id = uuid.uuid4()
    booking_data = BookingCreate(
        items=[
            BookingItemCreate(ticket_tier_id=tier_id, quantity=2)
        ],
        idempotency_key="order-abc-123",
    )
    assert len(booking_data.items) == 1
    assert booking_data.items[0].ticket_tier_id == tier_id
    assert booking_data.items[0].quantity == 2
    assert booking_data.idempotency_key == "order-abc-123"


def test_booking_empty_items_rejected():
    """Verify that a booking request with no line items is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        BookingCreate(items=[])
    assert "at least 1 item" in str(exc_info.value).lower()


def test_booking_item_zero_quantity_rejected():
    """Verify that quantity <= 0 is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        BookingItemCreate(ticket_tier_id=uuid.uuid4(), quantity=0)
    assert "greater than 0" in str(exc_info.value).lower()


def test_booking_item_excessive_quantity_rejected():
    """Verify that quantity > 10 per tier is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        BookingItemCreate(ticket_tier_id=uuid.uuid4(), quantity=11)
    assert "less than or equal to 10" in str(exc_info.value).lower()
