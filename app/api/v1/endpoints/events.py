"""
Event API Endpoints
RESTful routes for creating, listing, retrieving, updating, and deleting events.
Protected mutations enforce Organizer role and resource ownership.
"""

from typing import Optional
import uuid
from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_organizer
from app.database.session import get_db
from app.models.user import User
from app.schemas.event import (
    EventCreate,
    EventFilterParams,
    EventListResponse,
    EventResponse,
    EventUpdate,
)
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["Events"])


def get_service(db: AsyncSession = Depends(get_db)) -> EventService:
    return EventService(db=db)


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New Event",
    description="Registers a new event. Requires Organizer or Admin privileges.",
)
async def create_event(
    payload: EventCreate,
    current_user: User = Depends(get_current_organizer),
    service: EventService = Depends(get_service),
) -> EventResponse:
    return await service.create_event(data=payload, organizer_id=current_user.id)


@router.get(
    "",
    response_model=EventListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Events",
    description="Returns a paginated list of events with optional title, location, date, price, and status filters.",
)
async def list_events(
    title: Optional[str] = Query(None, description="Filter by title (case-insensitive substring)"),
    location: Optional[str] = Query(None, description="Filter by location (case-insensitive substring)"),
    is_published: Optional[bool] = Query(None, description="Filter by publication status"),
    from_date: Optional[datetime] = Query(None, description="Filter events starting on or after this timestamp"),
    to_date: Optional[datetime] = Query(None, description="Filter events ending on or before this timestamp"),
    min_price: Optional[Decimal] = Query(None, ge=Decimal("0.00"), description="Minimum ticket price"),
    max_price: Optional[Decimal] = Query(None, ge=Decimal("0.00"), description="Maximum ticket price"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    service: EventService = Depends(get_service),
) -> EventListResponse:
    filters = EventFilterParams(
        title=title,
        location=location,
        is_published=is_published,
        from_date=from_date,
        to_date=to_date,
        min_price=min_price,
        max_price=max_price,
        page=page,
        page_size=page_size,
    )
    return await service.list_events(filters=filters)


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Event Details",
    description="Fetches full details of a specific event by its UUID.",
)
async def get_event(
    event_id: uuid.UUID,
    service: EventService = Depends(get_service),
) -> EventResponse:
    return await service.get_event_by_id(event_id=event_id)


@router.put(
    "/{event_id}",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Event",
    description="Updates event fields. Requires that the caller is the organizer of this event or an Admin.",
)
async def update_event(
    event_id: uuid.UUID,
    payload: EventUpdate,
    current_user: User = Depends(get_current_organizer),
    service: EventService = Depends(get_service),
) -> EventResponse:
    return await service.update_event(
        event_id=event_id,
        data=payload,
        current_user=current_user,
    )


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Event",
    description="Permanently removes an event. Requires event ownership and no booked tickets.",
)
async def delete_event(
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_organizer),
    service: EventService = Depends(get_service),
) -> None:
    await service.delete_event(event_id=event_id, current_user=current_user)
