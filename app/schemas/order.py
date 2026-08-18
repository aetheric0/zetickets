from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ticket import TicketResponse


class OrderStatus(str, PyEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

class ReserveTicketsRequest(BaseModel):
    ticket_type_id: UUID
    quantity: int = Field(..., gt=0, le=10, description="Max 10 tickets per transaction")

class ReservationResponse(BaseModel):
    order_id: UUID
    ticket_type_id: UUID
    quantity: int
    total_amount: Decimal
    status: OrderStatus
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)

class OrderDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    total_amount: Decimal
    status: OrderStatus
    created_at: datetime
    tickets: list[TicketResponse] = []

    model_config = ConfigDict(from_attributes=True)