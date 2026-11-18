"""
Integration Tests for TicketTier REST APIs
Tests tier creation, aggregate event capacity constraints, unique naming, and ownership verification.
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


async def create_test_event(client: AsyncClient, capacity: int = 50) -> str:
    """Helper fixture to create a valid event and return its ID."""
    start = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=7, hours=3)).isoformat()
    resp = await client.post(
        f"{settings.API_V1_STR}/events",
        json={
            "title": "Tiered Conference 2026",
            "location": "Convention Center",
            "start_time": start,
            "end_time": end,
            "total_capacity": capacity,
            "price": "20.00",
            "is_published": True,
        },
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_ticket_tier_success(organizer_client: AsyncClient):
    """
    Test organizer can add a ticket tier to their event.
    """
    event_id = await create_test_event(organizer_client, capacity=100)

    payload = {
        "name": "Early Bird",
        "description": "Discounted admission for first 40 buyers",
        "price": "25.00",
        "total_capacity": 40,
    }
    response = await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["event_id"] == event_id
    assert data["name"] == "Early Bird"
    assert data["price"] == "25.00"
    assert data["total_capacity"] == 40
    assert data["available_capacity"] == 40


@pytest.mark.asyncio
async def test_create_multiple_tiers_within_capacity(organizer_client: AsyncClient):
    """
    Test creating multiple tiers whose sum equals the total event capacity.
    """
    event_id = await create_test_event(organizer_client, capacity=60)

    # Tier 1: Early Bird (20 seats)
    res1 = await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "Early Bird", "price": "20.00", "total_capacity": 20},
    )
    assert res1.status_code == 201

    # Tier 2: General Admission (30 seats)
    res2 = await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "General Admission", "price": "35.00", "total_capacity": 30},
    )
    assert res2.status_code == 201

    # Tier 3: VIP (10 seats) -> Total allocated is now 20 + 30 + 10 = 60
    res3 = await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "VIP", "price": "75.00", "total_capacity": 10},
    )
    assert res3.status_code == 201

    # Verify listing reflects metrics
    list_resp = await organizer_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] == 3
    assert list_data["total_allocated_capacity"] == 60
    assert list_data["event_total_capacity"] == 60


@pytest.mark.asyncio
async def test_create_tier_exceeding_event_capacity_fails(organizer_client: AsyncClient):
    """
    Test that creating a tier that exceeds the remaining unallocated event capacity is rejected with 400.
    """
    event_id = await create_test_event(organizer_client, capacity=50)

    # Allocate 40 seats
    await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "General", "price": "20.00", "total_capacity": 40},
    )

    # Attempt to allocate 20 seats (only 10 remaining)
    response = await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "VIP", "price": "50.00", "total_capacity": 20},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "TIER_CAPACITY_EXCEEDS_EVENT"
    assert "Only 10 seats remaining" in data["error"]["message"]


@pytest.mark.asyncio
async def test_create_tier_duplicate_name_fails(organizer_client: AsyncClient):
    """
    Test that adding a tier with duplicate name (case-insensitive) under the same event fails.
    """
    event_id = await create_test_event(organizer_client, capacity=50)

    # First tier
    await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "VIP Pass", "price": "100.00", "total_capacity": 10},
    )

    # Duplicate name
    response = await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "  vip pass  ", "price": "120.00", "total_capacity": 10},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TIER_NAME_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_customer_cannot_create_tier(async_client: AsyncClient, organizer_token: str, customer_token: str):
    """
    Test that customers receive 403 Forbidden when attempting to create a ticket tier.
    """
    # Create event as organizer
    start = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=7, hours=3)).isoformat()
    resp = await async_client.post(
        f"{settings.API_V1_STR}/events",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={
            "title": "Tiered Conference 2026",
            "location": "Convention Center",
            "start_time": start,
            "end_time": end,
            "total_capacity": 50,
            "price": "20.00",
            "is_published": True,
        },
    )
    event_id = resp.json()["id"]

    # Attempt to add tier with Customer token
    response = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"name": "Hacker Tier", "price": "0.00", "total_capacity": 10},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_non_owner_organizer_cannot_modify_tiers(
    organizer_client: AsyncClient,
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Test that Organizer B cannot create, update, or delete tiers on Organizer A's event.
    """
    # Create Organizer B
    org_b = User(
        email="organizer_other@evently.com",
        hashed_password=hash_password("Password123!"),
        full_name="Other Organizer",
        role="organizer",
        is_active=True,
    )
    db_session.add(org_b)
    await db_session.commit()
    await db_session.refresh(org_b)
    org_b_token = create_access_token(subject=org_b.id, role=org_b.role)

    # Organizer A creates event & tier
    event_id = await create_test_event(organizer_client, capacity=50)
    tier_resp = await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "Org A Tier", "price": "15.00", "total_capacity": 20},
    )
    tier_id = tier_resp.json()["id"]

    # Organizer B attempts to add a tier
    async_client.headers["Authorization"] = f"Bearer {org_b_token}"
    create_resp = await async_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "Org B Intrusion", "price": "10.00", "total_capacity": 10},
    )
    assert create_resp.status_code == 403
    assert create_resp.json()["error"]["code"] == "NOT_EVENT_OWNER"

    # Organizer B attempts to update Organizer A's tier
    update_resp = await async_client.put(
        f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}",
        json={"price": "1.00"},
    )
    assert update_resp.status_code == 403
    assert update_resp.json()["error"]["code"] == "NOT_EVENT_OWNER"

    # Organizer B attempts to delete Organizer A's tier
    del_resp = await async_client.delete(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert del_resp.status_code == 403
    assert del_resp.json()["error"]["code"] == "NOT_EVENT_OWNER"


@pytest.mark.asyncio
async def test_public_can_browse_tiers(organizer_client: AsyncClient, async_client: AsyncClient):
    """
    Test that anonymous/unauthenticated users can list and inspect ticket tiers.
    """
    event_id = await create_test_event(organizer_client, capacity=50)
    tier_resp = await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "Public Tier", "price": "30.00", "total_capacity": 25},
    )
    tier_id = tier_resp.json()["id"]

    # Clear authorization header
    async_client.headers.pop("Authorization", None)

    # Public list
    list_resp = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # Public get
    get_resp = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Public Tier"


@pytest.mark.asyncio
async def test_update_tier_success(organizer_client: AsyncClient):
    """
    Test organizer can update price and capacity of a tier.
    """
    event_id = await create_test_event(organizer_client, capacity=50)
    tier_resp = await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "Standard", "price": "20.00", "total_capacity": 25},
    )
    tier_id = tier_resp.json()["id"]

    update_resp = await organizer_client.put(
        f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}",
        json={"price": "29.99", "total_capacity": 35},
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["price"] == "29.99"
    assert data["total_capacity"] == 35
    assert data["available_capacity"] == 35


@pytest.mark.asyncio
async def test_delete_tier_success(organizer_client: AsyncClient):
    """
    Test organizer can delete an unbooked ticket tier.
    """
    event_id = await create_test_event(organizer_client, capacity=50)
    tier_resp = await organizer_client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        json={"name": "Temporary Tier", "price": "10.00", "total_capacity": 10},
    )
    tier_id = tier_resp.json()["id"]

    del_resp = await organizer_client.delete(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert del_resp.status_code == 204

    get_resp = await organizer_client.get(f"{settings.API_V1_STR}/events/{event_id}/tiers/{tier_id}")
    assert get_resp.status_code == 404
