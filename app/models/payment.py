"""Auditable persistence records for future provider-backed payment flows.

These models deliberately do not implement provider verification or fulfillment.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.enums import (
    PaymentAttemptStatus,
    PaymentEnvironment,
    ReconciliationDiscrepancyType,
    ReconciliationStatus,
    RefundStatus,
    WebhookAuthenticationStatus,
    WebhookProcessingStatus,
)
from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order


def _enum_values(enum_class):
    return [member.value for member in enum_class]


class PaymentAttempt(Base, TimestampMixin):
    """One immutable amount/currency snapshot and provider payment attempt."""

    __tablename__ = "payment_attempts"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_payment_attempts_amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_payment_attempts_currency_iso"),
        UniqueConstraint(
            "provider", "provider_account", "environment", "provider_reference",
            name="uq_payment_attempts_provider_reference_scope",
        ),
        UniqueConstraint("order_id", "idempotency_key", name="uq_payment_attempts_order_idempotency"),
        UniqueConstraint("id", "order_id", name="uq_payment_attempts_id_order"),
        UniqueConstraint("id", "order_id", "status", name="uq_payment_attempts_id_order_status"),
        UniqueConstraint(
            "id", "provider", "provider_account", "environment",
            name="uq_payment_attempts_id_provider_scope",
        ),
        CheckConstraint("currency = 'KES'", name="ck_payment_attempts_initial_currency_kes"),
        Index("ix_payment_attempts_order_status", "order_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="paystack", server_default="paystack")
    provider_account: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[PaymentEnvironment] = mapped_column(
        Enum(PaymentEnvironment, name="payment_environment", values_callable=_enum_values), nullable=False
    )
    client_reference: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    provider_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="KES")
    status: Mapped[PaymentAttemptStatus] = mapped_column(
        Enum(PaymentAttemptStatus, name="payment_attempt_status", values_callable=_enum_values),
        nullable=False, default=PaymentAttemptStatus.INITIALIZING,
        server_default=PaymentAttemptStatus.INITIALIZING.value,
    )
    provider_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    initiated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    order: Mapped[Order] = relationship("Order", back_populates="payment_attempts")
    refunds: Mapped[list[Refund]] = relationship(back_populates="payment_attempt", passive_deletes=True)
    webhook_events: Mapped[list[WebhookEvent]] = relationship(back_populates="payment_attempt", passive_deletes=True)
    reconciliation_records: Mapped[list[ReconciliationRecord]] = relationship(
        back_populates="payment_attempt", passive_deletes=True,
        foreign_keys="ReconciliationRecord.payment_attempt_id",
    )
    fulfillment: Mapped[PaymentFulfillment | None] = relationship(
        back_populates="payment_attempt", uselist=False, passive_deletes=True,
        foreign_keys="PaymentFulfillment.payment_attempt_id",
    )


class PaymentFulfillment(Base):
    """Unique claim tied to a successful-state attempt, not proof of provider verification."""

    __tablename__ = "payment_fulfillments"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_payment_fulfillments_order"),
        CheckConstraint("payment_status = 'SUCCEEDED'", name="ck_payment_fulfillments_success_only"),
        ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["payment_attempt_id", "order_id", "payment_status"],
            ["payment_attempts.id", "payment_attempts.order_id", "payment_attempts.status"],
            ondelete="RESTRICT",
            name="fk_payment_fulfillments_attempt_order",
        ),
    )

    payment_attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payment_status: Mapped[PaymentAttemptStatus] = mapped_column(
        Enum(PaymentAttemptStatus, name="payment_attempt_status", values_callable=_enum_values),
        nullable=False,
        server_default=PaymentAttemptStatus.SUCCEEDED.value,
    )
    fulfilled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    payment_attempt: Mapped[PaymentAttempt] = relationship(
        back_populates="fulfillment", foreign_keys=[payment_attempt_id]
    )
    order: Mapped[Order] = relationship("Order", back_populates="payment_fulfillment")


class WebhookEvent(Base):
    """Minimal durable webhook receipt; raw payloads and credentials are not stored."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_account", "environment", "deduplication_key",
            name="uq_webhook_events_deduplication_scope",
        ),
        UniqueConstraint(
            "provider", "provider_account", "environment", "provider_event_id",
            name="uq_webhook_events_provider_event_scope",
        ),
        CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_webhook_events_digest_sha256"),
        CheckConstraint(
            "processing_status NOT IN ('PROCESSING', 'PROCESSED', 'FAILED') OR "
            "authentication_status = 'AUTHENTICATED'",
            name="ck_webhook_events_processing_requires_authentication",
        ),
        CheckConstraint(
            "(authentication_status = 'AUTHENTICATED') = (authenticated_at IS NOT NULL)",
            name="ck_webhook_events_authentication_timestamp",
        ),
        ForeignKeyConstraint(
            ["payment_attempt_id", "provider", "provider_account", "environment"],
            ["payment_attempts.id", "payment_attempts.provider", "payment_attempts.provider_account", "payment_attempts.environment"],
            ondelete="RESTRICT",
            name="fk_webhook_events_payment_scope",
        ),
        Index("ix_webhook_events_processing", "processing_status", "received_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[PaymentEnvironment] = mapped_column(
        Enum(PaymentEnvironment, name="payment_environment", values_callable=_enum_values), nullable=False
    )
    provider_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    deduplication_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payment_attempt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    authentication_status: Mapped[WebhookAuthenticationStatus] = mapped_column(
        Enum(WebhookAuthenticationStatus, name="webhook_authentication_status", values_callable=_enum_values),
        nullable=False, default=WebhookAuthenticationStatus.UNVERIFIED,
        server_default=WebhookAuthenticationStatus.UNVERIFIED.value,
    )
    authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_status: Mapped[WebhookProcessingStatus] = mapped_column(
        Enum(WebhookProcessingStatus, name="webhook_processing_status", values_callable=_enum_values),
        nullable=False, default=WebhookProcessingStatus.RECEIVED,
        server_default=WebhookProcessingStatus.RECEIVED.value,
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_attempt: Mapped[PaymentAttempt | None] = relationship(back_populates="webhook_events")


class Refund(Base, TimestampMixin):
    """A separately tracked refund request; only provider confirmation is final."""

    __tablename__ = "payment_refunds"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_payment_refunds_amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_payment_refunds_currency_iso"),
        CheckConstraint("currency = 'KES'", name="ck_payment_refunds_initial_currency_kes"),
        CheckConstraint("status <> 'REFUNDED' OR completed_at IS NOT NULL", name="ck_payment_refunds_confirmed_timestamp"),
        UniqueConstraint("payment_attempt_id", "idempotency_key", name="uq_payment_refunds_idempotency"),
        UniqueConstraint(
            "provider", "provider_account", "environment", "provider_reference",
            name="uq_payment_refunds_provider_reference_scope",
        ),
        UniqueConstraint("id", "payment_attempt_id", "provider", "provider_account", "environment", name="uq_payment_refunds_id_payment_scope"),
        Index("ix_payment_refunds_payment_attempt_id", "payment_attempt_id"),
        Index("ix_payment_refunds_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    payment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[PaymentEnvironment] = mapped_column(
        Enum(PaymentEnvironment, name="payment_environment", values_callable=_enum_values), nullable=False
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="KES")
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status", values_callable=_enum_values), nullable=False,
        default=RefundStatus.PENDING, server_default=RefundStatus.PENDING.value,
    )
    initiated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)

    payment_attempt: Mapped[PaymentAttempt] = relationship(back_populates="refunds")
    reconciliation_records: Mapped[list[ReconciliationRecord]] = relationship(
        back_populates="refund", passive_deletes=True,
        foreign_keys="ReconciliationRecord.refund_id",
    )


