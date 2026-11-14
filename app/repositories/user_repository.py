"""
User Repository Module
Data access implementation for User entities using SQLAlchemy 2.0.
"""

from typing import Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """
    Repository handling PostgreSQL queries for Users.
    """
    def __init__(self, db: AsyncSession):
        super().__init__(model=User, db=db)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Retrieves a user by normalized (lowercased) email address.
        """
        normalized_email = email.lower().strip()
        result = await self.db.execute(
            select(User).where(User.email == normalized_email)
        )
        return result.scalars().first()

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Retrieves a user by UUID.
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalars().first()
