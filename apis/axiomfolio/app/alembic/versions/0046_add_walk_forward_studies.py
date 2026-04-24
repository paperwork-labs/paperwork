"""Add walk_forward_studies table for Optuna-based hyperparameter optimization.

Per the v1+ master plan Phase 6a, this stores the configuration and results
of a per-user walk-forward optimization study. Each row corresponds to one
study which Celery executes on the ``heavy`` queue (these can run for
30+ minutes). The frontend polls the row by id while ``status='running'``.

Numeric columns use ``Numeric`` to preserve Decimal precision on scores.
The migration claims slot 0046; if a parallel PR lands first, the
orchestrator will renumber on second-merge per branch policy.

Revision ID: 0046
Revises: 0045

Create Date: 2026-04-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "walk_forward_studies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("strategy_class", sa.String(length=120), nullable=False),
        sa.Column(
            "objective",
            sa.String(length=64),
            nullable=False,
            server_default="sharpe_ratio",
        ),
        sa.Column("param_space", sa.JSON(), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("train_window_days", sa.Integer(), nullable=False),
        sa.Column("test_window_days", sa.Integer(), nullable=False),
        sa.Column("n_splits", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("n_trials", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("regime_filter", sa.String(length=8), nullable=True),
        sa.Column("dataset_start", sa.DateTime(), nullable=False),
        sa.Column("dataset_end", sa.DateTime(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                name="walk_forward_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("best_params", sa.JSON(), nullable=True),
        sa.Column("best_score", sa.Numeric(18, 8), nullable=True),
        sa.Column("total_trials", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("per_split_results", sa.JSON(), nullable=True),
        sa.Column("regime_attribution", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_wf_study_user_status",
        "walk_forward_studies",
        ["user_id", "status"],
    )
    op.create_index(
        "idx_wf_study_created",
        "walk_forward_studies",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_wf_study_created", table_name="walk_forward_studies")
    op.drop_index("idx_wf_study_user_status", table_name="walk_forward_studies")
    op.drop_table("walk_forward_studies")
    sa.Enum(name="walk_forward_status").drop(op.get_bind(), checkfirst=True)
