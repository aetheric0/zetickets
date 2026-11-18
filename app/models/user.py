from __future__ import annotations

import uuid
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.order import Order
    from app.models.profile import OrganizerProfile

class UserRole(str, PyEnum):
    ORGANIZER = "organizer"
    GATEKEEPER = "gatekeeper"
    ADMIN = "admin"
    ATTENDEE = "attendee"

class User(Base, TimestampMixin):
    """
    User account model for Organizers, Gatekeepers, and Admins.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    phone_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", values_callable=lambda enum: [item.value for item in enum]),
        default=UserRole.ATTENDEE,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    # Retained for compatibility with existing authorization code; role
    # remains the canonical account classification.
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # Relationships
    organizer_profile: Mapped[OrganizerProfile | None] = relationship(
        "OrganizerProfile",
        back_populates="user",
        uselist=False,
        passive_deletes=True
    )
    events: Mapped[list[Event]] = relationship(
        "Event",
        back_populates="organizer",
        passive_deletes=True
    )
    orders: Mapped[list[Order]] = relationship(
        "Order",
        back_populates="user"
    )

