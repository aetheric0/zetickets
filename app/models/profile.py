from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.schemas.user import User

class OrganizerProfile(Base, TimestampMixin):
    """
    Stores business identity and Paystack subaccount configuration.
    """
    __tablename__ = "organizer_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    business_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    # Paystack Settlement Configuration
    paystack_subaccount_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )
    paystack_bank_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    paystack_account_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    percentage_charge: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=0.00,
        nullable=False,
        comment="Platform fee share percentage"
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="organizer_profile"
    )