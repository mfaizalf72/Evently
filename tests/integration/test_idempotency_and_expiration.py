"""
Integration Tests for V7 Milestone: Idempotency & Reservation Expiration
Verifies header-based idempotency keys, duplicate payload prevention,
automatic lazy expiration, and background sweep inventory replenishment.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.core.config import settings
from app.models.booking import Booking, BookingStatus
from app.models.event import Event
from app.models.ticket_tier import TicketTier
from app.models.user import User
from tests.conftest import TestAsyncSessionLocal


async def setup_published_event_with_tier(
    client: AsyncClient,
    organizer_token: str,
    total_capacity: int = 20,
    price: str = "50.00",
) -> tuple[str, str]:
    """Helper to create a published event with a single ticket tier."""
    start = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=5, hours=3)).isoformat()
    event_resp = await client.post(
        f"{settings.API_V1_STR}/events",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={
            "title": f"V7 Test Event {uuid.uuid4().hex[:6]}",
            "location": "Convention Center",
            "start_time": start,
            "end_time": end,
            "total_capacity": total_capacity,
            "price": price,
            "is_published": True,
        },
    )
    event_id = event_resp.json()["id"]

    tier_resp = await client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={
            "name": "Standard Admission",
            "price": price,
            "total_capacity": total_capacity,
        },
    )
    tier_id = tier_resp.json()["id"]
    return event_id, tier_id


@pytest.mark.asyncio
async def test_idempotency_key_header_prevents_duplicate_orders(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that submitting multiple booking requests with the same Idempotency-Key
    header replays the existing booking without deducting additional inventory.
    """
    event_id, tier_id = await setup_published_event_with_tier(
        async_client,
        organizer_token,
        total_capacity=20,
        price="50.00",
    )

    idempotency_key = f"idem-key-{uuid.uuid4()}"
    booking_payload = {
        "items": [{"ticket_tier_id": tier_id, "quantity": 2}],
    }

    # 1. First booking request with Idempotency-Key header
    first_resp = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={
            "Authorization": f"Bearer {customer_token}",
            "Idempotency-Key": idempotency_key,
        },
        json=booking_payload,
    )
    assert first_resp.status_code == 201
    first_data = first_resp.json()
    booking_id = first_data["id"]
    assert first_data["status"] == "pending"
    assert first_data["idempotency_key"] == idempotency_key

    # Check tier capacity decremented to 18
    tier_check = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert tier_check.json()["available_capacity"] == 18

    # 2. Customer repeats identical request with same Idempotency-Key header
    second_resp = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={
            "Authorization": f"Bearer {customer_token}",
            "Idempotency-Key": idempotency_key,
        },
        json=booking_payload,
    )
    assert second_resp.status_code == 201
    second_data = second_resp.json()
    assert second_data["id"] == booking_id
    assert second_data["total_amount"] == first_data["total_amount"]

    # Available capacity must remain strictly 18 (NO duplicate seat deduction)
    tier_check_after = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert tier_check_after.json()["available_capacity"] == 18


