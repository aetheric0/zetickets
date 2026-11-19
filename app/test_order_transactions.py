from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints.orders import checkout_order
from app.models.enums import OrderStatus
from app.models.order import Order
from app.models.ticket import Ticket, TicketStatus, TicketType
from app.services.orders import (
    IdempotencyConflict,
    InsufficientInventory,
    InventoryNeedsReconciliation,
    PaymentVerificationUnavailable,
    cancel_pending_order,
    expire_due_orders,
    record_payment_failure,
    reserve_tickets,
)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class FakeSession:
    """Scripted AsyncSession substitute; it never opens a connection."""

    def __init__(self, responses=(), *, flush_error=None):
        self.responses = list(responses)
        self.flush_error = flush_error
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        value = self.responses.pop(0)
        return value if isinstance(value, FakeResult) else FakeResult(value)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        if self.flush_error:
            raise self.flush_error

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def make_ticket_type(*, available=8, reserved=0, sold=0):
    return TicketType(
        id=uuid4(), event_id=uuid4(), name="General", price=Decimal("7.50"),
        quantity_available=available, quantity_reserved=reserved,
        quantity_sold=sold, is_active=True,
    )


def make_order(ticket_type, *, quantity=2, status=OrderStatus.PENDING, expires_at=None, key="retry-1"):
    order = Order(
        id=uuid4(), user_id=uuid4(), ticket_type_id=ticket_type.id,
        quantity=quantity, unit_price=Decimal("7.50"), currency=None,
        total_amount=Decimal("7.50") * quantity, status=status,
        payment_reference="internal-ref", expires_at=expires_at or datetime.now(UTC) + timedelta(minutes=5),
        idempotency_key=key, tickets=[],
    )
    order.tickets = [
        Ticket(id=uuid4(), ticket_type_id=ticket_type.id, order_id=order.id,
               ticket_code=f"ticket-{index}", status=TicketStatus.RESERVED)
        for index in range(quantity)
    ]
    return order


@pytest.mark.asyncio
async def test_reservation_updates_order_tickets_and_inventory_atomically():
    ticket_type = make_ticket_type()
    session = FakeSession([None, ticket_type])
    now = datetime(2030, 1, 1, tzinfo=UTC)

    order = await reserve_tickets(
        session, user_id=uuid4(), ticket_type_id=ticket_type.id,
        quantity=2, idempotency_key="request-abc", now=now,
    )

    assert session.commits == 1 and session.rollbacks == 0
    assert ticket_type.quantity_reserved == 2
    assert order.status is OrderStatus.PENDING
    assert order.quantity == 2
    assert order.expires_at == now + timedelta(minutes=10)
    assert order.currency is None
    assert len(order.tickets) == 2
    assert all(ticket.status is TicketStatus.RESERVED for ticket in order.tickets)


@pytest.mark.asyncio
async def test_idempotent_reservation_replay_does_not_reserve_twice():
    ticket_type = make_ticket_type(reserved=2)
    prior = make_order(ticket_type, key="same-key")
    session = FakeSession([prior])

    result = await reserve_tickets(
        session, user_id=prior.user_id, ticket_type_id=ticket_type.id,
        quantity=2, idempotency_key="same-key",
    )

    assert result is prior
    assert session.commits == 1 and session.rollbacks == 0
    assert ticket_type.quantity_reserved == 2
    assert len(session.statements) == 1


@pytest.mark.asyncio
async def test_idempotency_key_reuse_with_different_payload_conflicts():
    ticket_type = make_ticket_type(reserved=2)
    prior = make_order(ticket_type, key="same-key")
    session = FakeSession([prior])

    with pytest.raises(IdempotencyConflict):
        await reserve_tickets(
            session, user_id=prior.user_id, ticket_type_id=ticket_type.id,
            quantity=3, idempotency_key="same-key",
        )

    assert session.commits == 0 and session.rollbacks == 1


@pytest.mark.asyncio
async def test_insufficient_inventory_rolls_back_without_mutation():
    ticket_type = make_ticket_type(available=1)
    session = FakeSession([None, ticket_type])

    with pytest.raises(InsufficientInventory):
        await reserve_tickets(
            session, user_id=uuid4(), ticket_type_id=ticket_type.id,
            quantity=2, idempotency_key="too-many",
        )

    assert ticket_type.quantity_reserved == 0
    assert session.commits == 0 and session.rollbacks == 1


@pytest.mark.asyncio
async def test_concurrent_idempotency_unique_conflict_returns_winning_order():
    ticket_type = make_ticket_type()
    user_id = uuid4()
    winner = make_order(ticket_type, key="race-key")
    winner.user_id = user_id
    session = FakeSession(
        [None, ticket_type, winner],
        flush_error=IntegrityError("insert", {}, Exception("unique key")),
    )

    result = await reserve_tickets(
        session, user_id=user_id, ticket_type_id=ticket_type.id,
        quantity=2, idempotency_key="race-key",
    )

    assert result is winner
    assert session.rollbacks == 1 and session.commits == 1


@pytest.mark.asyncio
async def test_cancel_releases_inventory_and_is_idempotent():
    ticket_type = make_ticket_type(reserved=2)
    order = make_order(ticket_type)
    session = FakeSession([order, ticket_type])

    result = await cancel_pending_order(session, order_id=order.id, user_id=order.user_id)

    assert result.status is OrderStatus.CANCELLED
    assert ticket_type.quantity_reserved == 0
    assert all(ticket.status is TicketStatus.CANCELLED for ticket in order.tickets)
    assert session.commits == 1

    retry_session = FakeSession([order])
    await cancel_pending_order(retry_session, order_id=order.id, user_id=order.user_id)
    assert retry_session.commits == 1
    assert ticket_type.quantity_reserved == 0


