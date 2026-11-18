"""Transactional order and inventory operations.

Each public operation commits one complete state change or rolls the session
back. PostgreSQL row locks are the production concurrency mechanism; mocked
tests do not establish their runtime behaviour.
"""
from __future__ import annotations

import secrets
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import OrderStatus
from app.models.order import Order
from app.models.ticket import Ticket, TicketStatus, TicketType

RESERVATION_TIMEOUT = timedelta(minutes=10)
MAX_TICKETS_PER_ORDER = 10


class OrderOperationError(Exception):
    """Expected domain failure suitable for translation at the API boundary."""

    status_code = 409


class TicketTypeUnavailable(OrderOperationError):
    status_code = 404


class InsufficientInventory(OrderOperationError):
    status_code = 400


class InventoryNeedsReconciliation(OrderOperationError):
    status_code = 409


class OrderNotFound(OrderOperationError):
    status_code = 404


class InvalidOrderTransition(OrderOperationError):
    status_code = 409


class InvalidReservationRequest(OrderOperationError):
    status_code = 422


class IdempotencyConflict(OrderOperationError):
    status_code = 409


@dataclass(frozen=True, slots=True)
class VerifiedPaymentFailure:
    """Provider-neutral receipt created only after a trusted verifier runs.

    No HTTP request accepts this object. Phase 3 must provide the verification
    adapter before any request path can construct or submit one.
    """

    evidence_reference: str


async def _one_or_none(session: AsyncSession, statement):
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def _find_idempotent_order(
    session: AsyncSession, user_id: UUID, idempotency_key: str
) -> Order | None:
    statement = (
        select(Order)
        .options(selectinload(Order.tickets))
        .where(Order.user_id == user_id, Order.idempotency_key == idempotency_key)
    )
    return await _one_or_none(session, statement)


def _validate_idempotent_replay(
    order: Order, *, ticket_type_id: UUID, quantity: int
) -> Order:
    if order.ticket_type_id != ticket_type_id or order.quantity != quantity:
        raise IdempotencyConflict("Idempotency-Key was already used for a different reservation")
    return order


async def reserve_tickets(
    session: AsyncSession,
    *,
    user_id: UUID,
    ticket_type_id: UUID,
    quantity: int,
    idempotency_key: str,
    now: datetime | None = None,
) -> Order:
    """Create a reservation and its tickets as one retry-safe transaction."""
    key = idempotency_key.strip()
    try:
        if not key or len(key) > 128:
            raise InvalidReservationRequest("Idempotency-Key must contain 1 to 128 characters")
        if quantity < 1 or quantity > MAX_TICKETS_PER_ORDER:
            raise InvalidReservationRequest(f"Quantity must be between 1 and {MAX_TICKETS_PER_ORDER}")

        prior = await _find_idempotent_order(session, user_id, key)
        if prior is not None:
            _validate_idempotent_replay(prior, ticket_type_id=ticket_type_id, quantity=quantity)
            await session.commit()
            return prior

        inventory_statement = (
            select(TicketType)
            .where(TicketType.id == ticket_type_id)
            .with_for_update()
        )
        ticket_type = await _one_or_none(session, inventory_statement)
        if ticket_type is None or ticket_type.is_active is not True:
            raise TicketTypeUnavailable("Ticket tier unavailable")
        if ticket_type.quantity_reserved is None or ticket_type.quantity_sold is None:
            raise InventoryNeedsReconciliation("Ticket inventory requires reconciliation")

        remaining = ticket_type.remaining_capacity
        if remaining is None:
            raise InventoryNeedsReconciliation("Ticket inventory requires reconciliation")
        if remaining < quantity:
            raise InsufficientInventory(f"Only {remaining} tickets remain")

        created_at = now or datetime.now(UTC)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        order = Order(
            id=uuid4(),
            user_id=user_id,
            ticket_type_id=ticket_type.id,
            quantity=quantity,
            unit_price=ticket_type.price,
            # Currency is intentionally unknown until the product's currency
            # source is decided. Never invent it during a reservation.
            currency=None,
            total_amount=ticket_type.price * quantity,
            status=OrderStatus.PENDING,
            payment_reference=f"PAY-{secrets.token_hex(6).upper()}",
            expires_at=created_at + RESERVATION_TIMEOUT,
            idempotency_key=key,
        )
        ticket_type.quantity_reserved += quantity
        order.tickets = [
            Ticket(
                id=uuid4(),
                ticket_type_id=ticket_type.id,
                order_id=order.id,
                ticket_code=f"TCK-{uuid4().hex[:20].upper()}",
                status=TicketStatus.RESERVED,
            )
            for _ in range(quantity)
        ]
        session.add(order)
        await session.flush()
        await session.commit()
        return order
    except IntegrityError as integrity_error:
        await session.rollback()
        # A concurrent retry may have won the unique (user, key) constraint.
        try:
            prior = await _find_idempotent_order(session, user_id, key)
        except Exception:
            await session.rollback()
            raise
        if prior is not None:
            try:
                _validate_idempotent_replay(prior, ticket_type_id=ticket_type_id, quantity=quantity)
                await session.commit()
                return prior
            except Exception:
                await session.rollback()
                raise
        await session.rollback()
        raise integrity_error
    except Exception:
        await session.rollback()
        raise


