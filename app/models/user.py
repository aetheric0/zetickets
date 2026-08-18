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
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    phone_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum"),
        default=UserRole.ATTENDEE,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    organizer_profile: Mapped[OrganizerProfile | None] = relationship(
        "OrganizerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    events: Mapped[list[Event]] = relationship(
        "Event",
        back_populates="organizer",
        cascade="all, delete-orphan"
    )
    orders: Mapped[list[Order]] = relationship(
        "Order",
        back_populates="user"
    )

