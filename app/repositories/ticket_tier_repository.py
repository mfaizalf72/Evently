"""
TicketTier Repository Module
Data access implementation for TicketTier entities using SQLAlchemy 2.0.
"""

from typing import List, Optional
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket_tier import TicketTier
from app.repositories.base import BaseRepository


class TicketTierRepository(BaseRepository[TicketTier]):
    """
    Repository handling PostgreSQL queries for TicketTiers.
    """
    def __init__(self, db: AsyncSession):
        super().__init__(model=TicketTier, db=db)

    async def list_by_event(self, event_id: uuid.UUID) -> List[TicketTier]:
        """
        Retrieves all ticket tiers for a specific event ordered by price ascending.
        """
        result = await self.db.execute(
            select(TicketTier)
            .where(TicketTier.event_id == event_id)
            .order_by(TicketTier.price.asc())
        )
        return list(result.scalars().all())

    async def get_by_event_and_id(
        self,
        event_id: uuid.UUID,
        tier_id: uuid.UUID,
    ) -> Optional[TicketTier]:
        """
        Retrieves a ticket tier by its ID ensuring it belongs to the given event.
        """
        result = await self.db.execute(
            select(TicketTier).where(
                TicketTier.event_id == event_id,
                TicketTier.id == tier_id,
            )
        )
        return result.scalars().first()

    async def get_by_event_and_name(
        self,
        event_id: uuid.UUID,
        name: str,
    ) -> Optional[TicketTier]:
        """
        Checks for existing tier with the same case-insensitive name under an event.
        """
        result = await self.db.execute(
            select(TicketTier).where(
                TicketTier.event_id == event_id,
                func.lower(TicketTier.name) == name.strip().lower(),
            )
        )
        return result.scalars().first()

    async def get_allocated_capacity(
        self,
        event_id: uuid.UUID,
        exclude_tier_id: Optional[uuid.UUID] = None,
    ) -> int:
        """
        Calculates the sum of total_capacity allocated across tiers for an event.
        """
        query = select(func.coalesce(func.sum(TicketTier.total_capacity), 0)).where(
            TicketTier.event_id == event_id
        )
        if exclude_tier_id:
            query = query.where(TicketTier.id != exclude_tier_id)

        result = await self.db.execute(query)
        return int(result.scalar_one())
