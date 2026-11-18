from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app.core.deps import CurrentUser, SessionDep
from app.schemas.order import OrderDetailResponse, ReservationResponse, ReserveTicketsRequest
from app.services.orders import OrderOperationError, reserve_tickets as create_reservation

router = APIRouter()


@router.post("/reserve", response_model=ReservationResponse, status_code=201)
async def reserve_tickets(
    req: ReserveTicketsRequest,
    db: SessionDep,
    current_user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
) -> Any:
    try:
        return await create_reservation(
            db,
            user_id=current_user.id,
            ticket_type_id=req.ticket_type_id,
            quantity=req.quantity,
            idempotency_key=idempotency_key,
        )
    except OrderOperationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/{order_id}/checkout", response_model=OrderDetailResponse)
async def checkout_order(
    order_id: UUID,
    db: SessionDep,
    current_user: CurrentUser,
) -> Any:
    # Keep the existing operation closed until a trusted payment verifier is
    # supplied by Phase 3. A client request alone cannot complete an order.
    del order_id, db, current_user
    raise HTTPException(
        status_code=409,
        detail="Checkout cannot complete an order without trusted payment evidence; the verifier is not configured",
    )
