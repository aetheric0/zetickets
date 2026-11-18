from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.enums import OrderStatus
from app.schemas.ticket import TicketResponse


class ReserveTicketsRequest(BaseModel):
    ticket_type_id: UUID
    quantity: int = Field(..., gt=0, le=10, description="Max 10 tickets per transaction")

class ReservationResponse(BaseModel):
    order_id: UUID = Field(validation_alias=AliasChoices("order_id", "id"))
    ticket_type_id: UUID
    quantity: int
    total_amount: Decimal
    status: OrderStatus
    expires_at: datetime | None
    unit_price: Decimal | None = None
    currency: str | None = None

    model_config = ConfigDict(from_attributes=True)

class OrderDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    total_amount: Decimal
    ticket_type_id: UUID | None = None
    quantity: int | None = None
    unit_price: Decimal | None = None
    currency: str | None = None
    expires_at: datetime | None = None
    status: OrderStatus
    created_at: datetime
    tickets: list[TicketResponse] = []

    model_config = ConfigDict(from_attributes=True)
