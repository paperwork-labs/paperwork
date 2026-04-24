"""Add raw_payload + ingestion_status to email_inbox for Postmark inbound.

Stores the verbatim webhook JSON for parser replays and tracks ingestion
state (RECEIVED → PARSE_PENDING → …) separate from LLM parse rows.

Revision ID: 0040
Revises: 0039

Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_inbox",
        sa.Column("raw_payload", sa.JSON(), nullable=True),
    )
    op.add_column(
        "email_inbox",
        sa.Column(
            "ingestion_status",
            sa.String(32),
            nullable=False,
            server_default="RECEIVED",
        ),
    )


def downgrade() -> None:
    op.drop_column("email_inbox", "ingestion_status")
    op.drop_column("email_inbox", "raw_payload")
