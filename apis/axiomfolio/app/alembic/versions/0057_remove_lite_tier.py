"""Remove LITE tier, migrate users to PRO with grandfather metadata.

Revision ID: 0057
Revises: 0056
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The `metadata` column is JSON (not JSONB) — migration 0031 declared
    # it as `sa.JSON()`. `jsonb_set` only works on JSONB values, so we
    # cast to jsonb, mutate, and cast back to json for persistence.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE entitlements
            SET tier='pro',
                metadata=jsonb_set(
                    COALESCE(metadata::jsonb, '{}'::jsonb),
                    '{grandfather_price_usd}',
                    '9'::jsonb,
                    true
                )::json
            WHERE tier='lite'
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE entitlements
            SET tier='lite',
                metadata=(COALESCE(metadata::jsonb, '{}'::jsonb) - 'grandfather_price_usd')::json
            WHERE tier='pro'
              AND COALESCE(metadata::jsonb, '{}'::jsonb) ? 'grandfather_price_usd'
            """
        )
    )
