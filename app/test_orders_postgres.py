"""PostgreSQL-only integration tests for transactional order operations.

These tests never read application settings or .env. They skip unless an
explicit URL and cluster identifier for the dedicated disposable database are
provided, and fail before operations if the live server identity differs.
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event as sqla_event
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.enums import OrderStatus
from app.models.event import Event
from app.models.order import Order
from app.models.ticket import Ticket, TicketStatus, TicketType
from app.models.user import User, UserRole
from app.services.orders import (
    IdempotencyConflict,
    InsufficientInventory,
    VerifiedPaymentFailure,
    cancel_pending_order,
    expire_due_orders,
    record_verified_payment_failure,
    reserve_tickets,
)

EXPECTED_DATABASE = "zetickets_phase2_test"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 55439
EXPECTED_USERNAME = "zetickets_test_owner"
EXPECTED_HEAD = "a2d4e6f8091b"


def explicit_test_url() -> str:
    raw_url = os.environ.get("ZETICKETS_TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("Set ZETICKETS_TEST_DATABASE_URL explicitly for the disposable PostgreSQL test database")
    parsed = make_url(raw_url)
    identity = (parsed.drivername, parsed.host, parsed.port, parsed.database, parsed.username)
    expected = ("postgresql+asyncpg", EXPECTED_HOST, EXPECTED_PORT, EXPECTED_DATABASE, EXPECTED_USERNAME)
    if identity != expected or not parsed.password:
        pytest.fail("Refusing PostgreSQL test connection: URL does not identify the dedicated test database")
    if not os.environ.get("ZETICKETS_TEST_CLUSTER_ID"):
        pytest.fail("ZETICKETS_TEST_CLUSTER_ID is required to verify the disposable PostgreSQL cluster")
    return raw_url


async def assert_test_database_identity(connection) -> None:
    result = await connection.execute(
        text(
            "SELECT current_database() AS database, host(inet_server_addr()) AS host, "
            "inet_server_port() AS port, current_user AS username, "
            "(pg_control_system()).system_identifier::text AS cluster_id, "
            "current_setting('server_version_num')::integer AS version_num"
        )
    )
    identity = result.mappings().one()
    assert identity["database"] == EXPECTED_DATABASE
    assert identity["host"] == EXPECTED_HOST
    assert identity["port"] == EXPECTED_PORT
    assert identity["username"] == EXPECTED_USERNAME
    assert identity["cluster_id"] == os.environ["ZETICKETS_TEST_CLUSTER_ID"]
    assert identity["version_num"] >= 140000


@pytest_asyncio.fixture
async def pg_engine():
    url = explicit_test_url()
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await assert_test_database_identity(connection)
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != EXPECTED_HEAD:
                pytest.fail(f"Expected disposable test database at {EXPECTED_HEAD}, got {revision!r}")
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def pg_sessions(pg_engine):
    return async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


async def seed_inventory(pg_sessions, *, capacity: int = 8):
    user_id = uuid4()
    event_id = uuid4()
    ticket_type_id = uuid4()
    now = datetime.now(UTC)
    async with pg_sessions() as session:
        user = User(
            id=user_id,
            email=f"{user_id.hex}@phase2.invalid",
            hashed_password="test-hash-not-a-credential",
            full_name="Disposable Phase 2 Test",
            role=UserRole.ATTENDEE,
            is_active=True,
            is_superuser=False,
        )
        event_row = Event(
            id=event_id,
            title="Disposable Phase 2 Event",
            location="Test only",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=2),
            organizer_id=user_id,
            is_published=False,
        )
        ticket_type = TicketType(
            id=ticket_type_id,
            event_id=event_id,
            name="Test tier",
            price=Decimal("17.25"),
            quantity_available=capacity,
            quantity_reserved=0,
            quantity_sold=0,
            is_active=True,
        )
        session.add_all([user, event_row, ticket_type])
        await session.commit()
    return user_id, event_id, ticket_type_id


async def reserve(pg_sessions, *, user_id, ticket_type_id, quantity=1, key=None, now=None):
    async with pg_sessions() as session:
        return await reserve_tickets(
            session,
            user_id=user_id,
            ticket_type_id=ticket_type_id,
            quantity=quantity,
            idempotency_key=key or f"phase2-{uuid4().hex}",
            now=now,
        )


async def read_inventory(pg_sessions, ticket_type_id):
    async with pg_sessions() as session:
        return await session.get(TicketType, ticket_type_id)


@pytest.mark.asyncio
async def test_reservation_commits_order_tickets_and_inventory(pg_sessions):
    user_id, _, ticket_type_id = await seed_inventory(pg_sessions)
    order = await reserve(pg_sessions, user_id=user_id, ticket_type_id=ticket_type_id, quantity=3)

    async with pg_sessions() as session:
        persisted_order = await session.scalar(
            select(Order).where(Order.id == order.id).options()
        )
        tickets = list((await session.scalars(select(Ticket).where(Ticket.order_id == order.id))).all())
        inventory = await session.get(TicketType, ticket_type_id)
    assert persisted_order is not None
    assert persisted_order.status is OrderStatus.PENDING
    assert persisted_order.quantity == 3
    assert len(tickets) == 3
    assert all(ticket.status is TicketStatus.RESERVED for ticket in tickets)
    assert inventory.quantity_reserved == 3


@pytest.mark.asyncio
async def test_reservation_flush_failure_rolls_back_all_writes(pg_sessions):
    user_id, _, ticket_type_id = await seed_inventory(pg_sessions)
    session = pg_sessions()

    def fail_before_flush(sync_session, flush_context, instances):
        raise RuntimeError("injected disposable-test flush failure")

    sqla_event.listen(session.sync_session, "before_flush", fail_before_flush)
    try:
        with pytest.raises(RuntimeError, match="injected disposable-test flush failure"):
            await reserve_tickets(
                session,
                user_id=user_id,
                ticket_type_id=ticket_type_id,
                quantity=2,
                idempotency_key=f"rollback-{uuid4().hex}",
            )
    finally:
        sqla_event.remove(session.sync_session, "before_flush", fail_before_flush)
        await session.close()

    async with pg_sessions() as verify:
        inventory = await verify.get(TicketType, ticket_type_id)
        orders = list((await verify.scalars(select(Order).where(Order.ticket_type_id == ticket_type_id))).all())
        tickets = list((await verify.scalars(select(Ticket).where(Ticket.ticket_type_id == ticket_type_id))).all())
    assert inventory.quantity_reserved == 0
    assert orders == []
    assert tickets == []


@pytest.mark.asyncio
async def test_cancellation_releases_inventory_once(pg_sessions):
    user_id, _, ticket_type_id = await seed_inventory(pg_sessions)
    order = await reserve(pg_sessions, user_id=user_id, ticket_type_id=ticket_type_id, quantity=2)
    async with pg_sessions() as session:
        await cancel_pending_order(session, order_id=order.id, user_id=user_id)
    async with pg_sessions() as session:
        await cancel_pending_order(session, order_id=order.id, user_id=user_id)
    inventory = await read_inventory(pg_sessions, ticket_type_id)
    async with pg_sessions() as session:
        saved_order = await session.get(Order, order.id)
        tickets = list((await session.scalars(select(Ticket).where(Ticket.order_id == order.id))).all())
    assert inventory.quantity_reserved == 0
    assert saved_order.status is OrderStatus.CANCELLED
    assert all(ticket.status is TicketStatus.CANCELLED for ticket in tickets)


@pytest.mark.asyncio
async def test_expiry_cleanup_releases_inventory_once(pg_sessions):
    user_id, _, ticket_type_id = await seed_inventory(pg_sessions)
    order = await reserve(
        pg_sessions,
        user_id=user_id,
        ticket_type_id=ticket_type_id,
        quantity=2,
        now=datetime.now(UTC) - timedelta(hours=1),
    )
    async with pg_sessions() as session:
        assert await expire_due_orders(session, batch_size=20) == 1
    async with pg_sessions() as session:
        assert await expire_due_orders(session, batch_size=20) == 0
    inventory = await read_inventory(pg_sessions, ticket_type_id)
    async with pg_sessions() as session:
        saved_order = await session.get(Order, order.id)
    assert inventory.quantity_reserved == 0
    assert saved_order.status is OrderStatus.EXPIRED


@pytest.mark.asyncio
async def test_payment_failure_releases_inventory_once(pg_sessions):
    user_id, _, ticket_type_id = await seed_inventory(pg_sessions)
    order = await reserve(pg_sessions, user_id=user_id, ticket_type_id=ticket_type_id, quantity=2)
    evidence = VerifiedPaymentFailure(f"verified-decline-{uuid4().hex}")
    async with pg_sessions() as session:
        await record_verified_payment_failure(session, order_id=order.id, evidence=evidence)
    async with pg_sessions() as session:
        await record_verified_payment_failure(session, order_id=order.id, evidence=evidence)
    inventory = await read_inventory(pg_sessions, ticket_type_id)
    async with pg_sessions() as session:
        saved_order = await session.get(Order, order.id)
    assert inventory.quantity_reserved == 0
    assert saved_order.status is OrderStatus.PAYMENT_FAILED
    assert saved_order.payment_evidence_reference == evidence.evidence_reference


@pytest.mark.asyncio
async def test_same_key_retry_returns_original_without_double_reservation(pg_sessions):
    user_id, _, ticket_type_id = await seed_inventory(pg_sessions)
    key = f"same-{uuid4().hex}"
    original = await reserve(pg_sessions, user_id=user_id, ticket_type_id=ticket_type_id, quantity=2, key=key)
    replay = await reserve(pg_sessions, user_id=user_id, ticket_type_id=ticket_type_id, quantity=2, key=key)
    inventory = await read_inventory(pg_sessions, ticket_type_id)
    assert replay.id == original.id
    assert inventory.quantity_reserved == 2


@pytest.mark.asyncio
async def test_same_key_different_payload_is_rejected(pg_sessions):
    user_id, _, ticket_type_id = await seed_inventory(pg_sessions)
    key = f"mismatch-{uuid4().hex}"
    await reserve(pg_sessions, user_id=user_id, ticket_type_id=ticket_type_id, quantity=1, key=key)
    async with pg_sessions() as session:
        with pytest.raises(IdempotencyConflict):
            await reserve_tickets(
                session,
                user_id=user_id,
                ticket_type_id=ticket_type_id,
                quantity=2,
                idempotency_key=key,
            )
    inventory = await read_inventory(pg_sessions, ticket_type_id)
    assert inventory.quantity_reserved == 1


@pytest.mark.asyncio
async def test_concurrent_reservations_do_not_exceed_capacity(pg_sessions):
    user_a, _, ticket_type_id = await seed_inventory(pg_sessions, capacity=1)
    user_b, _, _ = await seed_inventory(pg_sessions, capacity=1)

    async def request(user_id):
        async with pg_sessions() as session:
            return await reserve_tickets(
                session,
                user_id=user_id,
                ticket_type_id=ticket_type_id,
                quantity=1,
                idempotency_key=f"capacity-{uuid4().hex}",
            )

    results = await asyncio.gather(request(user_a), request(user_b), return_exceptions=True)
    assert sum(isinstance(result, Order) for result in results) == 1
    assert sum(isinstance(result, InsufficientInventory) for result in results) == 1
    inventory = await read_inventory(pg_sessions, ticket_type_id)
    assert inventory.quantity_reserved == 1


@pytest.mark.asyncio
async def test_concurrent_same_key_requests_create_one_order(pg_sessions):
    user_id, _, ticket_type_id = await seed_inventory(pg_sessions, capacity=5)
    key = f"concurrent-{uuid4().hex}"

    async def request():
        async with pg_sessions() as session:
            return await reserve_tickets(
                session,
                user_id=user_id,
                ticket_type_id=ticket_type_id,
                quantity=2,
                idempotency_key=key,
            )

    first, second = await asyncio.gather(request(), request())
    inventory = await read_inventory(pg_sessions, ticket_type_id)
    async with pg_sessions() as session:
        orders = list((await session.scalars(select(Order).where(Order.idempotency_key == key))).all())
    assert first.id == second.id
    assert len(orders) == 1
    assert inventory.quantity_reserved == 2


@pytest.mark.asyncio
async def test_skip_locked_expiry_worker_does_not_claim_locked_order(pg_sessions):
    user_id, _, ticket_type_id = await seed_inventory(pg_sessions)
    order = await reserve(
        pg_sessions,
        user_id=user_id,
        ticket_type_id=ticket_type_id,
        now=datetime.now(UTC) - timedelta(hours=1),
    )
    locker = pg_sessions()
    await locker.execute(select(Order).where(Order.id == order.id).with_for_update())
    try:
        async with pg_sessions() as worker:
            assert await expire_due_orders(worker, batch_size=10) == 0
    finally:
        await locker.rollback()
        await locker.close()

    async with pg_sessions() as worker:
        assert await expire_due_orders(worker, batch_size=10) == 1
    inventory = await read_inventory(pg_sessions, ticket_type_id)
    assert inventory.quantity_reserved == 0


@pytest.mark.asyncio
async def test_migrated_schema_enums_constraints_fks_and_metadata_match(pg_engine):
    async with pg_engine.connect() as connection:
        enums = await connection.run_sync(lambda sync: inspect(sync).get_enums(schema="public"))
        tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names(schema="public"))
        order_fks = await connection.run_sync(lambda sync: inspect(sync).get_foreign_keys("orders"))
        order_uniques = await connection.run_sync(lambda sync: inspect(sync).get_unique_constraints("orders"))
        order_checks = await connection.run_sync(lambda sync: inspect(sync).get_check_constraints("orders"))
        ticket_checks = await connection.run_sync(lambda sync: inspect(sync).get_check_constraints("ticket_types"))
        order_columns = await connection.run_sync(lambda sync: inspect(sync).get_columns("orders"))
        event_columns = await connection.run_sync(lambda sync: inspect(sync).get_columns("events"))
        type_columns = await connection.run_sync(lambda sync: inspect(sync).get_columns("ticket_types"))
        user_columns = await connection.run_sync(lambda sync: inspect(sync).get_columns("users"))

        enum_map = {enum["name"]: set(enum["labels"]) for enum in enums}
        assert enum_map["orderstatus"] == {status.name for status in OrderStatus}
        assert enum_map["ticketstatus"] == {status.name for status in TicketStatus}
        assert enum_map["user_role_enum"] == {role.value for role in UserRole}
        assert {"users", "events", "orders", "ticket_types", "tickets", "organizer_profiles"} <= set(tables)
        assert any(fk["constrained_columns"] == ["ticket_type_id"] and fk["referred_table"] == "ticket_types" for fk in order_fks)
        assert {unique["name"] for unique in order_uniques} >= {
            "uq_orders_user_id_idempotency_key",
            "uq_orders_payment_evidence_reference",
        }
        assert {check["name"] for check in order_checks} >= {"ck_orders_quantity_positive"}
        assert {check["name"] for check in ticket_checks} >= {
            "ck_ticket_types_reserved_nonnegative",
            "ck_ticket_types_sold_nonnegative",
        }
        assert {column["name"] for column in order_columns} >= {
            "quantity", "unit_price", "currency", "expires_at", "idempotency_key", "payment_evidence_reference"
        }
        assert next(column for column in order_columns if column["name"] == "quantity")["nullable"]
        assert next(column for column in event_columns if column["name"] == "is_published")["nullable"]
        assert next(column for column in type_columns if column["name"] == "quantity_sold")["nullable"]
        assert next(column for column in type_columns if column["name"] == "is_active")["nullable"]
        assert next(column for column in user_columns if column["name"] == "full_name")["nullable"]
        assert not next(column for column in user_columns if column["name"] == "is_superuser")["nullable"]

        def compare(sync_connection):
            from alembic.autogenerate import compare_metadata
            from alembic.migration import MigrationContext

            return compare_metadata(MigrationContext.configure(sync_connection), Base.metadata)

        differences = await connection.run_sync(compare)
    assert differences == []
