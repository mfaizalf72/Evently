"""
Booking API Endpoints
RESTful routes for creating reservations, inspecting customer order history,
event roster management, and order cancellation.
"""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.booking import (
    BookingCreate,
    BookingExpirationSweepResponse,
    BookingListResponse,
    BookingResponse,
)
from app.services.booking_service import BookingService

router = APIRouter(tags=["Bookings"])


def get_booking_service(db: AsyncSession = Depends(get_db)) -> BookingService:
    return BookingService(db=db)


@router.post(
    "/events/{event_id}/bookings",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reserve Tickets",
    description="Atomically reserves tickets for an event. Guaranteed race-condition proof with idempotency.",
)
async def create_booking(
    event_id: uuid.UUID,
    payload: BookingCreate,
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_active_user),
    service: BookingService = Depends(get_booking_service),
) -> BookingResponse:
    # Header takes priority over body if provided
    idempotency_key = idempotency_key_header or payload.idempotency_key
    if idempotency_key:
        payload.idempotency_key = idempotency_key

    return await service.reserve_booking(
        customer=current_user,
        event_id=event_id,
        data=payload,
    )


@router.get(
    "/bookings/my-bookings",
    response_model=BookingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get My Booking History",
    description="Returns paginated list of bookings placed by the authenticated user.",
)
async def get_my_bookings(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    service: BookingService = Depends(get_booking_service),
) -> BookingListResponse:
    return await service.list_my_bookings(
        customer_id=current_user.id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/events/{event_id}/bookings",
    response_model=BookingListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Event Bookings",
    description="Lists all customer bookings placed for a specific event. Requires Organizer ownership.",
)
async def list_event_bookings(
    event_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    service: BookingService = Depends(get_booking_service),
) -> BookingListResponse:
    return await service.list_event_bookings(
        event_id=event_id,
        current_user=current_user,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/bookings/{booking_id}",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Booking Details",
    description="Fetches order status and line items. Requires order ownership or event organizer role.",
)
async def get_booking(
    booking_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    service: BookingService = Depends(get_booking_service),
) -> BookingResponse:
    return await service.get_booking_by_id(
        booking_id=booking_id,
        current_user=current_user,
    )


@router.post(
    "/bookings/{booking_id}/cancel",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Booking",
    description="Cancels an order and atomically releases held tickets back to available inventory.",
)
async def cancel_booking(
    booking_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    service: BookingService = Depends(get_booking_service),
) -> BookingResponse:
    return await service.cancel_booking(
        booking_id=booking_id,
        current_user=current_user,
    )


@router.post(
    "/bookings/expire-pending",
    response_model=BookingExpirationSweepResponse,
    status_code=status.HTTP_200_OK,
    summary="Expire Stale Pending Reservations",
    description="Sweeps all pending reservations past their expiration deadline, transitions them to EXPIRED, and releases reserved capacity.",
)
async def expire_pending_bookings(
    batch_size: int = Query(100, ge=1, le=500, description="Max bookings to process in this sweep batch"),
    current_user: User = Depends(get_current_active_user),
    service: BookingService = Depends(get_booking_service),
) -> BookingExpirationSweepResponse:
    expired_count, released_seats = await service.expire_pending_bookings(batch_size=batch_size)
    return BookingExpirationSweepResponse(
        expired_bookings_count=expired_count,
        released_seats_count=released_seats,
        message=f"Processed {expired_count} expired pending bookings and replenished {released_seats} seats.",
    )
