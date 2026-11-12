"""
Event SQLAlchemy 2.0 Database Model
Represents community events, workshops, and gatherings with database-level capacity constraints.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Event(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Event model representing workshops, webinars, and meetups.
    Enforces capacity and pricing invariants at the PostgreSQL table level.
    """
    __tablename__ = "events"

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    location: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    total_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    available_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "total_capacity > 0",
            name="check_event_total_capacity_positive",
        ),
        CheckConstraint(
            "available_capacity >= 0 AND available_capacity <= total_capacity",
            name="check_event_available_capacity_valid",
        ),
        CheckConstraint(
            "price >= 0",
            name="check_event_price_non_negative",
        ),
        CheckConstraint(
            "end_time > start_time",
            name="check_event_end_time_after_start_time",
        ),
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} title='{self.title}' available={self.available_capacity}/{self.total_capacity}>"
