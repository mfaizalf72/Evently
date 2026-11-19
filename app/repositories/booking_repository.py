"""
Booking Repository Module
Data access implementation for Bookings featuring PostgreSQL atomic conditional updates
to guarantee race-condition-proof inventory reservations.
"""

from typing import List, Optional, Tuple
import uuid
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.booking import Booking, BookingItem
from app.models.event import Event
from app.models.ticket_tier import TicketTier
from app.repositories.base import BaseRepository


class BookingRepository(BaseRepository[Booking]):
    """
    Repository managing Bookings with PostgreSQL concurrency primitives.
    """
    def __init__(self, db: AsyncSession):
        super().__init__(model=Booking, db=db)

    async def atomic_reserve_tier_capacity(
        self,
        tier_id: uuid.UUID,
        quantity: int,
    ) -> bool:
        """
        Executes an atomic conditional UPDATE on ticket_tiers table.
        Atomically decrements available_capacity IF AND ONLY IF enough seats are available.
        Returns True if reservation succeeded, False if sold out.
        """
        stmt = (
            update(TicketTier)
            .where(
                TicketTier.id == tier_id,
                TicketTier.available_capacity >= quantity,
            )
            .values(available_capacity=TicketTier.available_capacity - quantity)
            .returning(TicketTier.id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def atomic_release_tier_capacity(
        self,
        tier_id: uuid.UUID,
        quantity: int,
    ) -> None:
        """
        Atomically restores available_capacity to a ticket tier upon cancellation or expiration.
        """
        stmt = (
            update(TicketTier)
            .where(TicketTier.id == tier_id)
            .values(available_capacity=TicketTier.available_capacity + quantity)
        )
        await self.db.execute(stmt)

    async def atomic_reserve_event_capacity(
        self,
        event_id: uuid.UUID,
        quantity: int,
    ) -> bool:
        """
        Atomically decrements the parent event's available_capacity.
        """
        stmt = (
            update(Event)
            .where(
                Event.id == event_id,
                Event.available_capacity >= quantity,
            )
            .values(available_capacity=Event.available_capacity - quantity)
            .returning(Event.id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def atomic_release_event_capacity(
        self,
        event_id: uuid.UUID,
        quantity: int,
    ) -> None:
        """
        Atomically restores the parent event's available_capacity.
        """
        stmt = (
            update(Event)
            .where(Event.id == event_id)
            .values(available_capacity=Event.available_capacity + quantity)
        )
        await self.db.execute(stmt)

    async def get_by_id(self, booking_id: uuid.UUID) -> Optional[Booking]:
        """
        Retrieves a booking by ID with eagerly loaded line items and tier names.
        """
        stmt = (
            select(Booking)
            .where(Booking.id == booking_id)
            .options(
                selectinload(Booking.items).selectinload(BookingItem.ticket_tier),
                selectinload(Booking.event),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Booking]:
        """
        Fetches existing booking with given idempotency key.
        """
        stmt = (
            select(Booking)
            .where(Booking.idempotency_key == idempotency_key)
            .options(
                selectinload(Booking.items).selectinload(BookingItem.ticket_tier),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_by_customer(
        self,
        customer_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Booking], int]:
        """
        Lists customer's bookings with pagination and total count.
        """
        count_stmt = select(func.count(Booking.id)).where(Booking.customer_id == customer_id)
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Booking)
            .where(Booking.customer_id == customer_id)
            .options(
                selectinload(Booking.items).selectinload(BookingItem.ticket_tier),
            )
            .order_by(Booking.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def list_by_event(
        self,
        event_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Booking], int]:
        """
        Lists bookings for a specific event with pagination and total count.
        """
        count_stmt = select(func.count(Booking.id)).where(Booking.event_id == event_id)
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Booking)
            .where(Booking.event_id == event_id)
            .options(
                selectinload(Booking.items).selectinload(BookingItem.ticket_tier),
            )
            .order_by(Booking.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
