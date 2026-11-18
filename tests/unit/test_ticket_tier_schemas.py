"""
Unit Tests for TicketTier Pydantic Schemas
Validates name stripping, non-negative pricing, and positive capacity invariants.
"""

from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.ticket_tier import TicketTierCreate, TicketTierUpdate


def test_valid_ticket_tier_create():
    """Verify that valid ticket tier input passes schema validation."""
    tier_data = TicketTierCreate(
        name="  VIP Front Row  ",
        description="Includes complimentary drink and priority seating",
        price=Decimal("99.50"),
        total_capacity=25,
    )
    assert tier_data.name == "VIP Front Row"  # Whitespace stripped
    assert tier_data.price == Decimal("99.50")
    assert tier_data.total_capacity == 25


def test_ticket_tier_zero_capacity_rejected():
    """Verify that total_capacity <= 0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        TicketTierCreate(
            name="General Admission",
            price=Decimal("15.00"),
            total_capacity=0,
        )
    assert "Input should be greater than 0" in str(exc_info.value)


def test_ticket_tier_negative_price_rejected():
    """Verify that price < 0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        TicketTierCreate(
            name="General Admission",
            price=Decimal("-5.00"),
            total_capacity=10,
        )
    assert "Input should be greater than or equal to 0" in str(exc_info.value)


def test_ticket_tier_empty_name_rejected():
    """Verify that empty or whitespace-only name raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        TicketTierCreate(
            name="    ",
            price=Decimal("10.00"),
            total_capacity=10,
        )
    assert "name cannot be empty" in str(exc_info.value)


def test_ticket_tier_update_partial():
    """Verify partial updates with TicketTierUpdate."""
    update_data = TicketTierUpdate(price=Decimal("45.00"), total_capacity=30)
    assert update_data.price == Decimal("45.00")
    assert update_data.total_capacity == 30
    assert update_data.name is None
