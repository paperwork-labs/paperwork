"""Add ``auto_ops_explanations`` table for AnomalyExplainer persistence.

Backs :class:`backend.models.auto_ops_explanation.AutoOpsExplanation`.
One row per generated AnomalyExplainer output. Indexed for the admin UI
poll endpoint (``GET /api/v1/admin/agent/explanations``) and the
"latest explanation per anomaly" lookup used by the Celery wiring in
:mod:`backend.tasks.ops.explain_anomaly`.

Schema notes
------------
* ``payload_json`` carries the full Explanation dict so the explainer
  schema can evolve without column churn.
* ``confidence`` is ``Numeric(4, 3)`` to round-trip the explainer's
  ``Decimal`` confidence without IEEE-754 drift.
* Enum-like string columns (``category``, ``severity``) are plain
  ``VARCHAR`` per the engineering.mdc convention -- adding a new enum
  value should never require an ``ALTER TYPE`` migration.
* Composite indexes on ``(anomaly_id, generated_at)`` and
  ``(category, generated_at)`` cover the two read patterns documented in
  the model docstring without forcing a redundant single-column index.

Revision ID: 0036
Revises: 0035
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auto_ops_explanations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("anomaly_id", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column(
            "is_fallback",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "severity IN ('info','warning','error','critical')",
            name="ck_auto_ops_explanations_severity",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_auto_ops_explanations_confidence_range",
        ),
    )
    op.create_index(
        "ix_auto_ops_explanations_severity",
        "auto_ops_explanations",
        ["severity"],
    )
    op.create_index(
        "ix_auto_ops_explanations_is_fallback",
        "auto_ops_explanations",
        ["is_fallback"],
    )
    op.create_index(
        "ix_auto_ops_explanations_anomaly_generated",
        "auto_ops_explanations",
        ["anomaly_id", "generated_at"],
    )
    op.create_index(
        "ix_auto_ops_explanations_category_generated",
        "auto_ops_explanations",
        ["category", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auto_ops_explanations_category_generated",
        table_name="auto_ops_explanations",
    )
    op.drop_index(
        "ix_auto_ops_explanations_anomaly_generated",
        table_name="auto_ops_explanations",
    )
    op.drop_index(
        "ix_auto_ops_explanations_is_fallback",
        table_name="auto_ops_explanations",
    )
    op.drop_index(
        "ix_auto_ops_explanations_severity",
        table_name="auto_ops_explanations",
    )
    op.drop_table("auto_ops_explanations")
