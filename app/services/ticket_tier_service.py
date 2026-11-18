"""
TicketTier Service Module
Implements business rules, capacity invariants, and orchestrates repository operations for Ticket Tiers.
"""

from typing import List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationException,
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from app.models.ticket_tier import TicketTier
from app.models.user import User
from app.repositories.event_repository import EventRepository
from app.repositories.ticket_tier_repository import TicketTierRepository
from app.schemas.ticket_tier import (
    TicketTierCreate,
    TicketTierListResponse,
    TicketTierResponse,
    TicketTierUpdate,
)


class TicketTierService:
    """
    Service class managing Ticket Tier lifecycle and event capacity allocation invariants.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tier_repository = TicketTierRepository(db=db)
        self.event_repository = EventRepository(db=db)

    async def _verify_event_ownership(self, event_id: uuid.UUID, current_user: User):
        """Helper to ensure event exists and caller is authorized organizer or admin."""
        event = await self.event_repository.get_by_id(event_id)
        if not event:
            raise EntityNotFoundException(entity_name="Event", entity_id=event_id)

        if current_user.role != "admin":
            if event.organizer_id is not None and event.organizer_id != current_user.id:
                raise AuthorizationException(
                    message="You do not have permission to modify ticket tiers for this event.",
                    code="NOT_EVENT_OWNER",
                )
        return event

    async def create_tier(
        self,
        event_id: uuid.UUID,
        data: TicketTierCreate,
        current_user: User,
    ) -> TicketTierResponse:
        """
        Creates a new ticket tier while enforcing aggregate event capacity limits.
        """
        event = await self._verify_event_ownership(event_id, current_user)

        # Check duplicate name under this event
        existing_tier = await self.tier_repository.get_by_event_and_name(event_id, data.name)
        if existing_tier:
            raise BusinessRuleViolationException(
                message=f"A ticket tier named '{data.name}' already exists for this event.",
                code="TIER_NAME_ALREADY_EXISTS",
            )

        # Enforce aggregate capacity invariant
        allocated = await self.tier_repository.get_allocated_capacity(event_id)
        remaining_capacity = event.total_capacity - allocated

        if data.total_capacity > remaining_capacity:
            raise BusinessRuleViolationException(
                message=(
                    f"Cannot allocate {data.total_capacity} seats. "
                    f"Only {remaining_capacity} seats remaining in event capacity "
                    f"(Event Total: {event.total_capacity}, Allocated: {allocated})."
                ),
                code="TIER_CAPACITY_EXCEEDS_EVENT",
            )

        tier = TicketTier(
            event_id=event_id,
            name=data.name,
            description=data.description,
            price=data.price,
            total_capacity=data.total_capacity,
            available_capacity=data.total_capacity,
        )

        created_tier = await self.tier_repository.create(tier)
        await self.db.commit()
        return TicketTierResponse.model_validate(created_tier)

    async def list_tiers(self, event_id: uuid.UUID) -> TicketTierListResponse:
        """
        Lists all ticket tiers for an event along with capacity allocation metrics.
        """
        event = await self.event_repository.get_by_id(event_id)
        if not event:
            raise EntityNotFoundException(entity_name="Event", entity_id=event_id)

        tiers = await self.tier_repository.list_by_event(event_id)
        allocated = sum(t.total_capacity for t in tiers)

        return TicketTierListResponse(
            items=[TicketTierResponse.model_validate(t) for t in tiers],
            total=len(tiers),
            total_allocated_capacity=allocated,
            event_total_capacity=event.total_capacity,
        )

    async def get_tier_by_id(
        self,
        event_id: uuid.UUID,
        tier_id: uuid.UUID,
    ) -> TicketTierResponse:
        """
        Retrieves a single ticket tier.
        """
        tier = await self.tier_repository.get_by_event_and_id(event_id, tier_id)
        if not tier:
            raise EntityNotFoundException(entity_name="TicketTier", entity_id=tier_id)
        return TicketTierResponse.model_validate(tier)

    async def update_tier(
        self,
        event_id: uuid.UUID,
        tier_id: uuid.UUID,
        data: TicketTierUpdate,
        current_user: User,
    ) -> TicketTierResponse:
        """
        Updates an existing ticket tier with capacity and ownership safeguards.
        """
        event = await self._verify_event_ownership(event_id, current_user)

        tier = await self.tier_repository.get_by_event_and_id(event_id, tier_id)
        if not tier:
            raise EntityNotFoundException(entity_name="TicketTier", entity_id=tier_id)

        update_dict = data.model_dump(exclude_unset=True)

        # Check name collision if name is changing
        if "name" in update_dict and update_dict["name"].strip().lower() != tier.name.lower():
            existing = await self.tier_repository.get_by_event_and_name(event_id, update_dict["name"])
            if existing and existing.id != tier.id:
                raise BusinessRuleViolationException(
                    message=f"A ticket tier named '{update_dict['name']}' already exists for this event.",
                    code="TIER_NAME_ALREADY_EXISTS",
                )

        # Enforce capacity adjustment rules
        if "total_capacity" in update_dict:
            new_total = update_dict["total_capacity"]
            booked_seats = tier.total_capacity - tier.available_capacity
            if new_total < booked_seats:
                raise BusinessRuleViolationException(
                    message=f"Cannot reduce tier capacity to {new_total}. Already reserved seats: {booked_seats}.",
                    code="CAPACITY_BELOW_RESERVED",
                )

            # Check against event limit
            other_allocated = await self.tier_repository.get_allocated_capacity(event_id, exclude_tier_id=tier_id)
            if other_allocated + new_total > event.total_capacity:
                max_allowed = event.total_capacity - other_allocated
                raise BusinessRuleViolationException(
                    message=f"Cannot set capacity to {new_total}. Maximum available capacity for this tier is {max_allowed}.",
                    code="TIER_CAPACITY_EXCEEDS_EVENT",
                )

            tier.available_capacity = new_total - booked_seats
            tier.total_capacity = new_total

        # Apply other scalar fields
        for field, value in update_dict.items():
            if field not in ("total_capacity",):
                setattr(tier, field, value)

        updated_tier = await self.tier_repository.update(tier)
        await self.db.commit()
        return TicketTierResponse.model_validate(updated_tier)

    async def delete_tier(
        self,
        event_id: uuid.UUID,
        tier_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """
        Deletes a ticket tier provided no seats have been booked.
        """
        await self._verify_event_ownership(event_id, current_user)

        tier = await self.tier_repository.get_by_event_and_id(event_id, tier_id)
        if not tier:
            raise EntityNotFoundException(entity_name="TicketTier", entity_id=tier_id)

        booked_seats = tier.total_capacity - tier.available_capacity
        if booked_seats > 0:
            raise BusinessRuleViolationException(
                message=f"Cannot delete ticket tier with {booked_seats} active ticket bookings.",
                code="CANNOT_DELETE_ACTIVE_TIER",
            )

        await self.tier_repository.delete(tier)
        await self.db.commit()
