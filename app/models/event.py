from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.ticket import TicketType
    from app.models.user import User

class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid()
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable = False
    )
    end_time: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    organizer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # Relationships
    organizer: Mapped[User] = relationship(
        "User",
        back_populates="events"
    )
    ticket_types: Mapped[list[TicketType]] = relationship(
        "TicketType", 
        back_populates="event",
        cascade="all, delete-orphan"
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
