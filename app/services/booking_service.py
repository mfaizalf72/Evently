"""
Booking Service Module
Implements race-condition-proof booking reservation logic, inventory replenishment,
and customer order lifecycle management.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
from typing import List, Optional, Tuple
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthorizationException,
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from app.models.booking import Booking, BookingItem, BookingStatus
from app.models.user import User
from app.repositories.booking_repository import BookingRepository
from app.repositories.event_repository import EventRepository
from app.repositories.ticket_tier_repository import TicketTierRepository
from app.schemas.booking import (
    BookingCreate,
    BookingItemResponse,
    BookingListResponse,
    BookingResponse,
)


class BookingService:
    """
    Service coordinating concurrent seat reservations and booking state transitions.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.booking_repo = BookingRepository(db=db)
        self.event_repo = EventRepository(db=db)
        self.tier_repo = TicketTierRepository(db=db)

    def _to_response(self, booking: Booking) -> BookingResponse:
        """Helper to convert Booking ORM model to BookingResponse with tier names."""
        item_responses = [
            BookingItemResponse(
                id=item.id,
                ticket_tier_id=item.ticket_tier_id,
                tier_name=item.ticket_tier.name if item.ticket_tier else None,
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=item.subtotal,
                created_at=item.created_at,
            )
            for item in booking.items
        ]
        return BookingResponse(
            id=booking.id,
            customer_id=booking.customer_id,
            event_id=booking.event_id,
            status=booking.status,
            total_amount=booking.total_amount,
            idempotency_key=booking.idempotency_key,
            expires_at=booking.expires_at,
            items=item_responses,
            created_at=booking.created_at,
            updated_at=booking.updated_at,
        )

    async def reserve_booking(
        self,
        customer: User,
        event_id: uuid.UUID,
        data: BookingCreate,
    ) -> BookingResponse:
        """
        Executes a race-condition-proof seat reservation using atomic conditional updates.
        Rolls back automatically if inventory is insufficient.
        """
        # 1. Idempotency Check
        if data.idempotency_key:
            existing = await self.booking_repo.get_by_idempotency_key(data.idempotency_key)
            if existing:
                if existing.customer_id != customer.id:
                    raise BusinessRuleViolationException(
                        message="Idempotency key was already used by another customer.",
                        code="IDEMPOTENCY_KEY_COLLISION",
                    )
                if existing.event_id != event_id:
                    raise BusinessRuleViolationException(
                        message="Idempotency key was previously used for a different event.",
                        code="IDEMPOTENCY_CONFLICT",
                    )
                existing_items_map = {item.ticket_tier_id: item.quantity for item in existing.items}
                requested_items_map = {item.ticket_tier_id: item.quantity for item in data.items}
                if existing_items_map != requested_items_map:
                    raise BusinessRuleViolationException(
                        message="Idempotency key was previously used with different booking items.",
                        code="IDEMPOTENCY_CONFLICT",
                    )
                return self._to_response(existing)

        # 2. Event Validation
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise EntityNotFoundException(entity_name="Event", entity_id=event_id)

        if not event.is_published:
            raise BusinessRuleViolationException(
                message="Cannot book tickets for an unpublished event.",
                code="EVENT_NOT_PUBLISHED",
            )

        total_requested_quantity = sum(item.quantity for item in data.items)

        # 3. Atomically reserve event-level capacity
        event_reserved = await self.booking_repo.atomic_reserve_event_capacity(
            event_id=event_id,
            quantity=total_requested_quantity,
        )
        if not event_reserved:
            raise BusinessRuleViolationException(
                message="Event has insufficient available capacity.",
                code="EVENT_CAPACITY_EXCEEDED",
            )

        # 4. Atomically reserve tier-level capacities
        reserved_tiers = []
        booking_items: List[BookingItem] = []
        total_amount = Decimal("0.00")

        try:
            for item_req in data.items:
                tier = await self.tier_repo.get_by_event_and_id(event_id, item_req.ticket_tier_id)
                if not tier:
                    raise EntityNotFoundException(
                        entity_name="TicketTier",
                        entity_id=item_req.ticket_tier_id,
                    )

                tier_reserved = await self.booking_repo.atomic_reserve_tier_capacity(
                    tier_id=item_req.ticket_tier_id,
                    quantity=item_req.quantity,
                )
                if not tier_reserved:
                    raise BusinessRuleViolationException(
                        message=f"Insufficient available seats in ticket tier '{tier.name}'.",
                        code="INSUFFICIENT_INVENTORY",
                    )
                reserved_tiers.append((item_req.ticket_tier_id, item_req.quantity))

                unit_price = tier.price
                subtotal = unit_price * item_req.quantity
                total_amount += subtotal

                booking_item = BookingItem(
                    ticket_tier_id=item_req.ticket_tier_id,
                    quantity=item_req.quantity,
                    unit_price=unit_price,
                    subtotal=subtotal,
                )
                booking_items.append(booking_item)

            # 5. Determine Order Status & Expiration
            now = datetime.now(timezone.utc)
            if total_amount == Decimal("0.00"):
                initial_status = BookingStatus.CONFIRMED.value
                expires_at = None
            else:
                initial_status = BookingStatus.PENDING.value
                expires_at = now + timedelta(minutes=settings.BOOKING_HOLD_MINUTES)

            booking = Booking(
                customer_id=customer.id,
                event_id=event_id,
                status=initial_status,
                total_amount=total_amount,
                idempotency_key=data.idempotency_key,
                expires_at=expires_at,
                items=booking_items,
            )

            created_booking = await self.booking_repo.create(booking)
            await self.db.commit()

            # Re-fetch with eager loaded relationships
            full_booking = await self.booking_repo.get_by_id(created_booking.id)
            return self._to_response(full_booking)

        except Exception:
            # Compensating rollback on failure
            await self.db.rollback()
            raise

    async def get_booking_by_id(
        self,
        booking_id: uuid.UUID,
        current_user: User,
    ) -> BookingResponse:
        """
        Retrieves booking details with ownership verification and lazy expiration check.
        """
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise EntityNotFoundException(entity_name="Booking", entity_id=booking_id)

        # Lazy expiration check: automatically expire pending orders past their expiration deadline
        now = datetime.now(timezone.utc)
        if (
            booking.status == BookingStatus.PENDING.value
            and booking.expires_at is not None
            and booking.expires_at <= now
        ):
            event_seats = 0
            for item in booking.items:
                await self.booking_repo.atomic_release_tier_capacity(
                    tier_id=item.ticket_tier_id,
                    quantity=item.quantity,
                )
                event_seats += item.quantity

            await self.booking_repo.atomic_release_event_capacity(
                event_id=booking.event_id,
                quantity=event_seats,
            )

            booking.status = BookingStatus.EXPIRED.value
            await self.db.commit()
            booking = await self.booking_repo.get_by_id(booking_id)

        # Authorization: Customer, Event Organizer, or Admin
        is_owner = booking.customer_id == current_user.id
        is_organizer = booking.event.organizer_id == current_user.id if booking.event else False
        is_admin = current_user.role == "admin"

        if not (is_owner or is_organizer or is_admin):
            raise AuthorizationException(
                message="You do not have permission to view this booking.",
                code="FORBIDDEN_BOOKING_ACCESS",
            )

        return self._to_response(booking)

    async def list_my_bookings(
        self,
        customer_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> BookingListResponse:
        """
        Lists booking history for the current authenticated customer.
        """
        skip = (page - 1) * page_size
        bookings, total = await self.booking_repo.list_by_customer(
            customer_id=customer_id,
            skip=skip,
            limit=page_size,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return BookingListResponse(
            items=[self._to_response(b) for b in bookings],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def list_event_bookings(
        self,
        event_id: uuid.UUID,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> BookingListResponse:
        """
        Lists all bookings placed for an event (organizer or admin only).
        """
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise EntityNotFoundException(entity_name="Event", entity_id=event_id)

        if current_user.role != "admin":
            if event.organizer_id != current_user.id:
                raise AuthorizationException(
                    message="You do not have permission to view bookings for this event.",
                    code="NOT_EVENT_OWNER",
                )

        skip = (page - 1) * page_size
        bookings, total = await self.booking_repo.list_by_event(
            event_id=event_id,
            skip=skip,
            limit=page_size,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return BookingListResponse(
            items=[self._to_response(b) for b in bookings],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def cancel_booking(
        self,
        booking_id: uuid.UUID,
        current_user: User,
    ) -> BookingResponse:
        """
        Cancels a booking and atomically releases reserved seats back to tier and event capacity.
        """
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise EntityNotFoundException(entity_name="Booking", entity_id=booking_id)

        is_owner = booking.customer_id == current_user.id
        is_organizer = booking.event.organizer_id == current_user.id if booking.event else False
        is_admin = current_user.role == "admin"

        if not (is_owner or is_organizer or is_admin):
            raise AuthorizationException(
                message="You do not have permission to cancel this booking.",
                code="FORBIDDEN_BOOKING_CANCEL",
            )

        if booking.status in (BookingStatus.CANCELLED.value, BookingStatus.EXPIRED.value):
            raise BusinessRuleViolationException(
                message=f"Booking is already {booking.status}.",
                code="ALREADY_INACTIVE",
            )

        # Atomically restore capacity for each item
        total_released = 0
        for item in booking.items:
            await self.booking_repo.atomic_release_tier_capacity(
                tier_id=item.ticket_tier_id,
                quantity=item.quantity,
            )
            total_released += item.quantity

        # Atomically restore capacity to event
        await self.booking_repo.atomic_release_event_capacity(
            event_id=booking.event_id,
            quantity=total_released,
        )

        booking.status = BookingStatus.CANCELLED.value
        await self.db.commit()

        full_booking = await self.booking_repo.get_by_id(booking_id)
        return self._to_response(full_booking)

    async def expire_pending_bookings(
        self,
        batch_size: int = 100,
        now: Optional[datetime] = None,
    ) -> Tuple[int, int]:
        """
        Sweeps expired pending bookings using row-level locking (SKIP LOCKED),
        marks them EXPIRED, and atomically replenishes capacity to tiers and events.
        Returns a tuple of (expired_bookings_count, released_seats_count).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        expired_bookings = await self.booking_repo.get_expired_pending_bookings(
            now=now,
            limit=batch_size,
        )

        total_expired_count = 0
        total_seats_released = 0

        for booking in expired_bookings:
            event_seats = 0
            for item in booking.items:
                await self.booking_repo.atomic_release_tier_capacity(
                    tier_id=item.ticket_tier_id,
                    quantity=item.quantity,
                )
                event_seats += item.quantity

            await self.booking_repo.atomic_release_event_capacity(
                event_id=booking.event_id,
                quantity=event_seats,
            )

            booking.status = BookingStatus.EXPIRED.value
            total_expired_count += 1
            total_seats_released += event_seats

        if total_expired_count > 0:
            await self.db.commit()

        return total_expired_count, total_seats_released
