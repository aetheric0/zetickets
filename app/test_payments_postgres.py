"""PostgreSQL integration tests; skip unless the guarded disposable DB is explicit."""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url

from app.models.base import Base
from app.models.enums import (
    PaymentAttemptStatus,
    PaymentEnvironment,
    ReconciliationDiscrepancyType,
    ReconciliationStatus,
    RefundStatus,
    WebhookAuthenticationStatus,
    WebhookProcessingStatus,
)
from app.models.event import Event
from app.models.order import Order
from app.models.payment import PaymentAttempt, PaymentFulfillment, ReconciliationRecord, Refund, WebhookEvent
from app.models.ticket import TicketType
from app.models.user import User, UserRole

EXPECTED_DATABASE = "zetickets_phase2_test"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 55439
EXPECTED_USERNAME = "zetickets_test_owner"
EXPECTED_HEAD = "c7e2a4b19d60"


def explicit_url() -> str:
    url = os.environ.get("ZETICKETS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set explicit disposable ZETICKETS_TEST_DATABASE_URL for PostgreSQL payment tests")
    parsed = make_url(url)
    if (parsed.drivername, parsed.host, parsed.port, parsed.database, parsed.username) != (
        "postgresql+asyncpg", EXPECTED_HOST, EXPECTED_PORT, EXPECTED_DATABASE, EXPECTED_USERNAME
    ) or not parsed.password:
        pytest.fail("Refusing PostgreSQL test connection: URL does not identify the dedicated disposable database")
    if not os.environ.get("ZETICKETS_TEST_CLUSTER_ID"):
        pytest.fail("Dedicated PostgreSQL cluster identity is required")
    return url


async def assert_identity(connection) -> None:
    result = await connection.execute(text(
        "SELECT current_database() AS db, host(inet_server_addr()) AS host, "
        "inet_server_port() AS port, current_user AS username, "
        "(pg_control_system()).system_identifier::text AS cluster_id"
    ))
    row = result.mappings().one()
    assert (row["db"], row["host"], row["port"], row["username"]) == (
        EXPECTED_DATABASE, EXPECTED_HOST, EXPECTED_PORT, EXPECTED_USERNAME
    )
    assert row["cluster_id"] == os.environ["ZETICKETS_TEST_CLUSTER_ID"]


