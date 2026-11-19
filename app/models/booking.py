"""
Booking and BookingItem SQLAlchemy 2.0 Database Models
Represents customer reservations, orders, line items, and lifecycle states.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, TYPE_CHECKING
import uuid
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.ticket_tier import TicketTier
    from app.models.user import User


class BookingStatus(str, Enum):
    """Lifecycle states for a booking order."""
    PENDING = "pending"          # Reserved, awaiting payment
    CONFIRMED = "confirmed"      # Payment verified or complimentary event
    CANCELLED = "cancelled"      # Cancelled by user or expired
    REFUNDED = "refunded"        # Fully refunded


class Booking(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Booking entity tracking a customer's order for an event.
    """
    __tablename__ = "bookings"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=BookingStatus.PENDING.value,
        index=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # Relationships
    customer: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
    )
    event: Mapped["Event"] = relationship(
        "Event",
        lazy="selectin",
    )
    items: Mapped[List["BookingItem"]] = relationship(
        "BookingItem",
        back_populates="booking",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "total_amount >= 0",
            name="check_booking_total_amount_non_negative",
        ),
    )

    def __repr__(self) -> str:
        return f"<Booking id={self.id} customer={self.customer_id} event={self.event_id} status='{self.status}' total={self.total_amount}>"


class BookingItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    BookingItem line entity recording specific tier quantity and locked unit price.
    """
    __tablename__ = "booking_items"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_tier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ticket_tiers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="items",
    )
    ticket_tier: Mapped["TicketTier"] = relationship(
        "TicketTier",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="check_booking_item_quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="check_booking_item_unit_price_non_negative",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="check_booking_item_subtotal_non_negative",
        ),
    )

    def __repr__(self) -> str:
        return f"<BookingItem id={self.id} tier={self.ticket_tier_id} qty={self.quantity} subtotal={self.subtotal}>"
