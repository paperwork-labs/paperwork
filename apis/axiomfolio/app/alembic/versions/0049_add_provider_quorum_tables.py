"""Add provider_quorum_log and provider_drift_alerts tables.

Multi-source quorum and drift detection layer. For critical fields (price,
volume, fundamentals) we cross-check N providers and require majority
agreement. Disagreements are flagged (NEVER silently resolved). Per-provider
historical drift is tracked separately so a single rogue provider can be
surfaced before its values poison ``MarketSnapshot`` / ``PriceData``.

Schema:

* ``provider_quorum_log`` -- one row per quorum check (sampled, not on
  every read). Captures the value each provider returned, the agreed-on
  ``quorum_value`` (if any), the threshold used, the disagreement
  spread, and the action taken downstream.
* ``provider_drift_alerts`` -- one row per detected per-provider drift
  event (value outside ``mean +/- 3 sigma`` of that provider's recent
  history). Resolvable by an operator.

REBASE NOTE (for the merger)
----------------------------
This migration is intentionally numbered 0049. Sibling PRs in the v1
``feat/wc-*`` sprint reserve 0041..0048; the merger may renumber
``revision`` / ``down_revision`` so the chain stays linear (... -> 0040
-> 0041 -> ... -> head). The schema itself is unaffected by the
renumber. We chain off 0040 (the head at branch-creation time) so this
migration applies cleanly on top of ``main`` without depending on any
in-flight sibling.

Revision ID: 0049
Revises: 0040
Create Date: 2026-04-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0049"
down_revision = "0047"
branch_labels = None
depends_on = None


QUORUM_STATUS_ENUM = "provider_quorum_status_enum"
QUORUM_ACTION_ENUM = "provider_quorum_action_enum"


def upgrade() -> None:
    quorum_status = postgresql.ENUM(
        "QUORUM_REACHED",
        "DISAGREEMENT",
        "INSUFFICIENT_PROVIDERS",
        "SINGLE_SOURCE",
        name=QUORUM_STATUS_ENUM,
        create_type=True,
    )
    quorum_action = postgresql.ENUM(
        "ACCEPTED",
        "REJECTED",
        "FLAGGED_FOR_REVIEW",
        name=QUORUM_ACTION_ENUM,
        create_type=True,
    )
    bind = op.get_bind()
    quorum_status.create(bind, checkfirst=True)
    quorum_action.create(bind, checkfirst=True)

    op.create_table(
        "provider_quorum_log",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column(
            "check_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "providers_queried",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("quorum_value", sa.Numeric(precision=24, scale=10), nullable=True),
        sa.Column(
            "quorum_threshold",
            sa.Numeric(precision=4, scale=3),
            nullable=False,
            server_default=sa.text("0.667"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name=QUORUM_STATUS_ENUM, create_type=False),
            nullable=False,
        ),
        sa.Column(
            "max_disagreement_pct",
            sa.Numeric(precision=10, scale=6),
            nullable=True,
        ),
        sa.Column(
            "action_taken",
            postgresql.ENUM(name=QUORUM_ACTION_ENUM, create_type=False),
            nullable=False,
        ),
    )
    op.create_index("ix_provider_quorum_log_symbol", "provider_quorum_log", ["symbol"])
    op.create_index(
        "ix_provider_quorum_log_field_name",
        "provider_quorum_log",
        ["field_name"],
    )
    op.create_index(
        "ix_provider_quorum_log_check_at",
        "provider_quorum_log",
        ["check_at"],
    )
    op.create_index(
        "ix_provider_quorum_log_status",
        "provider_quorum_log",
        ["status"],
    )
    # Composite for the "find recent disagreements" admin query.
    op.create_index(
        "idx_provider_quorum_status_check_at",
        "provider_quorum_log",
        ["status", "check_at"],
    )
    # Idempotency guard: hourly sampler must not write two rows for the
    # same (symbol, field, second). The sampler floors check_at to the
    # second; this unique index makes a duplicate run a NOOP rather
    # than corrupting analytics.
    op.create_index(
        "uq_provider_quorum_symbol_field_check_at",
        "provider_quorum_log",
        ["symbol", "field_name", "check_at"],
        unique=True,
    )

    op.create_table(
        "provider_drift_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column(
            "expected_range",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("actual_value", sa.Numeric(precision=24, scale=10), nullable=False),
        sa.Column(
            "deviation_pct",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column(
            "alert_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_provider_drift_alerts_symbol",
        "provider_drift_alerts",
        ["symbol"],
    )
    op.create_index(
        "ix_provider_drift_alerts_provider",
        "provider_drift_alerts",
        ["provider"],
    )
    op.create_index(
        "ix_provider_drift_alerts_alert_at",
        "provider_drift_alerts",
        ["alert_at"],
    )
    # Open-vs-resolved is the dominant admin filter; index resolved_at
    # so partial-NULL scans stay cheap.
    op.create_index(
        "ix_provider_drift_alerts_resolved_at",
        "provider_drift_alerts",
        ["resolved_at"],
    )
    op.create_index(
        "idx_provider_drift_open",
        "provider_drift_alerts",
        ["resolved_at", "alert_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_provider_drift_open", table_name="provider_drift_alerts")
    op.drop_index(
        "ix_provider_drift_alerts_resolved_at",
        table_name="provider_drift_alerts",
    )
    op.drop_index(
        "ix_provider_drift_alerts_alert_at",
        table_name="provider_drift_alerts",
    )
    op.drop_index(
        "ix_provider_drift_alerts_provider",
        table_name="provider_drift_alerts",
    )
    op.drop_index(
        "ix_provider_drift_alerts_symbol",
        table_name="provider_drift_alerts",
    )
    op.drop_table("provider_drift_alerts")

    op.drop_index(
        "uq_provider_quorum_symbol_field_check_at",
        table_name="provider_quorum_log",
    )
    op.drop_index(
        "idx_provider_quorum_status_check_at",
        table_name="provider_quorum_log",
    )
    op.drop_index(
        "ix_provider_quorum_log_status",
        table_name="provider_quorum_log",
    )
    op.drop_index(
        "ix_provider_quorum_log_check_at",
        table_name="provider_quorum_log",
    )
    op.drop_index(
        "ix_provider_quorum_log_field_name",
        table_name="provider_quorum_log",
    )
    op.drop_index(
        "ix_provider_quorum_log_symbol",
        table_name="provider_quorum_log",
    )
    op.drop_table("provider_quorum_log")

    bind = op.get_bind()
    postgresql.ENUM(name=QUORUM_ACTION_ENUM, create_type=False).drop(bind, checkfirst=True)
    postgresql.ENUM(name=QUORUM_STATUS_ENUM, create_type=False).drop(bind, checkfirst=True)