@pytest_asyncio.fixture
async def sessions():
    engine = create_async_engine(explicit_url(), pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await assert_identity(connection)
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != EXPECTED_HEAD:
                pytest.fail(f"Expected dedicated disposable database at {EXPECTED_HEAD}; found {revision!r}")
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


async def seed_order(sessions) -> Order:
    uid, event_id, type_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    async with sessions() as session:
        session.add(User(
            id=uid, email=f"{uid.hex}@payment-test.invalid", hashed_password="test-only-hash",
            role=UserRole.ATTENDEE, is_active=True, is_superuser=False,
        ))
        session.add(Event(
            id=event_id, title="Disposable payment test", location="test",
            start_time=now + timedelta(days=1), end_time=now + timedelta(days=1, hours=1),
            organizer_id=uid, is_published=False,
        ))
        session.add(TicketType(
            id=type_id, event_id=event_id, name="test", price=Decimal("10.00"),
            quantity_available=10, quantity_reserved=0, quantity_sold=0, is_active=True,
        ))
        order = Order(
            user_id=uid, ticket_type_id=type_id, quantity=1, unit_price=Decimal("10.00"),
            currency="KES", total_amount=Decimal("10.00"), payment_reference=f"ord-{uuid4().hex}",
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order


def attempt(order_id, *, idem=None, ref=None, amount=1000, currency="KES", status=PaymentAttemptStatus.PENDING):
    token = uuid4().hex
    return PaymentAttempt(
        order_id=order_id, provider="paystack", provider_account="test-merchant",
        environment=PaymentEnvironment.TEST, client_reference=f"client-{token}",
        provider_reference=ref, idempotency_key=idem or f"idem-{token}",
        amount_minor=amount, currency=currency, status=status,
    )


@pytest.mark.asyncio
async def test_metadata_matches_migrated_postgresql_schema_and_enum_labels(sessions):
    async with sessions() as session:
        def inspect_sync(sync_connection):
            inspector = inspect(sync_connection)
            for table_name in (
                "payment_attempts", "payment_fulfillments", "webhook_events",
                "payment_refunds", "payment_reconciliation_records",
            ):
                model_table = Base.metadata.tables[table_name]
                assert {column["name"] for column in inspector.get_columns(table_name)} == set(model_table.columns.keys())
                assert {index["name"] for index in inspector.get_indexes(table_name) if not index.get("duplicates_constraint")} == {
                    index.name for index in model_table.indexes
                }
                actual_fks = {
                    (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]), fk["options"].get("ondelete"))
                    for fk in inspector.get_foreign_keys(table_name)
                }
                expected_fks = {
                    (tuple(element.parent.name for element in fk.elements), fk.elements[0].column.table.name,
                     tuple(element.column.name for element in fk.elements), fk.ondelete)
                    for fk in model_table.foreign_key_constraints
                }
                assert actual_fks == expected_fks
            return inspector.get_enums()

        connection = await session.connection()
        enums = await connection.run_sync(inspect_sync)
        labels = {item["name"]: item["labels"] for item in enums}
        expected_enums = {
            "payment_attempt_status": PaymentAttemptStatus,
            "payment_environment": PaymentEnvironment,
            "webhook_authentication_status": WebhookAuthenticationStatus,
            "webhook_processing_status": WebhookProcessingStatus,
            "refund_status": RefundStatus,
            "reconciliation_status": ReconciliationStatus,
            "reconciliation_discrepancy_type": ReconciliationDiscrepancyType,
        }
        for name, enum_type in expected_enums.items():
            assert labels[name] == [member.value for member in enum_type]
        triggers = await session.execute(text(
            "SELECT trigger_name FROM information_schema.triggers "
            "WHERE trigger_schema = current_schema() AND trigger_name IN "
            "('trg_payment_attempt_snapshot_immutable', 'trg_payment_refund_snapshot_immutable', "
            "'trg_webhook_receipt_immutable', 'trg_reconciliation_observation_immutable', "
            "'trg_payment_attempts_no_delete', 'trg_payment_fulfillments_no_delete', "
            "'trg_webhook_events_no_delete', 'trg_payment_refunds_no_delete', "
            "'trg_payment_reconciliation_records_no_delete')"
        ))
        assert {row[0] for row in triggers} == {
            "trg_payment_attempt_snapshot_immutable", "trg_payment_refund_snapshot_immutable",
            "trg_webhook_receipt_immutable", "trg_reconciliation_observation_immutable",
            "trg_payment_attempts_no_delete", "trg_payment_fulfillments_no_delete",
            "trg_webhook_events_no_delete", "trg_payment_refunds_no_delete",
            "trg_payment_reconciliation_records_no_delete",
        }


@pytest.mark.asyncio
async def test_multiple_attempts_and_successful_fulfillment_are_unique_per_order(sessions):
    order = await seed_order(sessions)
    first, second = attempt(order.id), attempt(order.id)
    first.status = PaymentAttemptStatus.SUCCEEDED
    second.status = PaymentAttemptStatus.SUCCEEDED
    async with sessions() as session:
        session.add_all([first, second])
        await session.commit()
    async with sessions() as session:
        session.add(PaymentFulfillment(payment_attempt_id=first.id, order_id=order.id))
        await session.commit()
    async with sessions() as session:
        session.add(PaymentFulfillment(payment_attempt_id=second.id, order_id=order.id))
        with pytest.raises(DBAPIError):
            await session.commit()


@pytest.mark.asyncio
async def test_invalid_amount_currency_and_unmatched_relationships_fail(sessions):
    order = await seed_order(sessions)
    async with sessions() as session:
        session.add(attempt(order.id, amount=0))
        with pytest.raises(DBAPIError):
            await session.commit()
    async with sessions() as session:
        session.add(attempt(order.id, currency="USD"))
        with pytest.raises(DBAPIError):
            await session.commit()
    async with sessions() as session:
        session.add(attempt(uuid4()))
        with pytest.raises(DBAPIError):
            await session.commit()


@pytest.mark.asyncio
async def test_provider_reference_and_idempotency_uniqueness(sessions):
    order = await seed_order(sessions)
    token = uuid4().hex
    async with sessions() as session:
        session.add_all([attempt(order.id, ref=f"provider-ref-{token}"), attempt(order.id, ref=f"provider-ref-{token}")])
        with pytest.raises(DBAPIError):
            await session.commit()
    async with sessions() as session:
        session.add_all([attempt(order.id, idem="same-key"), attempt(order.id, idem="same-key")])
        with pytest.raises(DBAPIError):
            await session.commit()