class ReconciliationRecord(Base):
    """Bounded observation of internal/provider state and its resolution."""

    __tablename__ = "payment_reconciliation_records"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_account", "environment", "run_id", "deduplication_key",
            name="uq_payment_reconciliation_idempotency",
        ),
        CheckConstraint("internal_amount_minor IS NULL OR internal_amount_minor >= 0", name="ck_recon_internal_amount_nonnegative"),
        CheckConstraint("provider_amount_minor IS NULL OR provider_amount_minor >= 0", name="ck_recon_provider_amount_nonnegative"),
        CheckConstraint("internal_currency IS NULL OR internal_currency ~ '^[A-Z]{3}$'", name="ck_recon_internal_currency_iso"),
        CheckConstraint("provider_currency IS NULL OR provider_currency ~ '^[A-Z]{3}$'", name="ck_recon_provider_currency_iso"),
        CheckConstraint("evidence_sha256 IS NULL OR evidence_sha256 ~ '^[0-9a-f]{64}$'", name="ck_reconciliation_evidence_sha256"),
        CheckConstraint("resolution_status <> 'RESOLVED' OR resolved_at IS NOT NULL", name="ck_reconciliation_resolved_timestamp"),
        Index("ix_payment_reconciliation_status_observed", "resolution_status", "observed_at"),
        Index("ix_payment_reconciliation_payment_attempt_id", "payment_attempt_id"),
        Index("ix_payment_reconciliation_refund_id", "refund_id"),
        ForeignKeyConstraint(
            ["payment_attempt_id", "provider", "provider_account", "environment"],
            ["payment_attempts.id", "payment_attempts.provider", "payment_attempts.provider_account", "payment_attempts.environment"],
            ondelete="RESTRICT",
            name="fk_payment_reconciliation_payment_scope",
        ),
        ForeignKeyConstraint(
            ["refund_id", "payment_attempt_id", "provider", "provider_account", "environment"],
            ["payment_refunds.id", "payment_refunds.payment_attempt_id", "payment_refunds.provider", "payment_refunds.provider_account", "payment_refunds.environment"],
            ondelete="RESTRICT",
            name="fk_payment_reconciliation_refund_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    payment_attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    refund_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[PaymentEnvironment] = mapped_column(
        Enum(PaymentEnvironment, name="payment_environment", values_callable=_enum_values), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(128), nullable=False)
    internal_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    internal_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    provider_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    internal_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    provider_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    discrepancy_type: Mapped[ReconciliationDiscrepancyType] = mapped_column(
        Enum(ReconciliationDiscrepancyType, name="reconciliation_discrepancy_type", values_callable=_enum_values),
        nullable=False,
    )
    resolution_status: Mapped[ReconciliationStatus] = mapped_column(
        Enum(ReconciliationStatus, name="reconciliation_status", values_callable=_enum_values),
        nullable=False, default=ReconciliationStatus.OPEN, server_default=ReconciliationStatus.OPEN.value,
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)

    payment_attempt: Mapped[PaymentAttempt] = relationship(
        back_populates="reconciliation_records", foreign_keys=[payment_attempt_id]
    )
    refund: Mapped[Refund | None] = relationship(
        back_populates="reconciliation_records", foreign_keys=[refund_id]
    )
