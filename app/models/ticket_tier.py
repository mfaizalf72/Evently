"""
TicketTier SQLAlchemy 2.0 Database Model
Represents ticket tiers (e.g. VIP, Early Bird, General Admission) with database-level capacity constraints.
"""

from decimal import Decimal
from typing import Optional, TYPE_CHECKING
import uuid
from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.event import Event


class TicketTier(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    TicketTier entity representing distinct ticket pricing categories and capacity allocations within an Event.
    """
    __tablename__ = "ticket_tiers"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    total_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    available_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Relationships
    event: Mapped["Event"] = relationship(
        "Event",
        back_populates="ticket_tiers",
    )

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "name",
            name="uq_ticket_tier_event_id_name",
        ),
        CheckConstraint(
            "price >= 0",
            name="check_tier_price_non_negative",
        ),
        CheckConstraint(
            "total_capacity > 0",
            name="check_tier_total_capacity_positive",
        ),
        CheckConstraint(
            "available_capacity >= 0 AND available_capacity <= total_capacity",
            name="check_tier_available_capacity_valid",
        ),
    )

    def __repr__(self) -> str:
        return f"<TicketTier id={self.id} event_id={self.event_id} name='{self.name}' price={self.price} available={self.available_capacity}/{self.total_capacity}>"