@pytest.mark.asyncio
async def test_expiry_cleanup_releases_only_due_reservations_once():
    now = datetime(2030, 1, 1, tzinfo=UTC)
    ticket_type = make_ticket_type(reserved=3)
    due = make_order(ticket_type, quantity=2, expires_at=now - timedelta(seconds=1))
    session = FakeSession([[due], [ticket_type]])

    count = await expire_due_orders(session, now=now, batch_size=25)

    assert count == 1
    assert due.status is OrderStatus.EXPIRED
    assert ticket_type.quantity_reserved == 1
    assert all(ticket.status is TicketStatus.EXPIRED for ticket in due.tickets)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_payment_failure_without_provider_verification_fails_closed():
    ticket_type = make_ticket_type(reserved=2)
    order = make_order(ticket_type)
    session = FakeSession()

    with pytest.raises(PaymentVerificationUnavailable):
        await record_payment_failure(session, order_id=order.id)

    assert order.status is OrderStatus.PENDING
    assert order.payment_evidence_reference is None
    assert ticket_type.quantity_reserved == 2
    assert all(ticket.status is TicketStatus.RESERVED for ticket in order.tickets)
    assert session.statements == []
    assert session.commits == 0 and session.rollbacks == 0


@pytest.mark.asyncio
async def test_forged_payment_evidence_is_not_accepted_by_order_service():
    ticket_type = make_ticket_type(reserved=1)
    order = make_order(ticket_type, quantity=1)
    session = FakeSession()

    with pytest.raises(TypeError):
        await record_payment_failure(session, order_id=order.id, evidence=object())

    assert order.status is OrderStatus.PENDING
    assert order.payment_evidence_reference is None
    assert ticket_type.quantity_reserved == 1
    assert all(ticket.status is TicketStatus.RESERVED for ticket in order.tickets)
    assert session.statements == []
    assert session.commits == 0 and session.rollbacks == 0


@pytest.mark.asyncio
async def test_reservation_database_failure_rolls_back():
    ticket_type = make_ticket_type()
    session = FakeSession([None, ticket_type], flush_error=RuntimeError("simulated insert failure"))

    with pytest.raises(RuntimeError, match="simulated insert failure"):
        await reserve_tickets(
            session, user_id=uuid4(), ticket_type_id=ticket_type.id,
            quantity=1, idempotency_key="failure-test",
        )

    assert session.commits == 0 and session.rollbacks == 1


@pytest.mark.asyncio
async def test_empty_expiry_batch_is_safe_to_retry():
    session = FakeSession([[]])
    assert await expire_due_orders(session) == 0
    assert session.commits == 1 and session.rollbacks == 0


@pytest.mark.asyncio
async def test_expiry_leaves_inconsistent_inventory_untouched_for_reconciliation():
    now = datetime(2030, 1, 1, tzinfo=UTC)
    ticket_type = make_ticket_type(reserved=1)
    due = make_order(ticket_type, quantity=2, expires_at=now - timedelta(seconds=1))
    session = FakeSession([[due], [ticket_type]])

    count = await expire_due_orders(session, now=now)

    assert count == 0
    assert due.status is OrderStatus.PENDING
    assert ticket_type.quantity_reserved == 1
    assert session.commits == 1


@pytest.mark.asyncio
async def test_cancel_inconsistent_inventory_rolls_back():
    ticket_type = make_ticket_type(reserved=1)
    order = make_order(ticket_type, quantity=2)
    session = FakeSession([order, ticket_type])

    with pytest.raises(InventoryNeedsReconciliation):
        await cancel_pending_order(session, order_id=order.id, user_id=order.user_id)

    assert order.status is OrderStatus.PENDING
    assert ticket_type.quantity_reserved == 1
    assert session.commits == 0 and session.rollbacks == 1


def test_locking_statements_compile_to_postgresql_lock_syntax():
    reserve_statement = select(TicketType).with_for_update()
    expiry_statement = select(Order).with_for_update(skip_locked=True)
    reserve_sql = str(reserve_statement.compile(dialect=postgresql.dialect()))
    expiry_sql = str(expiry_statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in reserve_sql
    assert "FOR UPDATE SKIP LOCKED" in expiry_sql


def test_database_constraints_cover_idempotency_and_inventory_invariants():
    order_constraint_names = {constraint.name for constraint in Order.__table__.constraints}
    inventory_constraint_names = {constraint.name for constraint in TicketType.__table__.constraints}
    assert "uq_orders_user_id_idempotency_key" in order_constraint_names
    assert "uq_orders_payment_evidence_reference" in order_constraint_names
    assert "ck_orders_quantity_positive" in order_constraint_names
    assert "ck_ticket_types_reserved_nonnegative" in inventory_constraint_names
    assert "ck_ticket_types_sold_nonnegative" in inventory_constraint_names


@pytest.mark.asyncio
async def test_checkout_never_completes_without_payment_evidence():
    ticket_type = make_ticket_type(reserved=1)
    order = make_order(ticket_type, quantity=1)
    session = FakeSession()

    with pytest.raises(HTTPException) as raised:
        await checkout_order(order.id, session, object())

    assert raised.value.status_code == 409
    assert "trusted payment evidence" in raised.value.detail
    assert order.status is OrderStatus.PENDING
    assert ticket_type.quantity_reserved == 1
    assert all(ticket.status is TicketStatus.RESERVED for ticket in order.tickets)
    assert session.statements == [] and session.commits == 0