async def _lock_owned_order(
    session: AsyncSession, *, order_id: UUID, user_id: UUID | None
) -> Order:
    statement = select(Order).options(selectinload(Order.tickets)).where(Order.id == order_id)
    if user_id is not None:
        statement = statement.where(Order.user_id == user_id)
    order = await _one_or_none(session, statement.with_for_update())
    if order is None:
        raise OrderNotFound("Order not found")
    return order


async def _lock_inventory(session: AsyncSession, ticket_type_id: UUID) -> TicketType:
    statement = select(TicketType).where(TicketType.id == ticket_type_id).with_for_update()
    ticket_type = await _one_or_none(session, statement)
    if ticket_type is None:
        raise InventoryNeedsReconciliation("The order's ticket type is unavailable")
    if ticket_type.quantity_reserved is None or ticket_type.quantity_sold is None:
        raise InventoryNeedsReconciliation("Ticket inventory requires reconciliation")
    return ticket_type


def _assert_reserved_quantity(order: Order, ticket_type: TicketType) -> int:
    if order.ticket_type_id is None or order.quantity is None:
        raise InventoryNeedsReconciliation("Order has no recorded ticket type or quantity")
    if order.quantity < 1:
        raise InventoryNeedsReconciliation("Order has an invalid reservation quantity")
    if ticket_type.quantity_reserved is None or ticket_type.quantity_reserved < order.quantity:
        raise InventoryNeedsReconciliation("Reserved inventory is inconsistent with the order")
    return order.quantity


def _transition_pending(order: Order, target: OrderStatus) -> None:
    if order.status == target:
        return
    if order.status != OrderStatus.PENDING:
        raise InvalidOrderTransition(f"Cannot transition order from {order.status} to {target}")
    if target not in (OrderStatus.CANCELLED, OrderStatus.EXPIRED):
        raise InvalidOrderTransition(f"Unsupported order transition without payment evidence to {target}")
    order.status = target


async def cancel_pending_order(
    session: AsyncSession, *, order_id: UUID, user_id: UUID
) -> Order:
    """Release a pending reservation once; repeat cancellation is idempotent."""
    try:
        order = await _lock_owned_order(session, order_id=order_id, user_id=user_id)
        if order.status == OrderStatus.CANCELLED:
            await session.commit()
            return order
        if order.status != OrderStatus.PENDING:
            raise InvalidOrderTransition(f"Cannot cancel order in status {order.status}")
        if order.ticket_type_id is None:
            raise InventoryNeedsReconciliation("Order has no recorded ticket type")

        ticket_type = await _lock_inventory(session, order.ticket_type_id)
        quantity = _assert_reserved_quantity(order, ticket_type)
        ticket_type.quantity_reserved -= quantity
        _transition_pending(order, OrderStatus.CANCELLED)
        for ticket in order.tickets:
            if ticket.status == TicketStatus.RESERVED:
                ticket.status = TicketStatus.CANCELLED
        await session.commit()
        return order
    except Exception:
        await session.rollback()
        raise


