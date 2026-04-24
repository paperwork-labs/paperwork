"""Add deploy_health_events table (G28 deploy-health guardrail, D120).

One row per observed Render deploy transition. The Beat poller inserts
into this table every 5 minutes; the ``/admin/health`` composite reads
the last N rows per service to build the ``deploys`` dimension.

Why a new table rather than extending ``job_runs``: job runs are Celery
tasks we run; deploy events are an external observability signal with
distinct cardinality, retention, and primary-key shape
(``(service_id, deploy_id, status)`` unique — a deploy can transition
through multiple terminal states if Render retries).

Revision ID: 0054
Revises: 0053
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deploy_health_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_id", sa.String(length=64), nullable=False, index=True),
        sa.Column(
            "service_slug",
            sa.String(length=128),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "service_type",
            sa.String(length=32),
            nullable=False,
            server_default="",
        ),
        sa.Column("deploy_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("status", sa.String(length=32), nullable=False, index=True),
        sa.Column("trigger", sa.String(length=64), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True, index=True),
        sa.Column("commit_message", sa.Text(), nullable=True),
        sa.Column("render_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("render_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column(
            "is_poll_error",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            index=True,
        ),
        sa.Column("poll_error_message", sa.Text(), nullable=True),
        sa.Column(
            "polled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "service_id",
            "deploy_id",
            "status",
            name="uq_deploy_health_service_deploy_status",
        ),
    )
    op.create_index(
        "ix_deploy_health_service_created",
        "deploy_health_events",
        ["service_id", "render_created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_deploy_health_service_created", table_name="deploy_health_events")
    op.drop_table("deploy_health_events")
