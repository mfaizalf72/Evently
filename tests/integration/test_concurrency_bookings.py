"""
Integration Tests for PostgreSQL Concurrency Controls & Race-Condition Prevention
Verifies that simultaneous booking requests for limited seats cannot cause overbooking.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User


@pytest.mark.asyncio
async def test_last_seat_concurrent_booking_race_condition(
    async_client: AsyncClient,
    organizer_token: str,
    db_session: AsyncSession,
):
    """
    CRITICAL CONCURRENCY TEST:
    A ticket tier has only ONE seat remaining.
    Five distinct customers attempt to book that last seat simultaneously via asyncio.gather.
    
    EXPECTED OUTCOME:
    - Exactly 1 customer receives a 201 Created allocation.
    - Exactly 4 customers receive 400 Bad Request (INSUFFICIENT_INVENTORY).
    - Database remaining available_capacity is exactly 0 (never negative).
    - No duplicate confirmations occur.
    """
    # 1. Create Event with capacity 10
    start = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=5, hours=2)).isoformat()
    event_resp = await async_client.post(
        f"{settings.API_V1_STR}/events",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={
            "title": "Exclusive Last Seat Workshop",
            "location": "Room 101",
            "start_time": start,
            "end_time": end,
            "total_capacity": 10,
            "is_published": True,
        },
    )
    event_id = event_resp.json()["id"]

    # 2. Create Tier with ONLY 1 SEAT AVAILABLE!
    tier_resp = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={
            "name": "Last Seat Tier",
            "price": "50.00",
            "total_capacity": 1,
        },
    )
    tier_id = tier_resp.json()["id"]

    # 3. Create 5 distinct registered customers with valid tokens
    customer_tokens = []
    for i in range(5):
        cust = User(
            email=f"concurrent_cust_{i}_{uuid.uuid4().hex[:6]}@evently.com",
            hashed_password=hash_password("Password123!"),
            full_name=f"Customer {i}",
            role="customer",
            is_active=True,
        )
        db_session.add(cust)
        await db_session.commit()
        await db_session.refresh(cust)
        token = create_access_token(subject=cust.id, role=cust.role)
        customer_tokens.append(token)

    # 4. Define client booking coroutine using independent transport/client instances
    async def attempt_booking(token: str):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                f"{settings.API_V1_STR}/events/{event_id}/bookings",
                headers={"Authorization": f"Bearer {token}"},
                json={"items": [{"ticket_tier_id": tier_id, "quantity": 1}]},
            )

    # 5. Fire all 5 requests SIMULTANEOUSLY!
    responses = await asyncio.gather(*[attempt_booking(tok) for tok in customer_tokens])

    # 6. Analyze results
    success_responses = [r for r in responses if r.status_code == 201]
    failed_responses = [r for r in responses if r.status_code == 400]

    # Exactly 1 customer must have received the seat
    assert len(success_responses) == 1, f"Expected 1 success, got {len(success_responses)}"
    # Exactly 4 must have failed safely
    assert len(failed_responses) == 4, f"Expected 4 failures, got {len(failed_responses)}"

    for fail in failed_responses:
        assert fail.json()["error"]["code"] == "INSUFFICIENT_INVENTORY"

    # 7. Verify authoritative database state
    tier_check = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    final_capacity = tier_check.json()["available_capacity"]
    assert final_capacity == 0, f"Expected exactly 0 available capacity, got {final_capacity}"


@pytest.mark.asyncio
async def test_multiple_seats_concurrent_bookings(
    async_client: AsyncClient,
    organizer_token: str,
    db_session: AsyncSession,
):
    """
    Test 10 concurrent requests competing for 3 available seats.
    Exactly 3 must succeed, 7 must fail, and available_capacity must reach exactly 0.
    """
    start = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=6, hours=3)).isoformat()
    event_resp = await async_client.post(
        f"{settings.API_V1_STR}/events",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={
            "title": "Three Seats Competition",
            "location": "Auditorium",
            "start_time": start,
            "end_time": end,
            "total_capacity": 10,
            "is_published": True,
        },
    )
    event_id = event_resp.json()["id"]

    tier_resp = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={
            "name": "Limited Trio",
            "price": "30.00",
            "total_capacity": 3,
        },
    )
    tier_id = tier_resp.json()["id"]

    # Create 10 customers
    customer_tokens = []
    for i in range(10):
        cust = User(
            email=f"multi_cust_{i}_{uuid.uuid4().hex[:6]}@evently.com",
            hashed_password=hash_password("Password123!"),
            full_name=f"Customer M{i}",
            role="customer",
            is_active=True,
        )
        db_session.add(cust)
        await db_session.commit()
        await db_session.refresh(cust)
        token = create_access_token(subject=cust.id, role=cust.role)
        customer_tokens.append(token)

    async def attempt_booking(token: str):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                f"{settings.API_V1_STR}/events/{event_id}/bookings",
                headers={"Authorization": f"Bearer {token}"},
                json={"items": [{"ticket_tier_id": tier_id, "quantity": 1}]},
            )

    responses = await asyncio.gather(*[attempt_booking(tok) for tok in customer_tokens])

    successes = [r for r in responses if r.status_code == 201]
    failures = [r for r in responses if r.status_code == 400]

    assert len(successes) == 3
    assert len(failures) == 7

    tier_check = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert tier_check.json()["available_capacity"] == 0