@pytest.mark.asyncio
async def test_idempotency_conflict_with_different_payload(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that reusing an Idempotency-Key with different line items or quantities
    is rejected as an idempotency conflict.
    """
    event_id, tier_id = await setup_published_event_with_tier(
        async_client,
        organizer_token,
        total_capacity=25,
        price="25.00",
    )

    idempotency_key = f"conflict-key-{uuid.uuid4()}"

    # Initial booking for 1 ticket
    initial_resp = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={
            "Authorization": f"Bearer {customer_token}",
            "Idempotency-Key": idempotency_key,
        },
        json={"items": [{"ticket_tier_id": tier_id, "quantity": 1}]},
    )
    assert initial_resp.status_code == 201

    # Attempting to use same idempotency key for 3 tickets
    conflict_resp = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={
            "Authorization": f"Bearer {customer_token}",
            "Idempotency-Key": idempotency_key,
        },
        json={"items": [{"ticket_tier_id": tier_id, "quantity": 3}]},
    )
    assert conflict_resp.status_code == 400
    err_body = conflict_resp.json()
    assert err_body["error"]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_sweep_expired_pending_reservations(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that background/endpoint sweep of expired pending reservations transitions
    bookings to EXPIRED and restores capacity to both ticket tiers and parent events.
    """
    event_id, tier_id = await setup_published_event_with_tier(
        async_client,
        organizer_token,
        total_capacity=10,
        price="100.00",
    )

    # Customer reserves 4 tickets
    booking_resp = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"items": [{"ticket_tier_id": tier_id, "quantity": 4}]},
    )
    assert booking_resp.status_code == 201
    booking_id = uuid.UUID(booking_resp.json()["id"])
    assert booking_resp.json()["status"] == "pending"

    # Verify inventory was decremented: 10 - 4 = 6
    tier_check = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert tier_check.json()["available_capacity"] == 6

    # Simulate expiration by updating expires_at directly in test database to 10 minutes ago
    past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    async with TestAsyncSessionLocal() as session:
        await session.execute(
            update(Booking)
            .where(Booking.id == booking_id)
            .values(expires_at=past_time)
        )
        await session.commit()

    # Trigger expiration sweep endpoint
    sweep_resp = await async_client.post(
        f"{settings.API_V1_STR}/bookings/expire-pending",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert sweep_resp.status_code == 200
    sweep_data = sweep_resp.json()
    assert sweep_data["expired_bookings_count"] >= 1
    assert sweep_data["released_seats_count"] >= 4

    # Verify booking status changed to 'expired'
    booking_check = await async_client.get(
        f"{settings.API_V1_STR}/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert booking_check.status_code == 200
    assert booking_check.json()["status"] == "expired"

    # Verify tier inventory is fully restored back to 10
    tier_restored = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert tier_restored.json()["available_capacity"] == 10

    # Verify event inventory is also restored back to 10
    event_restored = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}")
    assert event_restored.json()["available_capacity"] == 10


@pytest.mark.asyncio
async def test_lazy_expiration_on_booking_retrieval(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that viewing an expired pending booking via GET /bookings/{id} immediately
    transitions it to EXPIRED and restores inventory on the fly.
    """
    event_id, tier_id = await setup_published_event_with_tier(
        async_client,
        organizer_token,
        total_capacity=5,
        price="30.00",
    )

    # Customer books 3 seats
    book_resp = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"items": [{"ticket_tier_id": tier_id, "quantity": 3}]},
    )
    assert book_resp.status_code == 201
    booking_id = uuid.UUID(book_resp.json()["id"])

    # Capacity is 2
    tier_before = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert tier_before.json()["available_capacity"] == 2

    # Manually backdate expires_at
    past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    async with TestAsyncSessionLocal() as session:
        await session.execute(
            update(Booking)
            .where(Booking.id == booking_id)
            .values(expires_at=past_time)
        )
        await session.commit()

    # Customer fetches booking details
    fetch_resp = await async_client.get(
        f"{settings.API_V1_STR}/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert fetch_resp.status_code == 200
    assert fetch_resp.json()["status"] == "expired"

    # Inventory must now be restored to 5
    tier_after = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert tier_after.json()["available_capacity"] == 5


@pytest.mark.asyncio
async def test_cannot_cancel_already_expired_booking(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that attempting to cancel an already expired booking fails safely
    without double-replenishing inventory.
    """
    event_id, tier_id = await setup_published_event_with_tier(
        async_client,
        organizer_token,
        total_capacity=20,
        price="150.00",
    )

    book_resp = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"items": [{"ticket_tier_id": tier_id, "quantity": 2}]},
    )
    assert book_resp.status_code == 201
    booking_id = book_resp.json()["id"]

    # Expire it via database update and sweep
    past_time = datetime.now(timezone.utc) - timedelta(minutes=20)
    async with TestAsyncSessionLocal() as session:
        await session.execute(
            update(Booking)
            .where(Booking.id == uuid.UUID(booking_id))
            .values(expires_at=past_time)
        )
        await session.commit()

    # Run sweep
    await async_client.post(
        f"{settings.API_V1_STR}/bookings/expire-pending",
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    # Now attempt to cancel the expired booking
    cancel_resp = await async_client.post(
        f"{settings.API_V1_STR}/bookings/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert cancel_resp.status_code == 400
    assert cancel_resp.json()["error"]["code"] == "ALREADY_INACTIVE"

    # Capacity remains 20 (not 22)
    tier_check = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert tier_check.json()["available_capacity"] == 20
