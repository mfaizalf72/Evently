"""
Integration Tests for Event REST APIs
Tests Event CRUD endpoints against real PostgreSQL database instances with Organizer privileges.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_create_event_success(organizer_client: AsyncClient):
    """
    Test creating a new event returns 201 Created and properly initializes available_capacity.
    """
    start = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=10, hours=4)).isoformat()

    payload = {
        "title": "FastAPI Masterclass",
        "description": "Deep dive into async APIs and PostgreSQL",
        "location": "Innovation Lab, Austin TX",
        "start_time": start,
        "end_time": end,
        "total_capacity": 40,
        "price": "75.00",
        "is_published": True,
    }

    response = await organizer_client.post(f"{settings.API_V1_STR}/events", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["title"] == "FastAPI Masterclass"
    assert data["total_capacity"] == 40
    assert data["available_capacity"] == 40
    assert data["price"] == "75.00"
    assert data["is_published"] is True
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_event_validation_failure(organizer_client: AsyncClient):
    """
    Test that invalid date ranges reject the request with HTTP 422 Unprocessable Entity.
    """
    start = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()  # Invalid: end before start

    payload = {
        "title": "Invalid Event",
        "location": "Austin",
        "start_time": start,
        "end_time": end,
        "total_capacity": 10,
    }

    response = await organizer_client.post(f"{settings.API_V1_STR}/events", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_get_event_by_id_success(organizer_client: AsyncClient, async_client: AsyncClient):
    """
    Test retrieving an existing event by UUID returns 200 OK.
    """
    start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=2, hours=2)).isoformat()

    # Create an event first
    create_resp = await organizer_client.post(
        f"{settings.API_V1_STR}/events",
        json={
            "title": "GraphQL Workshop",
            "location": "Online via Zoom",
            "start_time": start,
            "end_time": end,
            "total_capacity": 25,
            "price": "0.00",
        },
    )
    event_id = create_resp.json()["id"]

    # Public fetch event by id
    response = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == event_id
    assert data["title"] == "GraphQL Workshop"


@pytest.mark.asyncio
async def test_get_event_not_found(async_client: AsyncClient):
    """
    Test that requesting a non-existent UUID returns HTTP 404 with structured error JSON.
    """
    non_existent_id = uuid.uuid4()
    response = await async_client.get(f"{settings.API_V1_STR}/events/{non_existent_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "EVENT_NOT_FOUND"
    assert str(non_existent_id) in data["error"]["message"]


@pytest.mark.asyncio
async def test_list_events_pagination(organizer_client: AsyncClient, async_client: AsyncClient):
    """
    Test listing events with page and page_size query parameters.
    """
    start = datetime.now(timezone.utc) + timedelta(days=1)
    # Create 3 events
    for i in range(3):
        await organizer_client.post(
            f"{settings.API_V1_STR}/events",
            json={
                "title": f"Batch Event {i}",
                "location": "Community Center",
                "start_time": (start + timedelta(days=i)).isoformat(),
                "end_time": (start + timedelta(days=i, hours=2)).isoformat(),
                "total_capacity": 15,
                "price": "20.00",
                "is_published": True,
            },
        )

    response = await async_client.get(f"{settings.API_V1_STR}/events?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] >= 3
    assert data["total_pages"] >= 2


@pytest.mark.asyncio
async def test_list_events_filtering(organizer_client: AsyncClient, async_client: AsyncClient):
    """
    Test filtering events by title, publication status, and price range.
    """
    start = datetime.now(timezone.utc) + timedelta(days=3)
    await organizer_client.post(
        f"{settings.API_V1_STR}/events",
        json={
            "title": "Rust Systems Programming",
            "location": "Seattle Tech Center",
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=3)).isoformat(),
            "total_capacity": 20,
            "price": "120.00",
            "is_published": True,
        },
    )

    # Filter by title substring
    res = await async_client.get(f"{settings.API_V1_STR}/events?title=Rust")
    assert res.status_code == 200
    data = res.json()
    assert any("Rust" in e["title"] for e in data["items"])

    # Filter by min_price
    res_price = await async_client.get(f"{settings.API_V1_STR}/events?min_price=100.00")
    assert res_price.status_code == 200
    for e in res_price.json()["items"]:
        assert Decimal(e["price"]) >= Decimal("100.00")


@pytest.mark.asyncio
async def test_update_event_success(organizer_client: AsyncClient):
    """
    Test updating an event's title, price, and capacity.
    """
    start = datetime.now(timezone.utc) + timedelta(days=7)
    create_resp = await organizer_client.post(
        f"{settings.API_V1_STR}/events",
        json={
            "title": "Initial Title",
            "location": "Room A",
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=2)).isoformat(),
            "total_capacity": 30,
            "price": "10.00",
        },
    )
    event_id = create_resp.json()["id"]

    update_payload = {
        "title": "Updated Title",
        "total_capacity": 50,
        "price": "15.00",
    }
    response = await organizer_client.put(f"{settings.API_V1_STR}/events/{event_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["total_capacity"] == 50
    assert data["available_capacity"] == 50
    assert data["price"] == "15.00"


@pytest.mark.asyncio
async def test_delete_event_success(organizer_client: AsyncClient, async_client: AsyncClient):
    """
    Test deleting an event returns 204 and the event is subsequently not found.
    """
    start = datetime.now(timezone.utc) + timedelta(days=4)
    create_resp = await organizer_client.post(
        f"{settings.API_V1_STR}/events",
        json={
            "title": "Temporary Event",
            "location": "Warehouse 10",
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=2)).isoformat(),
            "total_capacity": 10,
        },
    )
    event_id = create_resp.json()["id"]

    # Delete event
    delete_resp = await organizer_client.delete(f"{settings.API_V1_STR}/events/{event_id}")
    assert delete_resp.status_code == 204

    # Verify event is deleted
    get_resp = await async_client.get(f"{settings.API_V1_STR}/events/{event_id}")
    assert get_resp.status_code == 404
