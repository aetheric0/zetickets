from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ticket import TicketTypeCreate, TicketTypeResponse


class EventBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    location: str = Field(..., max_length=255)
    start_time: datetime
    end_time: datetime

class EventCreate(EventBase):
    ticket_types: list[TicketTypeCreate] = []

class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    location: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    is_published: bool | None = None

class EventResponse(EventBase):
    id: UUID
    organizer_id: UUID
    is_published: bool
    created_at: datetime
    updated_at: datetime
    ticket_types: list[TicketTypeResponse] = []

    model_config = ConfigDict(from_attributes=True)

