from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.enums import OrderStatus

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.payment import PaymentAttempt, PaymentFulfillment
    from app.models.ticket import Ticket
    from app.models.ticket import TicketType
    from app.models.user import User

class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_id_idempotency_key"),
        UniqueConstraint("payment_evidence_reference", name="uq_orders_payment_evidence_reference"),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_orders_quantity_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    # Nullable only for historical rows: the initial schema had no order to
    # ticket-type link. New reservations always provide this value.
    ticket_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ticket_types.id"), nullable=True
    )
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payment_evidence_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="orderstatus", native_enum=True),
        default=OrderStatus.PENDING,
        nullable=False
    )
    payment_reference: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="orders")
    ticket_type: Mapped[TicketType | None] = relationship(back_populates="orders")
    tickets: Mapped[list[Ticket]] = relationship(back_populates="order")
    payment_attempts: Mapped[list[PaymentAttempt]] = relationship(
        "PaymentAttempt", back_populates="order", passive_deletes=True
    )
    payment_fulfillment: Mapped[PaymentFulfillment | None] = relationship(
        "PaymentFulfillment", back_populates="order", uselist=False, passive_deletes=True
    )

