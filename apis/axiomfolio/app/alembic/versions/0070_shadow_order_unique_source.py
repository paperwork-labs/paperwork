"""Partial unique index on shadow_orders.source_order_id (idempotent shadow rows).

Belt-and-suspenders with OrderManager lock ordering: duplicate submits for the
same preview order cannot insert two shadow rows. NULL source_order_id (direct
API submits) remains allowed in multiple rows.

Revision ID: 0070
Revises: 0069
Create Date: 2026-04-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_shadow_orders_source_order_id", table_name="shadow_orders")
    op.create_index(
        "uq_shadow_orders_source_order_id_not_null",
        "shadow_orders",
        ["source_order_id"],
        unique=True,
        postgresql_where=sa.text("source_order_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_shadow_orders_source_order_id_not_null", table_name="shadow_orders")
    op.create_index(
        "ix_shadow_orders_source_order_id",
        "shadow_orders",
        ["source_order_id"],
        unique=False,
    )
