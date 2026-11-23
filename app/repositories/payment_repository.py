"""
Payment and WebhookEvent Repositories Module
Data access implementation for Payment transactions and WebhookEvent audit records.
"""

from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payment import Payment, PaymentStatus, WebhookEvent
from app.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    """
    Repository managing Payment entities.
    """
    def __init__(self, db: AsyncSession):
        super().__init__(model=Payment, db=db)

    async def get_by_provider_payment_intent_id(
        self,
        provider_payment_intent_id: str,
    ) -> Optional[Payment]:
        """
        Retrieves a payment record by its external provider payment intent ID.
        """
        stmt = (
            select(Payment)
            .where(Payment.provider_payment_intent_id == provider_payment_intent_id)
            .options(selectinload(Payment.booking))
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_pending_payment_for_booking(
        self,
        booking_id: uuid.UUID,
    ) -> Optional[Payment]:
        """
        Retrieves an active pending payment for a given booking to avoid duplicate intents.
        """
        stmt = (
            select(Payment)
            .where(
                Payment.booking_id == booking_id,
                Payment.status == PaymentStatus.PENDING.value,
            )
            .order_by(Payment.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_booking_id(
        self,
        booking_id: uuid.UUID,
    ) -> List[Payment]:
        """
        Lists all payment transactions recorded for a booking.
        """
        stmt = (
            select(Payment)
            .where(Payment.booking_id == booking_id)
            .order_by(Payment.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class WebhookEventRepository(BaseRepository[WebhookEvent]):
    """
    Repository managing idempotent WebhookEvent records.
    """
    def __init__(self, db: AsyncSession):
        super().__init__(model=WebhookEvent, db=db)

    async def get_by_provider_event_id(
        self,
        provider_event_id: str,
    ) -> Optional[WebhookEvent]:
        """
        Retrieves an existing webhook event record by external event ID to ensure idempotency.
        """
        stmt = select(WebhookEvent).where(WebhookEvent.provider_event_id == provider_event_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()