@pytest.mark.asyncio
async def test_webhook_receipt_authentication_deduplication_and_processing(sessions):
    order = await seed_order(sessions)
    payment = attempt(order.id)
    token = uuid4().hex
    async with sessions() as session:
        session.add(payment)
        await session.commit()
    def event(
        key, *, auth=WebhookAuthenticationStatus.UNVERIFIED,
        state=WebhookProcessingStatus.RECEIVED, event_id=None, digest="a" * 64,
    ):
        return WebhookEvent(
            provider="paystack", provider_account="test-merchant", environment=PaymentEnvironment.TEST,
            deduplication_key=key, provider_event_id=event_id,
            event_type="charge.success", payload_sha256=digest,
            payment_attempt_id=payment.id, authentication_status=auth, processing_status=state,
        )
    async with sessions() as session:
        session.add(event(f"webhook-{token}"))
        await session.commit()
    async with sessions() as session:
        session.add(event(f"webhook-{token}"))
        with pytest.raises(IntegrityError):
            await session.commit()
    async with sessions() as session:
        session.add(event(f"forged-processing-{token}", state=WebhookProcessingStatus.PROCESSED))
        with pytest.raises(IntegrityError):
            await session.commit()
    async with sessions() as session:
        session.add(event(f"bad-digest-{token}", digest="not-a-sha256"))
        with pytest.raises(IntegrityError):
            await session.commit()
    async with sessions() as session:
        session.add_all([
            event(f"provider-event-a-{token}", event_id=f"evt-{token}"),
            event(f"provider-event-b-{token}", event_id=f"evt-{token}"),
        ])
        with pytest.raises(IntegrityError):
            await session.commit()
    async with sessions() as session:
        receipt = event(f"verified-process-{token}", auth=WebhookAuthenticationStatus.AUTHENTICATED, state=WebhookProcessingStatus.PROCESSED)
        receipt.authenticated_at = datetime.now(UTC)
        session.add(receipt)
        await session.commit()
    async with sessions() as session:
        rejected = event(f"rejected-event-{token}", auth=WebhookAuthenticationStatus.REJECTED)
        session.add(rejected)
        await session.commit()
    async with sessions() as session:
        rejected = await session.scalar(select(WebhookEvent).where(WebhookEvent.deduplication_key == f"rejected-event-{token}"))
        rejected.authentication_status = WebhookAuthenticationStatus.AUTHENTICATED
        rejected.authenticated_at = datetime.now(UTC)
        with pytest.raises(DBAPIError):
            await session.commit()
    async with sessions() as session:
        rejected = await session.scalar(select(WebhookEvent).where(WebhookEvent.deduplication_key == f"rejected-event-{token}"))
        await session.delete(rejected)
        with pytest.raises(DBAPIError):
            await session.commit()


@pytest.mark.asyncio
async def test_refunds_are_separate_repeatable_and_idempotent(sessions):
    order = await seed_order(sessions)
    payment = attempt(order.id, status=PaymentAttemptStatus.SUCCEEDED)
    token = uuid4().hex
    async with sessions() as session:
        session.add(payment)
        await session.commit()
    def refund(key, amount=400):
        return Refund(
            payment_attempt_id=payment.id, provider="paystack", provider_account="test-merchant",
            environment=PaymentEnvironment.TEST, amount_minor=amount, currency="KES",
            reason_code="late_payment", idempotency_key=key, status=RefundStatus.PENDING,
        )
    async with sessions() as session:
        session.add_all([refund(f"part-1-{token}"), refund(f"part-2-{token}")])
        await session.commit()
    async with sessions() as session:
        session.add(refund(f"part-1-{token}"))
        with pytest.raises(IntegrityError):
            await session.commit()
    async with sessions() as session:
        first = refund(f"provider-refund-a-{token}")
        second = refund(f"provider-refund-b-{token}")
        first.provider_reference = second.provider_reference = f"refund-ref-{token}"
        session.add_all([first, second])
        with pytest.raises(IntegrityError):
            await session.commit()
    async with sessions() as session:
        session.add(refund(f"zero-{token}", amount=0))
        with pytest.raises(IntegrityError):
            await session.commit()
    async with sessions() as session:
        invalid = refund(f"unconfirmed-{token}")
        invalid.status = RefundStatus.REFUNDED
        session.add(invalid)
        with pytest.raises(IntegrityError):
            await session.commit()
    async with sessions() as session:
        saved = await session.scalar(select(Refund).where(Refund.idempotency_key == f"part-1-{token}"))
        assert saved.status is RefundStatus.PENDING and saved.completed_at is None
        saved.status, saved.completed_at = RefundStatus.REFUNDED, datetime.now(UTC)
        await session.commit()


