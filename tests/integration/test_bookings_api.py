"""
Integration Tests for Booking REST APIs
Tests ticket reservations, inventory decrements, auto-confirmation of free events,
cancellation inventory replenishment, and customer order history.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


async def setup_event_with_tiers(client: AsyncClient, organizer_token: str):
    """Helper to create an event and tiers for booking tests."""
    start = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=10, hours=4)).isoformat()

    # Create Event (Capacity: 50)
    event_resp = await client.post(
        f"{settings.API_V1_STR}/events",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={
            "title": "Booking Engine Masterclass",
            "location": "Convention Center",
            "start_time": start,
            "end_time": end,
            "total_capacity": 50,
            "price": "50.00",
            "is_published": True,
        },
    )
    event_id = event_resp.json()["id"]

    # Tier 1: Paid General Admission (30 seats @ $50.00)
    tier_paid = await client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={"name": "General Admission", "price": "50.00", "total_capacity": 30},
    )
    paid_tier_id = tier_paid.json()["id"]

    # Tier 2: Free Community Pass (10 seats @ $0.00)
    tier_free = await client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={"name": "Community Pass", "price": "0.00", "total_capacity": 10},
    )
    free_tier_id = tier_free.json()["id"]

    return event_id, paid_tier_id, free_tier_id


@pytest.mark.asyncio
async def test_create_paid_booking_success_pending(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test reserving paid tickets initializes status to 'pending', calculates total,
    and atomically decrements available_capacity.
    """
    event_id, paid_tier_id, _ = await setup_event_with_tiers(async_client, organizer_token)

    booking_payload = {
        "items": [
            {"ticket_tier_id": paid_tier_id, "quantity": 2}
        ]
    }

    response = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json=booking_payload,
    )
    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["status"] == "pending"
    assert data["total_amount"] == "100.00"  # 2 * 50.00
    assert data["expires_at"] is not None
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 2
    assert data["items"][0]["subtotal"] == "100.00"

    # Verify tier available_capacity decremented from 30 to 28
    tier_check = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{paid_tier_id}")
    assert tier_check.json()["available_capacity"] == 28


@pytest.mark.asyncio
async def test_create_free_booking_auto_confirmed(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test reserving a complimentary ($0.00) ticket tier automatically sets status to 'confirmed'.
    """
    event_id, _, free_tier_id = await setup_event_with_tiers(async_client, organizer_token)

    booking_payload = {
        "items": [
            {"ticket_tier_id": free_tier_id, "quantity": 1}
        ]
    }

    response = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json=booking_payload,
    )
    assert response.status_code == 201
    data = response.json()

    assert data["status"] == "confirmed"
    assert data["total_amount"] == "0.00"
    assert data["expires_at"] is None


@pytest.mark.asyncio
async def test_insufficient_inventory_rejected(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that requesting more tickets than available in a tier returns 400 INSUFFICIENT_INVENTORY.
    """
    event_id, _, free_tier_id = await setup_event_with_tiers(async_client, organizer_token)

    # Free tier only has 10 seats. Request 10 once -> succeeds.
    res1 = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"items": [{"ticket_tier_id": free_tier_id, "quantity": 10}]},
    )
    assert res1.status_code == 201

    # Request 1 more seat -> must fail as tier is sold out!
    res2 = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"items": [{"ticket_tier_id": free_tier_id, "quantity": 1}]},
    )
    assert res2.status_code == 400
    assert res2.json()["error"]["code"] == "INSUFFICIENT_INVENTORY"


@pytest.mark.asyncio
async def test_booking_idempotency_prevents_duplicate_orders(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that sending the same idempotency key twice returns the existing booking without double decrementing.
    """
    event_id, paid_tier_id, _ = await setup_event_with_tiers(async_client, organizer_token)

    idem_key = "unique-order-key-999"
    payload = {
        "items": [{"ticket_tier_id": paid_tier_id, "quantity": 2}],
        "idempotency_key": idem_key,
    }

    # First attempt
    res1 = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json=payload,
    )
    assert res1.status_code == 201
    booking_id_1 = res1.json()["id"]

    # Duplicate request with same idempotency key
    res2 = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json=payload,
    )
    assert res2.status_code == 201
    assert res2.json()["id"] == booking_id_1  # Exact same booking returned!

    # Capacity should only have been decremented by 2, NOT 4!
    tier_check = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{paid_tier_id}")
    assert tier_check.json()["available_capacity"] == 28


@pytest.mark.asyncio
async def test_cancel_booking_replenishes_inventory(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test cancelling a booking updates status to 'cancelled' and restores available_capacity.
    """
    event_id, paid_tier_id, _ = await setup_event_with_tiers(async_client, organizer_token)

    # Book 3 tickets
    create_resp = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"items": [{"ticket_tier_id": paid_tier_id, "quantity": 3}]},
    )
    booking_id = create_resp.json()["id"]

    # Verify decremented to 27
    t1 = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{paid_tier_id}")
    assert t1.json()["available_capacity"] == 27

    # Cancel booking
    cancel_resp = await async_client.post(
        f"{settings.API_V1_STR}/bookings/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    # Verify replenished back to 30!
    t2 = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{paid_tier_id}")
    assert t2.json()["available_capacity"] == 30


@pytest.mark.asyncio
async def test_customer_booking_history(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test customer can list their booking history.
    """
    event_id, paid_tier_id, _ = await setup_event_with_tiers(async_client, organizer_token)

    # Place a booking
    await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"items": [{"ticket_tier_id": paid_tier_id, "quantity": 1}]},
    )

    history_resp = await async_client.get(
        f"{settings.API_V1_STR}/bookings/my-bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert history_resp.status_code == 200
    assert history_resp.json()["total"] >= 1
    assert len(history_resp.json()["items"]) >= 1
