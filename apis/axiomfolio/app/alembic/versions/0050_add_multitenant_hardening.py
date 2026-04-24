"""Multi-tenant hardening: rate limits, GDPR jobs, cost rollup, incidents.

Adds six tables that enforce per-tenant isolation across:

* Rate limiting (per-user-per-endpoint token buckets + violation log)
* GDPR data-subject rights (export + two-phase delete jobs)
* Cost attribution (daily rollup keyed on user_id)
* Incident audit (failure trail for fail-loud surfaces)

REBASE NOTE (for the merger)
----------------------------
This migration claims slot ``0050`` per ``MASTER_PLAN_2026.md`` Phase 8d.
Sibling PRs in the v1 sprint hold 0041-0049; if any of those ship with
non-linear ``revision`` / ``down_revision`` chains the merger may need
to renumber so the chain stays linear (... -> 0044 -> 0045 -> ... -> head).
The schema itself is independent of the renumber.

Revision ID: 0050
Revises: 0046
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0050"
# Chained after main tip walk-forward head (0046); multitenant hardening extends chain.
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # tenant_rate_limits
    # ------------------------------------------------------------------
    op.create_table(
        "tenant_rate_limits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("endpoint_pattern", sa.String(length=200), nullable=False),
        sa.Column("bucket_size_per_minute", sa.Integer(), nullable=False),
        sa.Column("burst_capacity", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            "endpoint_pattern",
            name="uq_tenant_rate_limits_user_endpoint",
        ),
    )
    op.create_index(
        "ix_tenant_rate_limits_user_id", "tenant_rate_limits", ["user_id"]
    )
    op.create_index(
        "ix_tenant_rate_limits_endpoint",
        "tenant_rate_limits",
        ["endpoint_pattern"],
    )

    # ------------------------------------------------------------------
    # rate_limit_violations
    # ------------------------------------------------------------------
    op.create_table(
        "rate_limit_violations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("endpoint", sa.String(length=200), nullable=False),
        sa.Column(
            "attempted_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("headers", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_rate_limit_violations_user_id",
        "rate_limit_violations",
        ["user_id"],
    )
    op.create_index(
        "ix_rate_limit_violations_endpoint",
        "rate_limit_violations",
        ["endpoint"],
    )
    op.create_index(
        "ix_rate_limit_violations_attempted_at",
        "rate_limit_violations",
        ["attempted_at"],
    )

    # ------------------------------------------------------------------
    # gdpr_export_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "gdpr_export_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "requested_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("bytes_written", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_gdpr_export_jobs_user_id", "gdpr_export_jobs", ["user_id"]
    )
    op.create_index(
        "ix_gdpr_export_user_status",
        "gdpr_export_jobs",
        ["user_id", "status"],
    )

    # ------------------------------------------------------------------
    # gdpr_delete_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "gdpr_delete_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("confirmation_token_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "requested_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_gdpr_delete_jobs_user_id", "gdpr_delete_jobs", ["user_id"]
    )
    op.create_index(
        "ix_gdpr_delete_user_status",
        "gdpr_delete_jobs",
        ["user_id", "status"],
    )

    # ------------------------------------------------------------------
    # tenant_cost_rollups
    # ------------------------------------------------------------------
    op.create_table(
        "tenant_cost_rollups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "llm_cost_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "provider_call_cost_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "storage_mb",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_cost_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "day", name="uq_tenant_cost_rollups_user_day"
        ),
    )
    op.create_index(
        "ix_tenant_cost_rollups_user_id",
        "tenant_cost_rollups",
        ["user_id"],
    )
    op.create_index(
        "ix_tenant_cost_rollups_day", "tenant_cost_rollups", ["day"]
    )

    # ------------------------------------------------------------------
    # incidents (forensic audit for fail-loud surfaces)
    # ------------------------------------------------------------------
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column(
            "severity",
            sa.String(length=16),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolved_notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_incidents_user_id", "incidents", ["user_id"])
    op.create_index("ix_incidents_category", "incidents", ["category"])
    op.create_index("ix_incidents_occurred_at", "incidents", ["occurred_at"])
    op.create_index(
        "ix_incidents_category_occurred",
        "incidents",
        ["category", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_incidents_category_occurred", table_name="incidents")
    op.drop_index("ix_incidents_occurred_at", table_name="incidents")
    op.drop_index("ix_incidents_category", table_name="incidents")
    op.drop_index("ix_incidents_user_id", table_name="incidents")
    op.drop_table("incidents")

    op.drop_index("ix_tenant_cost_rollups_day", table_name="tenant_cost_rollups")
    op.drop_index(
        "ix_tenant_cost_rollups_user_id", table_name="tenant_cost_rollups"
    )
    op.drop_table("tenant_cost_rollups")

    op.drop_index("ix_gdpr_delete_user_status", table_name="gdpr_delete_jobs")
    op.drop_index("ix_gdpr_delete_jobs_user_id", table_name="gdpr_delete_jobs")
    op.drop_table("gdpr_delete_jobs")

    op.drop_index("ix_gdpr_export_user_status", table_name="gdpr_export_jobs")
    op.drop_index("ix_gdpr_export_jobs_user_id", table_name="gdpr_export_jobs")
    op.drop_table("gdpr_export_jobs")

    op.drop_index(
        "ix_rate_limit_violations_attempted_at", table_name="rate_limit_violations"
    )
    op.drop_index(
        "ix_rate_limit_violations_endpoint", table_name="rate_limit_violations"
    )
    op.drop_index(
        "ix_rate_limit_violations_user_id", table_name="rate_limit_violations"
    )
    op.drop_table("rate_limit_violations")

    op.drop_index(
        "ix_tenant_rate_limits_endpoint", table_name="tenant_rate_limits"
    )
    op.drop_index("ix_tenant_rate_limits_user_id", table_name="tenant_rate_limits")
    op.drop_table("tenant_rate_limits")
