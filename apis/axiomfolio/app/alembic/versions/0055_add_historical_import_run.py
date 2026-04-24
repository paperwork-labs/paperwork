"""Add historical import runs + account auto-discovery flag.

Revision ID: 0055
Revises: 0054
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "broker_accounts",
        sa.Column(
            "auto_discovered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    source_enum = postgresql.ENUM(
        "FLEX_XML",
        "CSV",
        name="historicalimportsource",
        create_type=False,
    )
    status_enum = postgresql.ENUM(
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        name="historicalimportstatus",
        create_type=False,
    )
    source_enum_create = postgresql.ENUM(
        "FLEX_XML",
        "CSV",
        name="historicalimportsource",
    )
    source_enum_create.create(op.get_bind(), checkfirst=True)
    status_enum_create = postgresql.ENUM(
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        name="historicalimportstatus",
    )
    status_enum_create.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "historical_import_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("broker_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", source_enum, nullable=False),
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default="QUEUED",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "records_total",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "records_written",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "records_skipped",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "records_errors",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("import_metadata", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_historical_import_runs_user_id", "historical_import_runs", ["user_id"])
    op.create_index(
        "ix_historical_import_runs_account_id", "historical_import_runs", ["account_id"]
    )
    op.create_index(
        "ix_historical_import_runs_user_account",
        "historical_import_runs",
        ["user_id", "account_id"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO tenant_rate_limits (user_id, endpoint_pattern, bucket_size_per_minute, burst_capacity)
            VALUES
              (NULL, '/api/v1/accounts/' || chr(58) || 'id/historical-import', 3, 3),
              (NULL, '/api/v1/accounts/' || chr(58) || 'id/historical-import-csv', 10, 10)
            ON CONFLICT (user_id, endpoint_pattern) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM tenant_rate_limits
            WHERE user_id IS NULL
              AND endpoint_pattern IN (
                '/api/v1/accounts/' || chr(58) || 'id/historical-import',
                '/api/v1/accounts/' || chr(58) || 'id/historical-import-csv'
              )
            """
        )
    )

    op.drop_index("ix_historical_import_runs_user_account", table_name="historical_import_runs")
    op.drop_index("ix_historical_import_runs_account_id", table_name="historical_import_runs")
    op.drop_index("ix_historical_import_runs_user_id", table_name="historical_import_runs")
    op.drop_table("historical_import_runs")

    status_enum = postgresql.ENUM(
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        name="historicalimportstatus",
    )
    source_enum = postgresql.ENUM("FLEX_XML", "CSV", name="historicalimportsource")
    status_enum.drop(op.get_bind(), checkfirst=True)
    source_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_column("broker_accounts", "auto_discovered")
