"""Add PII consent timestamp on MCP tokens.

Revision ID: 0059
Revises: 0058
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mcp_tokens",
        sa.Column("pii_consent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_tokens", "pii_consent_at")
