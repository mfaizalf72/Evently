"""
Integration Tests for Role-Based Access Control (RBAC) and Organizer Ownership
Verifies that:
- Customers cannot perform organizer actions.
- Organizers cannot modify or delete events owned by other organizers.
- Administrators can manage all events.
- Public users can browse events without authentication.
"""

from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_unauthenticated_cannot_create_event(async_client: AsyncClient):
    """
    Test creating an event without Authorization header fails with 401 Unauthorized.
    """
    start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=2, hours=3)).isoformat()
    payload = {
        "title": "Unauthenticated Event",
        "location": "Room 1",
        "start_time": start,
        "end_time": end,
        "total_capacity": 20,
    }
    response = await async_client.post(f"{settings.API_V1_STR}/events", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_customer_cannot_create_event(customer_client: AsyncClient):
    """
    Test that users with role 'customer' receive 403 Forbidden when attempting to create events.
    """
    start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=2, hours=3)).isoformat()
    payload = {
        "title": "Customer Forbidden Event",
        "location": "Room 1",
        "start_time": start,
        "end_time": end,
        "total_capacity": 20,
    }
    response = await customer_client.post(f"{settings.API_V1_STR}/events", json=payload)
    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_organizer_can_create_event(organizer_client: AsyncClient, test_organizer: User):
    """
    Test that an organizer can create an event and the event's organizer_id matches their ID.
    """
    start = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=5, hours=3)).isoformat()
    payload = {
        "title": "Organizer Workshop",
        "location": "Online",
        "start_time": start,
        "end_time": end,
        "total_capacity": 50,
        "price": "29.99",
        "is_published": True,
    }
    response = await organizer_client.post(f"{settings.API_V1_STR}/events", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["organizer_id"] == str(test_organizer.id)
    assert data["title"] == "Organizer Workshop"


@pytest.mark.asyncio
async def test_organizer_cannot_modify_other_organizer_event(
    organizer_client: AsyncClient,
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Test that Organizer B receives 403 Forbidden when attempting to update Organizer A's event.
    """
    # Create Organizer B
    org_b = User(
        email="organizer_b@evently.com",
        hashed_password=hash_password("Password123!"),
        full_name="Organizer B",
        role="organizer",
        is_active=True,
    )
    db_session.add(org_b)
    await db_session.commit()
    await db_session.refresh(org_b)
    org_b_token = create_access_token(subject=org_b.id, role=org_b.role)

    # Organizer A creates an event
    start = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=3, hours=2)).isoformat()
    create_resp = await organizer_client.post(
        f"{settings.API_V1_STR}/events",
        json={
            "title": "Organizer A Event",
            "location": "Room 101",
            "start_time": start,
            "end_time": end,
            "total_capacity": 30,
        },
    )
    event_id = create_resp.json()["id"]

    # Organizer B attempts to update Organizer A's event
    org_b_client = async_client
    org_b_client.headers["Authorization"] = f"Bearer {org_b_token}"
    update_resp = await org_b_client.put(
        f"{settings.API_V1_STR}/events/{event_id}",
        json={"title": "Hacked Title"},
    )
    assert update_resp.status_code == 403
    data = update_resp.json()
    assert data["error"]["code"] == "NOT_EVENT_OWNER"

    # Organizer B attempts to delete Organizer A's event
    delete_resp = await org_b_client.delete(f"{settings.API_V1_STR}/events/{event_id}")
    assert delete_resp.status_code == 403
    assert delete_resp.json()["error"]["code"] == "NOT_EVENT_OWNER"


@pytest.mark.asyncio
async def test_admin_can_modify_any_event(
    organizer_client: AsyncClient,
    admin_client: AsyncClient,
):
    """
    Test that an administrator can update and delete any organizer's event.
    """
    start = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=6, hours=2)).isoformat()
    create_resp = await organizer_client.post(
        f"{settings.API_V1_STR}/events",
        json={
            "title": "Admin Override Event",
            "location": "Auditorium",
            "start_time": start,
            "end_time": end,
            "total_capacity": 100,
        },
    )
    event_id = create_resp.json()["id"]

    # Admin updates event
    update_resp = await admin_client.put(
        f"{settings.API_V1_STR}/events/{event_id}",
        json={"title": "Admin Updated Event"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Admin Updated Event"

    # Admin deletes event
    delete_resp = await admin_client.delete(f"{settings.API_V1_STR}/events/{event_id}")
    assert delete_resp.status_code == 204


@pytest.mark.asyncio
async def test_public_can_browse_events_without_authentication(
    organizer_client: AsyncClient,
    async_client: AsyncClient,
):
    """
    Test that unauthenticated clients can list and retrieve event details.
    """
    start = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=4, hours=2)).isoformat()
    create_resp = await organizer_client.post(
        f"{settings.API_V1_STR}/events",
        json={
            "title": "Public Browsable Workshop",
            "location": "Public Library",
            "start_time": start,
            "end_time": end,
            "total_capacity": 45,
            "is_published": True,
        },
    )
    event_id = create_resp.json()["id"]

    # Clear auth headers
    async_client.headers.pop("Authorization", None)

    # Public list
    list_resp = await async_client.get(f"{settings.API_V1_STR}/events")
    assert list_resp.status_code == 200

    # Public get
    get_resp = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Public Browsable Workshop"
