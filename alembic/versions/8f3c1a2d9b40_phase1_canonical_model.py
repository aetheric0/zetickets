"""Add canonical reservation and ticket-type fields without fabricating history.

Revision ID: 8f3c1a2d9b40
Revises: 6b2696fd5856

This revision is intentionally forward-only. It has not been verified against
any deployed database. Newly introduced historical order facts stay NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f3c1a2d9b40"
down_revision: Union[str, Sequence[str], None] = "6b2696fd5856"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Preserve every existing status label; retain legacy order labels in the
    # ORM until their lifecycle meaning is confirmed.
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'COMPLETED'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'EXPIRED'")
    op.execute("ALTER TYPE ticketstatus ADD VALUE IF NOT EXISTS 'EXPIRED'")
    op.execute("ALTER TYPE ticketstatus ADD VALUE IF NOT EXISTS 'RESERVED'")

    # The user enum in the initial revision stores member names (uppercase),
    # while the Python enum's declared values are lowercase.
    op.execute("ALTER TYPE user_role_enum RENAME VALUE 'ORGANIZER' TO 'organizer'")
    op.execute("ALTER TYPE user_role_enum RENAME VALUE 'GATEKEEPER' TO 'gatekeeper'")
    op.execute("ALTER TYPE user_role_enum RENAME VALUE 'ADMIN' TO 'admin'")
    op.execute("ALTER TYPE user_role_enum RENAME VALUE 'ATTENDEE' TO 'attendee'")

    op.add_column("orders", sa.Column("ticket_type_id", sa.UUID(), nullable=True))
    op.add_column("orders", sa.Column("quantity", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("unit_price", sa.Numeric(10, 2), nullable=True))
    op.add_column("orders", sa.Column("currency", sa.String(3), nullable=True))
    op.add_column("orders", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_orders_ticket_type_id_ticket_types", "orders", "ticket_types", ["ticket_type_id"], ["id"])

    op.add_column("ticket_types", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("ticket_types", sa.Column("quantity_reserved", sa.Integer(), nullable=True))
    op.add_column("ticket_types", sa.Column("quantity_sold", sa.Integer(), nullable=True))
    # The initial schema had no activation flag; keep existing state unknown.
    op.add_column("ticket_types", sa.Column("is_active", sa.Boolean(), nullable=True))
    # Publication state was absent from the initial schema; preserve unknown as NULL.
    op.add_column("events", sa.Column("is_published", sa.Boolean(), nullable=True))
    op.add_column("users", sa.Column("is_superuser", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.alter_column("users", "full_name", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    raise NotImplementedError("Phase 1 migration is forward-only; restore from a verified backup to reverse it.")
