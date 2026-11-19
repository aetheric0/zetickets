"""Database-independent contract tests for the payment persistence model."""
from sqlalchemy.orm import configure_mappers

from app.models import Base
from app.models.enums import (
    PaymentAttemptStatus,
    PaymentEnvironment,
    ReconciliationDiscrepancyType,
    ReconciliationStatus,
    RefundStatus,
    WebhookAuthenticationStatus,
    WebhookProcessingStatus,
)


def test_payment_mappers_configure_and_register_expected_entities():
    configure_mappers()
    assert {
        "payment_attempts",
        "payment_fulfillments",
        "webhook_events",
        "payment_refunds",
        "payment_reconciliation_records",
    } <= set(Base.metadata.tables)


def test_payment_enum_values_are_explicit_persisted_labels():
    assert [member.value for member in PaymentAttemptStatus] == [
        "INITIALIZING", "PENDING", "SUCCEEDED", "FAILED", "EXPIRED", "RECONCILIATION_REQUIRED"
    ]
    assert [member.value for member in PaymentEnvironment] == ["TEST", "LIVE"]
    assert [member.value for member in WebhookAuthenticationStatus] == [
        "UNVERIFIED", "AUTHENTICATED", "REJECTED"
    ]
    assert [member.value for member in WebhookProcessingStatus] == [
        "RECEIVED", "PENDING", "PROCESSING", "PROCESSED", "FAILED"
    ]
    assert RefundStatus.REFUNDED.value == "REFUNDED"
    assert ReconciliationStatus.ESCALATED.value == "ESCALATED"
    assert ReconciliationDiscrepancyType.CURRENCY_MISMATCH.value == "CURRENCY_MISMATCH"


def test_constraints_enforce_snapshots_deduplication_and_single_fulfillment():
    attempts = Base.metadata.tables["payment_attempts"]
    fulfillments = Base.metadata.tables["payment_fulfillments"]
    webhooks = Base.metadata.tables["webhook_events"]
    refunds = Base.metadata.tables["payment_refunds"]
    reconciliations = Base.metadata.tables["payment_reconciliation_records"]

    assert "amount_minor > 0" in {str(c.sqltext) for c in attempts.constraints if hasattr(c, "sqltext")}
    assert "currency = 'KES'" in {str(c.sqltext) for c in attempts.constraints if hasattr(c, "sqltext")}
    assert any(c.name == "uq_payment_fulfillments_order" for c in fulfillments.constraints)
    assert any(c.name == "uq_webhook_events_deduplication_scope" for c in webhooks.constraints)
    assert any(c.name == "uq_payment_refunds_idempotency" for c in refunds.constraints)
    assert any(c.name == "uq_payment_reconciliation_idempotency" for c in reconciliations.constraints)
    assert all(fk.ondelete == "RESTRICT" for table in (attempts, fulfillments, refunds, reconciliations) for fk in table.foreign_key_constraints)


def test_webhook_storage_has_digest_not_raw_payload_or_credentials():
    columns = set(Base.metadata.tables["webhook_events"].columns.keys())
    assert "payload_sha256" in columns
    assert "raw_payload" not in columns
    assert "secret_key" not in columns


def test_refund_schema_allows_multiple_records_without_unapproved_total_policy():
    refunds = Base.metadata.tables["payment_refunds"]
    assert "amount_minor" in refunds.columns
    assert not any(
        "sum(" in str(constraint).lower() or "amount_minor <=" in str(constraint).lower()
        for constraint in refunds.constraints
    )
