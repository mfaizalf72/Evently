"""
Base Repository Module
Provides generic asynchronous CRUD operations using SQLAlchemy 2.0.
"""

from typing import Generic, List, Optional, Type, TypeVar
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Abstract generic base repository defining standard asynchronous data access patterns.
    """
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, id: uuid.UUID) -> Optional[ModelType]:
        """Fetch a single record by primary key UUID."""
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalars().first()

    async def create(self, entity: ModelType) -> ModelType:
        """Persist a new entity to the database."""
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def update(self, entity: ModelType) -> ModelType:
        """Flush changes to an existing attached entity."""
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def delete(self, entity: ModelType) -> None:
        """Remove an entity from the database."""
        await self.db.delete(entity)
        await self.db.flush()
