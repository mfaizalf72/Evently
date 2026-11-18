"""
TicketTier API Endpoints
RESTful routes for creating, listing, inspecting, updating, and deleting event ticket tiers.
"""

import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_organizer
from app.database.session import get_db
from app.models.user import User
from app.schemas.ticket_tier import (
    TicketTierCreate,
    TicketTierListResponse,
    TicketTierResponse,
    TicketTierUpdate,
)
from app.services.ticket_tier_service import TicketTierService

router = APIRouter(prefix="/events/{event_id}/tiers", tags=["Ticket Tiers"])


def get_tier_service(db: AsyncSession = Depends(get_db)) -> TicketTierService:
    return TicketTierService(db=db)


@router.post(
    "",
    response_model=TicketTierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Ticket Tier",
    description="Adds a new ticket tier (e.g. Early Bird, VIP) to an event. Requires Organizer ownership.",
)
async def create_tier(
    event_id: uuid.UUID,
    payload: TicketTierCreate,
    current_user: User = Depends(get_current_organizer),
    service: TicketTierService = Depends(get_tier_service),
) -> TicketTierResponse:
    return await service.create_tier(
        event_id=event_id,
        data=payload,
        current_user=current_user,
    )


@router.get(
    "",
    response_model=TicketTierListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Event Ticket Tiers",
    description="Returns all ticket tiers for a specific event with capacity allocations. Publicly accessible.",
)
async def list_tiers(
    event_id: uuid.UUID,
    service: TicketTierService = Depends(get_tier_service),
) -> TicketTierListResponse:
    return await service.list_tiers(event_id=event_id)


@router.get(
    "/{tier_id}",
    response_model=TicketTierResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Ticket Tier",
    description="Fetches details of a specific ticket tier. Publicly accessible.",
)
async def get_tier(
    event_id: uuid.UUID,
    tier_id: uuid.UUID,
    service: TicketTierService = Depends(get_tier_service),
) -> TicketTierResponse:
    return await service.get_tier_by_id(event_id=event_id, tier_id=tier_id)


@router.put(
    "/{tier_id}",
    response_model=TicketTierResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Ticket Tier",
    description="Updates ticket tier price, description, or capacity. Requires Organizer ownership.",
)
async def update_tier(
    event_id: uuid.UUID,
    tier_id: uuid.UUID,
    payload: TicketTierUpdate,
    current_user: User = Depends(get_current_organizer),
    service: TicketTierService = Depends(get_tier_service),
) -> TicketTierResponse:
    return await service.update_tier(
        event_id=event_id,
        tier_id=tier_id,
        data=payload,
        current_user=current_user,
    )


@router.delete(
    "/{tier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Ticket Tier",
    description="Deletes a ticket tier provided no bookings exist. Requires Organizer ownership.",
)
async def delete_tier(
    event_id: uuid.UUID,
    tier_id: uuid.UUID,
    current_user: User = Depends(get_current_organizer),
    service: TicketTierService = Depends(get_tier_service),
) -> None:
    await service.delete_tier(
        event_id=event_id,
        tier_id=tier_id,
        current_user=current_user,
    )
