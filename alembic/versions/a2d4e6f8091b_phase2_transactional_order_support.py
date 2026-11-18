"""Add reservation idempotency and inventory invariants.

Revision ID: a2d4e6f8091b
Revises: 8f3c1a2d9b40

Forward-only and unverified against PostgreSQL. Historical order keys remain
NULL; new reservation requests must provide a key.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2d4e6f8091b"
down_revision: Union[str, Sequence[str], None] = "8f3c1a2d9b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'PAYMENT_FAILED'")
    # Reconcile model documentation with the preserved initial schema.
    # PostgreSQL stores these as column comments, so keep Alembic's metadata
    # check clean without editing the original migration.
    op.alter_column(
        "ticket_types", "quantity_available", existing_type=sa.Integer(),
        comment="Total max tickets allocated for this tier",
    )
    op.alter_column(
        "ticket_types", "quantity_reserved", existing_type=sa.Integer(),
        comment="Active pending reservation holds",
    )
    op.alter_column(
        "ticket_types", "quantity_sold", existing_type=sa.Integer(),
        comment="Finalized paid ticket sales",
    )
    op.add_column("orders", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("orders", sa.Column("payment_evidence_reference", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_orders_payment_evidence_reference", "orders", ["payment_evidence_reference"]
    )
    op.create_unique_constraint(
        "uq_orders_user_id_idempotency_key", "orders", ["user_id", "idempotency_key"]
    )
    op.create_check_constraint(
        "ck_orders_quantity_positive", "orders", "quantity IS NULL OR quantity > 0"
    )
    op.create_check_constraint(
        "ck_ticket_types_reserved_nonnegative",
        "ticket_types",
        "quantity_reserved IS NULL OR quantity_reserved >= 0",
    )
    op.create_check_constraint(
        "ck_ticket_types_sold_nonnegative",
        "ticket_types",
        "quantity_sold IS NULL OR quantity_sold >= 0",
    )


def downgrade() -> None:
    raise NotImplementedError("Phase 2 migration is forward-only; restore from a verified backup to reverse it.")
