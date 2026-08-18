import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, SessionDep
from app.models.order import Order as OrderModel
from app.models.order import OrderStatus
from app.models.ticket import Ticket as TicketModel
from app.models.ticket import TicketStatus
from app.models.ticket import TicketType as TicketTypeModel
from app.schemas.order import (
    OrderDetailResponse,
    ReservationResponse,
    ReserveTicketsRequest,
)

router = APIRouter()

RESERVATION_TIMEOUT_MINUTES = 10

@router.post(
    "/reserve",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED
)
async def reserve_tickets(
    req: ReserveTicketsRequest,
    db: SessionDep,
    current_user: CurrentUser
) -> Any:
    """
    Atomically reserve tickets with row-level lock (FOR UPDATE).
    Prevents overbooking during high-concurrency ticket drops.
    """
    # 0. Lock the TicketType row for concurrency safety
    stmt = (
        select(TicketTypeModel)
        .where(TicketTypeModel.id == req.ticket_type_id, TicketTypeModel.is_active.is_(True))
        .with_for_update()
    )
    result = await db.execute(stmt)
    ticket_type = result.scalar_one_or_none()

    if not ticket_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket tier unavailable"
        )

    if not ticket_type.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_BAD_REQUEST,
            detail="Sales for this ticket tier are currently paused",
        )

    # 1. Check real remaining capacity
    if ticket_type.remaining_capacity < req.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {ticket_type.remaining_capacity}tickets remaining for this tier.",
        )
    # 3. Calculate total and set expiration
    total_amount = ticket_type.price * req.quantity
    expires_at = datetime.now(UTC) + timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)

    # 4. Create pending order & adjust reserved counter
    order = OrderModel(
        user_id=current_user.id,
        ticket_type_id=ticket_type.id,
        quantity=req.quantity,
        total_amount=total_amount,
        status=OrderStatus.PENDING,
        payment_reference=f"PAY-{uuid4().hex[:12].upper()}",
        expires_at=expires_at,
    )
    ticket_type.quantity_reserved += req.quantity
    db.add(order)
    await db.flush()

    # 5. Generate reserved ticket instances
    for _ in range(req.quantity):
        ticket = TicketModel(
            ticket_type_id=ticket_type.id,
            order_id=order.id,
            ticket_code=f"TCK-{uuid4().hex[:10].upper()}",
            status="reserved",
        )
        db.add(ticket)
    await db.commit()

    order_stmt = (
        select(OrderModel)
        .options(selectinload(OrderModel.tickets))
        .where(OrderModel.id == order.id)
    )
    result = await db.execute(order_stmt)

    return result.scalar_one()

@router.post(
    "/{order_id}/checkout",
    response_model=OrderDetailResponse,
)
async def checkout_order(
    order_id: UUID,
    db: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Confirm payment and transition order from PENDING TO COMPLETED.
    Generates unique verifiable ticket tokens.
    """
    stmt = select(OrderModel).options(selectinload(OrderModel.tickets)).where(OrderModel.id == order_id, OrderModel.user_id == current_user.id).with_for_update()
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or non-pending order. Order status is {order.status}"
        )

    # Lock ticket_type row before checking expiration and counter transition
    tt_stmt = (
        select(TicketTypeModel)
        .where(TicketTypeModel.id == order.ticket_type_id)
        .with_for_update()
    )
    tt_result = await db.execute(tt_stmt)
    ticket_type = tt_result.scalar_one()

    # Verify reservation expiration
    created_at = order.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    order_expires_at: datetime = created_at + timedelta(
        minutes=RESERVATION_TIMEOUT_MINUTES
    )
    current_time = datetime.now(UTC)
    order_qty = int(order.total_amount)
    if current_time > order_expires_at:
        order.status = OrderStatus.EXPIRED
        ticket_type.quantity_reserved -= order_qty
        for ticket in order.tickets:
            ticket.status = TicketStatus.EXPIRED
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation expired",
        )

    # Transition counters: reserved -> sold(uses order.quantity, NOT total_amount)
    ticket_type.quantity_reserved -= order_qty
    ticket_type.quantity_sold += order_qty
    order.status = OrderStatus.COMPLETED

    # Update existing reserved tickets to valid active status with unique tokens
    for ticket in order.tickets:
        ticket.status = TicketStatus.ISSUED
        ticket.ticket_code = f"ZET-{secrets.token_hex(6).upper()}"
    await db.commit()

    # # Count tickets per tier in this order
    # tier_counts: dict[UUID, int] = {}
    # for ticket in order.tickets:
    #     ticket.status = "valid"
    #     tier_counts[ticket.ticket_type_id] = tier_counts.get(ticket.ticket_type_id, 0) + 1
    # Generate individual tickets


    # Load with tickets relation
    result_stmt = select(OrderModel).options(selectinload(OrderModel.tickets)).where(OrderModel.id == order.id)
    result = await db.execute(result_stmt)
    return result.scalar_one()