from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.order import Order


class TicketStatus(str, PyEnum):
    RESERVED = "RESERVED"
    ISSUED = "ISSUED"
    USED = "USED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

class TicketType(Base, TimestampMixin):
    """
    Defines ticket tiers created by organizers for an event.
    """
    __tablename__ = "ticket_types"
    __table_args__ = (
        CheckConstraint("quantity_reserved IS NULL OR quantity_reserved >= 0", name="ck_ticket_types_reserved_nonnegative"),
        CheckConstraint("quantity_sold IS NULL OR quantity_sold >= 0", name="ck_ticket_types_sold_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid()
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    ) # e.g. "VIP", "Early bird"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    quantity_available: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Total max tickets allocated for this tier"
    )
    # NULL identifies legacy inventory whose counters cannot be reconstructed
    # safely. New ticket types initialize both counters explicitly.
    quantity_reserved: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Active pending reservation holds")
    quantity_sold: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Finalized paid ticket sales")

    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Relationships
    event: Mapped[Event] = relationship(
        "Event",
        back_populates="ticket_types"
    )
    tickets: Mapped[list[Ticket]] = relationship(
        "Ticket",
        back_populates="ticket_type"
    )
    orders: Mapped[list[Order]] = relationship("Order", back_populates="ticket_type")

    @hybrid_property
    def remaining_capacity(self) -> int | None:
        """
        Dynamic Python evaluation for remaining available capacity.
        """
        if self.quantity_sold is None or self.quantity_reserved is None:
            return None
        return self.quantity_available - (self.quantity_sold + self.quantity_reserved)

    @remaining_capacity.inplace.expression
    @classmethod
    def _remaining_capacity_expression(cls):
        """
        Dynamic SQL expression evaluation for filtering in database queries
        """
        return cls.quantity_available - (cls.quantity_sold + cls.quantity_reserved)


class Ticket(Base, TimestampMixin):
    """
    An individual ticket issued to a user after a successful purchase
    """
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid()
    )
    ticket_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ticket_types.id"),
        nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id"),
        nullable=False
    )
    ticket_code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticketstatus", native_enum=True),
        default=TicketStatus.ISSUED,
        nullable=False
    )

    # Relationships
    ticket_type: Mapped[TicketType] = relationship(back_populates="tickets")
    order: Mapped[Order] = relationship(back_populates="tickets")
