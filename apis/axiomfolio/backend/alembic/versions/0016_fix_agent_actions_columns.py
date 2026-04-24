"""Add missing confidence_score column to agent_actions.

Uses IF NOT EXISTS for idempotency since this column may already exist
in some environments from the baseline.

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-02
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE agent_actions ADD COLUMN IF NOT EXISTS confidence_score FLOAT")


def downgrade() -> None:
    # No-op: this migration is an idempotent reconciliation step, and
    # confidence_score may already exist in revision 0015/baseline.
    # Dropping it here could leave the downgraded schema inconsistent.
    pass
