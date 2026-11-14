"""
Event Service Module
Implements business rules, validation invariants, ownership verification, and orchestrates repository operations.
"""

import math
from typing import Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationException,
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from app.models.event import Event
from app.models.user import User
from app.repositories.event_repository import EventRepository
from app.schemas.event import (
    EventCreate,
    EventFilterParams,
    EventListResponse,
    EventResponse,
    EventUpdate,
)


class EventService:
    """
    Service class managing Event business logic, lifecycle operations, and ownership verification.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = EventRepository(db=db)

    async def create_event(
        self,
        data: EventCreate,
        organizer_id: Optional[uuid.UUID] = None,
    ) -> EventResponse:
        """
        Creates a new event with available_capacity initially equal to total_capacity
        and binds it to the authenticated organizer.
        """
        event = Event(
            title=data.title,
            description=data.description,
            location=data.location,
            start_time=data.start_time,
            end_time=data.end_time,
            total_capacity=data.total_capacity,
            available_capacity=data.total_capacity,
            price=data.price,
            is_published=data.is_published,
            organizer_id=organizer_id,
        )

        created_event = await self.repository.create(event)
        await self.db.commit()
        return EventResponse.model_validate(created_event)

    async def get_event_by_id(self, event_id: uuid.UUID) -> EventResponse:
        """
        Retrieves an event by UUID, raising EntityNotFoundException if absent.
        """
        event = await self.repository.get_by_id(event_id)
        if not event:
            raise EntityNotFoundException(entity_name="Event", entity_id=event_id)
        return EventResponse.model_validate(event)

    async def list_events(self, filters: EventFilterParams) -> EventListResponse:
        """
        Lists events according to pagination and filter parameters.
        """
        events, total = await self.repository.list_events(filters=filters)
        total_pages = math.ceil(total / filters.page_size) if total > 0 else 0

        return EventListResponse(
            items=[EventResponse.model_validate(e) for e in events],
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
        )

    async def update_event(
        self,
        event_id: uuid.UUID,
        data: EventUpdate,
        current_user: Optional[User] = None,
    ) -> EventResponse:
        """
        Updates an existing event while enforcing date, capacity invariants, and organizer ownership.
        """
        event = await self.repository.get_by_id(event_id)
        if not event:
            raise EntityNotFoundException(entity_name="Event", entity_id=event_id)

        # Enforce organizer ownership if caller is authenticated
        if current_user and current_user.role != "admin":
            if event.organizer_id is not None and event.organizer_id != current_user.id:
                raise AuthorizationException(
                    message="You do not have permission to modify this event because you are not its organizer.",
                    code="NOT_EVENT_OWNER",
                )

        update_dict = data.model_dump(exclude_unset=True)

        # Validate date consistency if dates are updated
        new_start = update_dict.get("start_time", event.start_time)
        new_end = update_dict.get("end_time", event.end_time)
        if new_end <= new_start:
            raise BusinessRuleViolationException(
                message="Event end_time must be strictly after start_time.",
                code="INVALID_EVENT_DATES",
            )

        # Validate capacity adjustments against existing bookings
        if "total_capacity" in update_dict:
            new_total = update_dict["total_capacity"]
            booked_seats = event.total_capacity - event.available_capacity
            if new_total < booked_seats:
                raise BusinessRuleViolationException(
                    message=f"Cannot reduce total capacity to {new_total}. Already reserved seats: {booked_seats}.",
                    code="CAPACITY_BELOW_RESERVED",
                )
            event.available_capacity = new_total - booked_seats
            event.total_capacity = new_total

        # Apply other scalar fields
        for field, value in update_dict.items():
            if field not in ("total_capacity",):
                setattr(event, field, value)

        updated_event = await self.repository.update(event)
        await self.db.commit()
        return EventResponse.model_validate(updated_event)

    async def delete_event(
        self,
        event_id: uuid.UUID,
        current_user: Optional[User] = None,
    ) -> None:
        """
        Deletes an event if no seats have been booked and caller owns the event.
        """
        event = await self.repository.get_by_id(event_id)
        if not event:
            raise EntityNotFoundException(entity_name="Event", entity_id=event_id)

        # Enforce organizer ownership
        if current_user and current_user.role != "admin":
            if event.organizer_id is not None and event.organizer_id != current_user.id:
                raise AuthorizationException(
                    message="You do not have permission to delete this event because you are not its organizer.",
                    code="NOT_EVENT_OWNER",
                )

        booked_seats = event.total_capacity - event.available_capacity
        if booked_seats > 0:
            raise BusinessRuleViolationException(
                message=f"Cannot delete event with {booked_seats} active ticket bookings.",
                code="CANNOT_DELETE_ACTIVE_EVENT",
            )

        await self.repository.delete(event)
        await self.db.commit()


def get_event_service(db: AsyncSession) -> EventService:
    """Dependency helper to create EventService instance."""
    return EventService(db=db)
