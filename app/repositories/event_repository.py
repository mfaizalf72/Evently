"""
Event Repository Module
Data access implementation for Event entities using SQLAlchemy 2.0.
"""

from typing import List, Optional, Tuple
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.repositories.base import BaseRepository
from app.schemas.event import EventFilterParams


class EventRepository(BaseRepository[Event]):
    """
    Repository handling PostgreSQL queries for Events.
    """
    def __init__(self, db: AsyncSession):
        super().__init__(model=Event, db=db)

    async def list_events(
        self,
        filters: EventFilterParams,
    ) -> Tuple[List[Event], int]:
        """
        Retrieves a paginated list of events matching query filters along with the total count.
        """
        # Base query
        query = select(Event)
        count_query = select(func.count(Event.id))

        conditions = []

        if filters.title:
            conditions.append(Event.title.ilike(f"%{filters.title.strip()}%"))
        if filters.location:
            conditions.append(Event.location.ilike(f"%{filters.location.strip()}%"))
        if filters.is_published is not None:
            conditions.append(Event.is_published == filters.is_published)
        if filters.from_date:
            conditions.append(Event.start_time >= filters.from_date)
        if filters.to_date:
            conditions.append(Event.end_time <= filters.to_date)
        if filters.min_price is not None:
            conditions.append(Event.price >= filters.min_price)
        if filters.max_price is not None:
            conditions.append(Event.price <= filters.max_price)

        if conditions:
            query = query.where(*conditions)
            count_query = count_query.where(*conditions)

        # Execute total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Apply ordering and pagination
        skip = (filters.page - 1) * filters.page_size
        query = query.order_by(Event.start_time.asc()).offset(skip).limit(filters.page_size)

        result = await self.db.execute(query)
        events = list(result.scalars().all())

        return events, total