@pytest.mark.asyncio
async def test_reconciliation_is_idempotent_resolvable_and_restricts_deletion(sessions):
    order = await seed_order(sessions)
    payment = attempt(order.id, status=PaymentAttemptStatus.SUCCEEDED)
    other_payment = attempt(order.id, status=PaymentAttemptStatus.SUCCEEDED)
    async with sessions() as session:
        session.add_all([payment, other_payment])
        await session.commit()
    refund = Refund(
        payment_attempt_id=payment.id, provider="paystack", provider_account="test-merchant",
        environment=PaymentEnvironment.TEST, amount_minor=250, currency="KES",
        reason_code="test", idempotency_key=f"refund-{uuid4().hex}",
    )
    async with sessions() as session:
        session.add(refund)
        await session.commit()
    async with sessions() as session:
        session.add(ReconciliationRecord(
            payment_attempt_id=other_payment.id, refund_id=refund.id,
            provider="paystack", provider_account="test-merchant", environment=PaymentEnvironment.TEST,
            run_id=uuid4(), deduplication_key="wrong-refund-parent",
            discrepancy_type=ReconciliationDiscrepancyType.OTHER,
        ))
        with pytest.raises(IntegrityError):
            await session.commit()
    record = ReconciliationRecord(
        payment_attempt_id=payment.id, provider="paystack", provider_account="test-merchant",
        environment=PaymentEnvironment.TEST, run_id=uuid4(), deduplication_key="missing-capture",
        internal_amount_minor=1000, provider_amount_minor=900, internal_currency="KES",
        provider_currency="KES", discrepancy_type=ReconciliationDiscrepancyType.AMOUNT_MISMATCH,
        evidence_sha256="b" * 64, evidence_summary="test-only discrepancy",
    )
    async with sessions() as session:
        session.add(record)
        await session.commit()
    async with sessions() as session:
        duplicate = ReconciliationRecord(
            payment_attempt_id=payment.id, provider="paystack", provider_account="test-merchant",
            environment=PaymentEnvironment.TEST, run_id=record.run_id, deduplication_key="missing-capture",
            discrepancy_type=ReconciliationDiscrepancyType.OTHER,
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            await session.commit()
    async with sessions() as session:
        saved = await session.get(ReconciliationRecord, record.id)
        assert saved.resolution_status is ReconciliationStatus.OPEN
        saved.resolution_status, saved.resolved_at = ReconciliationStatus.RESOLVED, datetime.now(UTC)
        await session.commit()
    async with sessions() as session:
        payment = await session.get(PaymentAttempt, payment.id)
        await session.delete(payment)
        with pytest.raises(DBAPIError):
            await session.commit()


@pytest.mark.asyncio
async def test_snapshot_immutability_and_transaction_rollback(sessions):
    order = await seed_order(sessions)
    payment = attempt(order.id)
    async with sessions() as session:
        session.add(payment)
        await session.commit()
    async with sessions() as session:
        saved = await session.get(PaymentAttempt, payment.id)
        saved.currency = "USD"
        with pytest.raises(DBAPIError):
            await session.commit()
    async with sessions() as session:
        saved = await session.get(PaymentAttempt, payment.id)
        assert saved.currency == "KES"
        session.add(attempt(uuid4()))
        with pytest.raises(IntegrityError):
            await session.commit()
    async with sessions() as session:
        saved = await session.get(PaymentAttempt, payment.id)
        assert saved is not None


@pytest.mark.asyncio
async def test_concurrent_duplicate_idempotency_insert_has_one_winner(sessions):
    order = await seed_order(sessions)
    async def insert_one():
        async with sessions() as session:
            session.add(attempt(order.id, idem="concurrent-key"))
            try:
                await session.commit()
                return "committed"
            except IntegrityError:
                await session.rollback()
                return "rejected"
    outcomes = await asyncio.gather(insert_one(), insert_one())
    assert sorted(outcomes) == ["committed", "rejected"]
