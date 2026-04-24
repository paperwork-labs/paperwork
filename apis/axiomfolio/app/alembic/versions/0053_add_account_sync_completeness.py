"""Add G22 sync-completeness fields to account_syncs.

Adds five JSON columns so each sync row records the structured outcome of
``CompletenessReport`` (see ``app/services/portfolio/ibkr/sync_validator``):

* ``warnings`` — list of structured warning dicts (level/section/code/message)
* ``expected_sections`` — canonical list of FlexQuery sections we asked for
* ``received_sections`` — sections actually present in the XML
* ``missing_sections`` — combined required+optional missing list
* ``section_row_counts`` — section -> row count discovered in the XML

Why JSON rather than narrow columns: the validator's vocabulary is going to
expand as we cover Schwab and TastyTrade (G24/G25); per-row JSON keeps the
schema stable while we iterate. Server defaults keep legacy rows readable
without backfill.

Closes the silent-partial-success gap (G22) end-to-end: pipeline now sets
``status: "partial"`` when sections are missing, ``broker_sync_service``
honours that status (no longer forces SUCCESS unconditionally), and the
Celery task persists the structured report to this row.

Revision ID: 0053
Revises: 0052
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account_syncs",
        sa.Column("warnings", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "account_syncs",
        sa.Column("expected_sections", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "account_syncs",
        sa.Column("received_sections", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "account_syncs",
        sa.Column("missing_sections", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "account_syncs",
        sa.Column("section_row_counts", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("account_syncs", "section_row_counts")
    op.drop_column("account_syncs", "missing_sections")
    op.drop_column("account_syncs", "received_sections")
    op.drop_column("account_syncs", "expected_sections")
    op.drop_column("account_syncs", "warnings")
