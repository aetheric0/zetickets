from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ticket import TicketStatus


class TicketTypeBase(BaseModel):
    name: str = Field(..., max_length=100, examples=["Regular", "VIP Pass", "Early Bird General"])
    description: str | None = Field(None, max_length=500)
    price: Decimal = Field(..., ge=Decimal("0.00"), description="Price in base currency")
    capacity: int = Field(..., validation_alias="quantity_avaialable", ge=1, description="Total tickets available for purchase")

class TicketTypeCreate(TicketTypeBase):
    is_active: bool = True

class TicketTypeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: Decimal | None = Field(None, ge=Decimal("0.00"))
    capacity: int | None = Field(None, ge=1)
    is_active: bool | None = None

class TicketTypeResponse(TicketTypeBase):
    id: UUID
    event_id: UUID
    capacity: int
    quantity_reserved: int
    quantity_sold: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TicketResponse(BaseModel):
    id: UUID
    ticket_type_id: UUID
    order_id: UUID
    ticket_code: str
    status: TicketStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)