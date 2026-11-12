"""
Unit Tests for Event Pydantic Schemas
Validates field-level rules, type coercions, and model-level date invariants.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.event import EventCreate, EventUpdate


def test_valid_event_create():
    """Verify that valid event input passes schema validation."""
    start = datetime.now(timezone.utc) + timedelta(days=5)
    end = start + timedelta(hours=3)

    event_data = EventCreate(
        title="  Python Microservices Workshop  ",
        description="Hands-on building with FastAPI & PostgreSQL",
        location="Tech Hub Room 402",
        start_time=start,
        end_time=end,
        total_capacity=50,
        price=Decimal("49.99"),
        is_published=True,
    )

    assert event_data.title == "Python Microservices Workshop"  # Whitespace stripped
    assert event_data.location == "Tech Hub Room 402"
    assert event_data.total_capacity == 50
    assert event_data.price == Decimal("49.99")
    assert event_data.is_published is True


def test_event_create_invalid_dates():
    """Verify that end_time earlier than or equal to start_time raises ValidationError."""
    start = datetime.now(timezone.utc) + timedelta(days=5)
    end = start - timedelta(hours=1)  # Invalid: end is before start

    with pytest.raises(ValidationError) as exc_info:
        EventCreate(
            title="Invalid Date Workshop",
            location="Online",
            start_time=start,
            end_time=end,
            total_capacity=20,
        )
    assert "Event end_time must be strictly after start_time." in str(exc_info.value)


def test_event_create_zero_capacity():
    """Verify that total_capacity <= 0 raises ValidationError."""
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)

    with pytest.raises(ValidationError) as exc_info:
        EventCreate(
            title="Zero Capacity Event",
            location="Room 1",
            start_time=start,
            end_time=end,
            total_capacity=0,
        )
    assert "Input should be greater than 0" in str(exc_info.value)


def test_event_create_negative_price():
    """Verify that price < 0 raises ValidationError."""
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)

    with pytest.raises(ValidationError) as exc_info:
        EventCreate(
            title="Negative Price Event",
            location="Room 1",
            start_time=start,
            end_time=end,
            total_capacity=10,
            price=Decimal("-10.00"),
        )
    assert "Input should be greater than or equal to 0" in str(exc_info.value)


def test_event_update_dates_validation():
    """Verify that EventUpdate validates date ordering when both dates are provided."""
    start = datetime.now(timezone.utc) + timedelta(days=2)
    end = start - timedelta(hours=2)

    with pytest.raises(ValidationError) as exc_info:
        EventUpdate(start_time=start, end_time=end)
    assert "Event end_time must be strictly after start_time." in str(exc_info.value)
