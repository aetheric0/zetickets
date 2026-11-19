"""Add auditable payment attempts, webhook receipts, refunds and reconciliation.

Revision ID: c7e2a4b19d60
Revises: a2d4e6f8091b

Forward-only, data-preserving. This revision has not been applied to an
application database; validate it against an isolated PostgreSQL cluster.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c7e2a4b19d60"
down_revision: Union[str, Sequence[str], None] = "a2d4e6f8091b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENUMS = {
    "payment_environment": ("TEST", "LIVE"),
    "payment_attempt_status": (
        "INITIALIZING", "PENDING", "SUCCEEDED", "FAILED", "EXPIRED", "RECONCILIATION_REQUIRED"
    ),
    "webhook_authentication_status": ("UNVERIFIED", "AUTHENTICATED", "REJECTED"),
    "webhook_processing_status": ("RECEIVED", "PENDING", "PROCESSING", "PROCESSED", "FAILED"),
    "refund_status": ("PENDING", "PROCESSING", "REFUNDED", "FAILED", "NEEDS_RECONCILIATION"),
    "reconciliation_status": ("OPEN", "RESOLVED", "ESCALATED"),
    "reconciliation_discrepancy_type": (
        "NONE", "STATUS_MISMATCH", "AMOUNT_MISMATCH", "CURRENCY_MISMATCH",
        "REFERENCE_MISMATCH", "MISSING_PROVIDER_RECORD", "MISSING_INTERNAL_RECORD",
        "REFUND_MISMATCH", "OTHER",
    ),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    op.create_table(
        "payment_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), server_default="paystack", nullable=False),
        sa.Column("provider_account", sa.String(100), nullable=False),
        sa.Column("environment", _enum("payment_environment"), nullable=False),
        sa.Column("client_reference", sa.String(128), nullable=False),
        sa.Column("provider_reference", sa.String(128), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="KES", nullable=False),
        sa.Column("status", _enum("payment_attempt_status"), server_default="INITIALIZING", nullable=False),
        sa.Column("provider_status", sa.String(64), nullable=True),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount_minor > 0", name="ck_payment_attempts_amount_positive"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_payment_attempts_currency_iso"),
        sa.CheckConstraint("currency = 'KES'", name="ck_payment_attempts_initial_currency_kes"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_reference"),
        sa.UniqueConstraint("provider", "provider_account", "environment", "provider_reference", name="uq_payment_attempts_provider_reference_scope"),
        sa.UniqueConstraint("order_id", "idempotency_key", name="uq_payment_attempts_order_idempotency"),
        sa.UniqueConstraint("id", "order_id", name="uq_payment_attempts_id_order"),
        sa.UniqueConstraint("id", "order_id", "status", name="uq_payment_attempts_id_order_status"),
        sa.UniqueConstraint("id", "provider", "provider_account", "environment", name="uq_payment_attempts_id_provider_scope"),
    )
    op.create_index("ix_payment_attempts_order_status", "payment_attempts", ["order_id", "status"])

    op.create_table(
        "payment_fulfillments",
        sa.Column("payment_attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_status", _enum("payment_attempt_status"), server_default="SUCCEEDED", nullable=False),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("payment_status = 'SUCCEEDED'", name="ck_payment_fulfillments_success_only"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_attempt_id", "order_id", "payment_status"], ["payment_attempts.id", "payment_attempts.order_id", "payment_attempts.status"], ondelete="RESTRICT", name="fk_payment_fulfillments_attempt_order_status"),
        sa.PrimaryKeyConstraint("payment_attempt_id"),
        sa.UniqueConstraint("order_id", name="uq_payment_fulfillments_order"),
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_account", sa.String(100), nullable=False),
        sa.Column("environment", _enum("payment_environment"), nullable=False),
        sa.Column("provider_event_id", sa.String(128), nullable=True),
        sa.Column("deduplication_key", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("provider_reference", sa.String(128), nullable=True),
        sa.Column("payment_attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("authentication_status", _enum("webhook_authentication_status"), server_default="UNVERIFIED", nullable=False),
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_status", _enum("webhook_processing_status"), server_default="RECEIVED", nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_detail", sa.String(500), nullable=True),
        sa.CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_webhook_events_digest_sha256"),
        sa.CheckConstraint("processing_status NOT IN ('PROCESSING', 'PROCESSED', 'FAILED') OR authentication_status = 'AUTHENTICATED'", name="ck_webhook_events_processing_requires_authentication"),
        sa.CheckConstraint("(authentication_status = 'AUTHENTICATED') = (authenticated_at IS NOT NULL)", name="ck_webhook_events_authentication_timestamp"),
        sa.ForeignKeyConstraint(["payment_attempt_id", "provider", "provider_account", "environment"], ["payment_attempts.id", "payment_attempts.provider", "payment_attempts.provider_account", "payment_attempts.environment"], ondelete="RESTRICT", name="fk_webhook_events_payment_scope"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_account", "environment", "deduplication_key", name="uq_webhook_events_deduplication_scope"),
        sa.UniqueConstraint("provider", "provider_account", "environment", "provider_event_id", name="uq_webhook_events_provider_event_scope"),
    )
    op.create_index("ix_webhook_events_processing", "webhook_events", ["processing_status", "received_at"])

    op.create_table(
        "payment_refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("payment_attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_account", sa.String(100), nullable=False),
        sa.Column("environment", _enum("payment_environment"), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="KES", nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("provider_reference", sa.String(128), nullable=True),
        sa.Column("status", _enum("refund_status"), server_default="PENDING", nullable=False),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_detail", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount_minor > 0", name="ck_payment_refunds_amount_positive"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_payment_refunds_currency_iso"),
        sa.CheckConstraint("currency = 'KES'", name="ck_payment_refunds_initial_currency_kes"),
        sa.CheckConstraint("status <> 'REFUNDED' OR completed_at IS NOT NULL", name="ck_payment_refunds_confirmed_timestamp"),
        sa.ForeignKeyConstraint(["payment_attempt_id"], ["payment_attempts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_attempt_id", "idempotency_key", name="uq_payment_refunds_idempotency"),
        sa.UniqueConstraint("provider", "provider_account", "environment", "provider_reference", name="uq_payment_refunds_provider_reference_scope"),
        sa.UniqueConstraint("id", "payment_attempt_id", "provider", "provider_account", "environment", name="uq_payment_refunds_id_payment_scope"),
    )
    op.create_index("ix_payment_refunds_payment_attempt_id", "payment_refunds", ["payment_attempt_id"])
    op.create_index("ix_payment_refunds_status", "payment_refunds", ["status"])

    op.create_table(
        "payment_reconciliation_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("payment_attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refund_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_account", sa.String(100), nullable=False),
        sa.Column("environment", _enum("payment_environment"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deduplication_key", sa.String(128), nullable=False),
        sa.Column("internal_status", sa.String(64), nullable=True),
        sa.Column("provider_status", sa.String(64), nullable=True),
        sa.Column("internal_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("provider_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("internal_currency", sa.String(3), nullable=True),
        sa.Column("provider_currency", sa.String(3), nullable=True),
        sa.Column("discrepancy_type", _enum("reconciliation_discrepancy_type"), nullable=False),
        sa.Column("resolution_status", _enum("reconciliation_status"), server_default="OPEN", nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_sha256", sa.String(64), nullable=True),
        sa.Column("evidence_summary", sa.String(500), nullable=True),
        sa.CheckConstraint("internal_amount_minor IS NULL OR internal_amount_minor >= 0", name="ck_recon_internal_amount_nonnegative"),
        sa.CheckConstraint("provider_amount_minor IS NULL OR provider_amount_minor >= 0", name="ck_recon_provider_amount_nonnegative"),
        sa.CheckConstraint("internal_currency IS NULL OR internal_currency ~ '^[A-Z]{3}$'", name="ck_recon_internal_currency_iso"),
        sa.CheckConstraint("provider_currency IS NULL OR provider_currency ~ '^[A-Z]{3}$'", name="ck_recon_provider_currency_iso"),
        sa.CheckConstraint("evidence_sha256 IS NULL OR evidence_sha256 ~ '^[0-9a-f]{64}$'", name="ck_reconciliation_evidence_sha256"),
        sa.CheckConstraint("resolution_status <> 'RESOLVED' OR resolved_at IS NOT NULL", name="ck_reconciliation_resolved_timestamp"),
        sa.ForeignKeyConstraint(["payment_attempt_id", "provider", "provider_account", "environment"], ["payment_attempts.id", "payment_attempts.provider", "payment_attempts.provider_account", "payment_attempts.environment"], ondelete="RESTRICT", name="fk_payment_reconciliation_payment_scope"),
        sa.ForeignKeyConstraint(["refund_id", "payment_attempt_id", "provider", "provider_account", "environment"], ["payment_refunds.id", "payment_refunds.payment_attempt_id", "payment_refunds.provider", "payment_refunds.provider_account", "payment_refunds.environment"], ondelete="RESTRICT", name="fk_payment_reconciliation_refund_scope"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_account", "environment", "run_id", "deduplication_key", name="uq_payment_reconciliation_idempotency"),
    )
    op.create_index("ix_payment_reconciliation_payment_attempt_id", "payment_reconciliation_records", ["payment_attempt_id"])
    op.create_index("ix_payment_reconciliation_refund_id", "payment_reconciliation_records", ["refund_id"])
    op.create_index("ix_payment_reconciliation_status_observed", "payment_reconciliation_records", ["resolution_status", "observed_at"])

    # Financial snapshot fields are immutable at the database boundary. A provider
    # reference may be populated once, then cannot be changed or erased.
    op.execute("""
    CREATE FUNCTION reject_payment_snapshot_mutation() RETURNS trigger AS $$
    BEGIN
      IF ROW(NEW.order_id, NEW.provider, NEW.provider_account, NEW.environment,
             NEW.client_reference, NEW.idempotency_key, NEW.amount_minor, NEW.currency)
         IS DISTINCT FROM
         ROW(OLD.order_id, OLD.provider, OLD.provider_account, OLD.environment,
             OLD.client_reference, OLD.idempotency_key, OLD.amount_minor, OLD.currency) THEN
        RAISE EXCEPTION 'payment attempt snapshot fields are immutable';
      END IF;
      IF OLD.provider_reference IS NOT NULL AND NEW.provider_reference IS DISTINCT FROM OLD.provider_reference THEN
        RAISE EXCEPTION 'provider reference cannot be changed after assignment';
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_payment_attempt_snapshot_immutable BEFORE UPDATE ON payment_attempts FOR EACH ROW EXECUTE FUNCTION reject_payment_snapshot_mutation()")
    op.execute("""
    CREATE FUNCTION reject_refund_snapshot_mutation() RETURNS trigger AS $$
    BEGIN
      IF ROW(NEW.payment_attempt_id, NEW.provider, NEW.provider_account, NEW.environment,
             NEW.amount_minor, NEW.currency, NEW.reason_code, NEW.idempotency_key)
         IS DISTINCT FROM
         ROW(OLD.payment_attempt_id, OLD.provider, OLD.provider_account, OLD.environment,
             OLD.amount_minor, OLD.currency, OLD.reason_code, OLD.idempotency_key) THEN
        RAISE EXCEPTION 'refund snapshot fields are immutable';
      END IF;
      IF OLD.provider_reference IS NOT NULL AND NEW.provider_reference IS DISTINCT FROM OLD.provider_reference THEN
        RAISE EXCEPTION 'refund provider reference cannot be changed after assignment';
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_payment_refund_snapshot_immutable BEFORE UPDATE ON payment_refunds FOR EACH ROW EXECUTE FUNCTION reject_refund_snapshot_mutation()")

    op.execute("""
    CREATE FUNCTION reject_webhook_receipt_mutation() RETURNS trigger AS $$
    BEGIN
      IF ROW(NEW.provider, NEW.provider_account, NEW.environment, NEW.provider_event_id,
             NEW.deduplication_key, NEW.event_type, NEW.payload_sha256, NEW.provider_reference,
             NEW.payment_attempt_id, NEW.received_at)
         IS DISTINCT FROM
         ROW(OLD.provider, OLD.provider_account, OLD.environment, OLD.provider_event_id,
             OLD.deduplication_key, OLD.event_type, OLD.payload_sha256, OLD.provider_reference,
             OLD.payment_attempt_id, OLD.received_at) THEN
        RAISE EXCEPTION 'webhook receipt evidence is immutable';
      END IF;
      IF OLD.authentication_status = 'REJECTED' AND NEW.authentication_status = 'AUTHENTICATED' THEN
        RAISE EXCEPTION 'rejected webhook receipt cannot become authenticated';
      END IF;
      IF OLD.authentication_status = 'AUTHENTICATED' AND NEW.authentication_status <> 'AUTHENTICATED' THEN
        RAISE EXCEPTION 'authenticated webhook result cannot be reversed';
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_webhook_receipt_immutable BEFORE UPDATE ON webhook_events FOR EACH ROW EXECUTE FUNCTION reject_webhook_receipt_mutation()")
    op.execute("""
    CREATE FUNCTION reject_reconciliation_observation_mutation() RETURNS trigger AS $$
    BEGIN
      IF ROW(NEW.payment_attempt_id, NEW.refund_id, NEW.provider, NEW.provider_account,
             NEW.environment, NEW.run_id, NEW.deduplication_key, NEW.internal_status,
             NEW.provider_status, NEW.internal_amount_minor, NEW.provider_amount_minor,
             NEW.internal_currency, NEW.provider_currency, NEW.discrepancy_type, NEW.observed_at,
             NEW.evidence_sha256, NEW.evidence_summary)
         IS DISTINCT FROM
         ROW(OLD.payment_attempt_id, OLD.refund_id, OLD.provider, OLD.provider_account,
             OLD.environment, OLD.run_id, OLD.deduplication_key, OLD.internal_status,
             OLD.provider_status, OLD.internal_amount_minor, OLD.provider_amount_minor,
             OLD.internal_currency, OLD.provider_currency, OLD.discrepancy_type, OLD.observed_at,
             OLD.evidence_sha256, OLD.evidence_summary) THEN
        RAISE EXCEPTION 'reconciliation observation is immutable';
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_reconciliation_observation_immutable BEFORE UPDATE ON payment_reconciliation_records FOR EACH ROW EXECUTE FUNCTION reject_reconciliation_observation_mutation()")
    op.execute("""
    CREATE FUNCTION reject_financial_record_delete() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'financial and payment audit records cannot be deleted';
    END;
    $$ LANGUAGE plpgsql
    """)
    for table_name in (
        "payment_attempts", "payment_fulfillments", "webhook_events",
        "payment_refunds", "payment_reconciliation_records",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_no_delete BEFORE DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION reject_financial_record_delete()"
        )


def downgrade() -> None:
    # Refuse to erase financial/audit data even on a fresh disposable database.
    op.execute("""
    DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM payment_attempts) OR EXISTS (SELECT 1 FROM payment_fulfillments)
         OR EXISTS (SELECT 1 FROM webhook_events) OR EXISTS (SELECT 1 FROM payment_refunds)
         OR EXISTS (SELECT 1 FROM payment_reconciliation_records) THEN
        RAISE EXCEPTION 'refusing to downgrade payment schema containing records';
      END IF;
    END;
    $$
    """)
    op.execute("DROP TRIGGER trg_payment_refund_snapshot_immutable ON payment_refunds")
    op.execute("DROP FUNCTION reject_refund_snapshot_mutation()")
    op.execute("DROP TRIGGER trg_payment_attempt_snapshot_immutable ON payment_attempts")
    op.execute("DROP FUNCTION reject_payment_snapshot_mutation()")
    for table_name in (
        "payment_attempts", "payment_fulfillments", "webhook_events",
        "payment_refunds", "payment_reconciliation_records",
    ):
        op.execute(f"DROP TRIGGER trg_{table_name}_no_delete ON {table_name}")
    op.execute("DROP FUNCTION reject_financial_record_delete()")
    op.execute("DROP TRIGGER trg_reconciliation_observation_immutable ON payment_reconciliation_records")
    op.execute("DROP FUNCTION reject_reconciliation_observation_mutation()")
    op.execute("DROP TRIGGER trg_webhook_receipt_immutable ON webhook_events")
    op.execute("DROP FUNCTION reject_webhook_receipt_mutation()")
    op.drop_index("ix_payment_reconciliation_status_observed", table_name="payment_reconciliation_records")
    op.drop_index("ix_payment_reconciliation_refund_id", table_name="payment_reconciliation_records")
    op.drop_index("ix_payment_reconciliation_payment_attempt_id", table_name="payment_reconciliation_records")
    op.drop_table("payment_reconciliation_records")
    op.drop_index("ix_payment_refunds_status", table_name="payment_refunds")
    op.drop_index("ix_payment_refunds_payment_attempt_id", table_name="payment_refunds")
    op.drop_table("payment_refunds")
    op.drop_index("ix_webhook_events_processing", table_name="webhook_events")
    op.drop_table("webhook_events")
    op.drop_table("payment_fulfillments")
    op.drop_index("ix_payment_attempts_order_status", table_name="payment_attempts")
    op.drop_table("payment_attempts")
    for name in reversed(tuple(ENUMS)):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
