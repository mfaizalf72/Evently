"""
Payment and WebhookEvent SQLAlchemy 2.0 Database Models
Represents payment provider transactions, payment states, and idempotent webhook events.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING
import uuid
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.booking import Booking


class PaymentStatus(str, Enum):
    """Lifecycle states for a payment transaction."""
    PENDING = "pending"          # Checkout initiated, awaiting payment
    SUCCEEDED = "succeeded"      # Verified paid via cryptographic webhook
    FAILED = "failed"            # Payment declined or failed
    REFUNDED = "refunded"        # Fully or partially refunded


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Payment transaction record associated with a booking order.
    """
    __tablename__ = "payments"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="stripe",
        index=True,
    )
    provider_payment_intent_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="usd",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=PaymentStatus.PENDING.value,
        index=True,
    )
    client_secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )

    # Relationship to Booking
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="payments",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "amount >= 0",
            name="check_payment_amount_non_negative",
        ),
    )

    def __repr__(self) -> str:
        return f"<Payment id={self.id} booking={self.booking_id} provider='{self.provider}' status='{self.status}' amount={self.amount}>"


class WebhookEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Audit log of ingested webhook events ensuring strict idempotency and replay protection.
    """
    __tablename__ = "webhook_events"

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="stripe",
        index=True,
    )
    provider_event_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
        index=True,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<WebhookEvent id={self.id} event_id='{self.provider_event_id}' type='{self.event_type}' status='{self.status}'>"
