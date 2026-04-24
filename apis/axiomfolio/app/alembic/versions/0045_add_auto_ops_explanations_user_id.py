"""Add nullable ``user_id`` to ``auto_ops_explanations`` for MCP scoping.

MCP ``get_recent_explanations`` must filter by authenticated user; system-
generated rows keep ``user_id`` NULL and remain visible only via admin
HTTP routes that intentionally list platform-wide audit data.

Revision ID: 0045
Revises: 0044
Create Date: 2026-04-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auto_ops_explanations",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_auto_ops_explanations_user_id_generated",
        "auto_ops_explanations",
        ["user_id", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auto_ops_explanations_user_id_generated",
        table_name="auto_ops_explanations",
    )
    op.drop_column("auto_ops_explanations", "user_id")