async def record_verified_payment_failure(
    session: AsyncSession,
    *,
    order_id: UUID,
    evidence: VerifiedPaymentFailure,
    now: datetime | None = None,
) -> Order:
    """Record a trusted failed-payment result and release a pending hold once."""
    try:
        reference = evidence.evidence_reference.strip()
        if not reference or len(reference) > 255:
            raise InvalidReservationRequest("Payment evidence reference must contain 1 to 255 characters")
        order = await _lock_owned_order(session, order_id=order_id, user_id=None)
        if order.payment_evidence_reference == reference and order.status in (
            OrderStatus.CANCELLED,
            OrderStatus.PAYMENT_FAILED,
            OrderStatus.EXPIRED,
        ):
            await session.commit()
            return order
        if order.status in (OrderStatus.CANCELLED, OrderStatus.EXPIRED):
            if order.payment_evidence_reference is not None:
                raise InvalidOrderTransition("A different payment result is already recorded for this order")
            order.payment_evidence_reference = reference
            await session.commit()
            return order
        if order.status != OrderStatus.PENDING:
            raise InvalidOrderTransition(f"Cannot apply payment failure to order in status {order.status}")
        if order.ticket_type_id is None:
            raise InventoryNeedsReconciliation("Order has no recorded ticket type")

        ticket_type = await _lock_inventory(session, order.ticket_type_id)
        quantity = _assert_reserved_quantity(order, ticket_type)
        order.payment_evidence_reference = reference
        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        expires_at = order.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        ticket_type.quantity_reserved -= quantity
        if expires_at is not None and current_time >= expires_at:
            _transition_pending(order, OrderStatus.EXPIRED)
            ticket_status = TicketStatus.EXPIRED
        else:
            if order.status != OrderStatus.PENDING:
                raise InvalidOrderTransition(f"Cannot fail order in status {order.status}")
            order.status = OrderStatus.PAYMENT_FAILED
            ticket_status = TicketStatus.CANCELLED
        for ticket in order.tickets:
            if ticket.status == TicketStatus.RESERVED:
                ticket.status = ticket_status
        await session.commit()
        return order
    except Exception:
        await session.rollback()
        raise


async def expire_due_orders(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    batch_size: int = 100,
) -> int:
    """Expire one bounded batch, using skip-locked rows for competing workers."""
    if batch_size < 1 or batch_size > 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    cutoff = now or datetime.now(UTC)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=UTC)
    try:
        due_statement = (
            select(Order)
            .options(selectinload(Order.tickets))
            .where(
                Order.status == OrderStatus.PENDING,
                Order.expires_at.is_not(None),
                Order.expires_at <= cutoff,
            )
            .order_by(Order.expires_at, Order.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        due_result = await session.execute(due_statement)
        due_orders = list(due_result.scalars().all())
        ticket_type_ids = sorted(
            {order.ticket_type_id for order in due_orders if order.ticket_type_id is not None},
            key=str,
        )
        if not due_orders or not ticket_type_ids:
            await session.commit()
            return 0

        inventory_statement = (
            select(TicketType)
            .where(TicketType.id.in_(ticket_type_ids))
            .order_by(TicketType.id)
            .with_for_update()
        )
        inventory_result = await session.execute(inventory_statement)
        inventory = {item.id: item for item in inventory_result.scalars().all()}

        valid_by_type: dict[UUID, list[tuple[Order, int]]] = defaultdict(list)
        for order in due_orders:
            if order.ticket_type_id is None or order.quantity is None or order.quantity < 1:
                continue
            type_row = inventory.get(order.ticket_type_id)
            if type_row is None or type_row.quantity_reserved is None:
                continue
            valid_by_type[order.ticket_type_id].append((order, order.quantity))

        transitioned = 0
        for type_id, group in valid_by_type.items():
            type_row = inventory[type_id]
            release_quantity = sum(quantity for _, quantity in group)
            # Leave the group untouched rather than making a possibly corrupt
            # counter negative. Reconciliation can then diagnose the rows.
            if type_row.quantity_reserved is None or type_row.quantity_reserved < release_quantity:
                continue
            type_row.quantity_reserved -= release_quantity
            for order, _ in group:
                _transition_pending(order, OrderStatus.EXPIRED)
                for ticket in order.tickets:
                    if ticket.status == TicketStatus.RESERVED:
                        ticket.status = TicketStatus.EXPIRED
                transitioned += 1

        await session.commit()
        return transitioned
    except Exception:
        await session.rollback()
        raise
