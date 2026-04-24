"""Picks candidate queue states + audit + publish metadata.

Adds validator workflow columns on ``candidates`` (state transition audit,
optional email-parse provenance, suggested prices, ``published_at``),
creates ``picks_audit_log`` for transition history, and migrates legacy
``candidate_status`` string values to the queue model:

* pending_review -> draft
* promoted       -> published (``published_at`` backfilled)
* rejected       -> rejected
* expired        -> rejected

Revision ID: 0039
Revises: 0038
Create Date: 2026-04-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "picks_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("from_state", sa.String(24), nullable=False),
        sa.Column("to_state", sa.String(24), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_picks_audit_log_candidate_created",
        "picks_audit_log",
        ["candidate_id", "created_at"],
    )

    op.add_column(
        "candidates",
        sa.Column("state_transitioned_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "candidates",
        sa.Column(
            "state_transitioned_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "candidates",
        sa.Column(
            "source_email_parse_id",
            sa.Integer(),
            sa.ForeignKey("email_parses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "candidates",
        sa.Column("suggested_target", sa.Numeric(18, 6), nullable=True),
    )
    op.add_column(
        "candidates",
        sa.Column("suggested_stop", sa.Numeric(18, 6), nullable=True),
    )
    op.add_column(
        "candidates",
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_candidates_published_at",
        "candidates",
        ["published_at"],
    )
    op.create_index(
        "ix_candidates_source_email_parse_id",
        "candidates",
        ["source_email_parse_id"],
    )

    op.execute(
        sa.text(
            """
            UPDATE candidates
            SET published_at = COALESCE(decided_at, generated_at)
            WHERE status = 'promoted'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE candidates
            SET status = CASE status
                WHEN 'pending_review' THEN 'draft'
                WHEN 'promoted' THEN 'published'
                WHEN 'rejected' THEN 'rejected'
                WHEN 'expired' THEN 'rejected'
                ELSE 'draft'
            END
            """
        )
    )
    op.alter_column(
        "candidates",
        "status",
        server_default="draft",
        existing_type=sa.String(24),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "candidates",
        "status",
        server_default="pending_review",
        existing_type=sa.String(24),
        existing_nullable=False,
    )
    op.execute(
        sa.text(
            """
            UPDATE candidates
            SET status = CASE status
                WHEN 'draft' THEN 'pending_review'
                WHEN 'approved' THEN 'pending_review'
                WHEN 'published' THEN 'promoted'
                WHEN 'rejected' THEN 'rejected'
                ELSE 'pending_review'
            END
            """
        )
    )

    op.drop_index("ix_candidates_source_email_parse_id", table_name="candidates")
    op.drop_index("ix_candidates_published_at", table_name="candidates")
    op.drop_column("candidates", "published_at")
    op.drop_column("candidates", "suggested_stop")
    op.drop_column("candidates", "suggested_target")
    op.drop_column("candidates", "source_email_parse_id")
    op.drop_column("candidates", "state_transitioned_by")
    op.drop_column("candidates", "state_transitioned_at")

    op.drop_index("ix_picks_audit_log_candidate_created", table_name="picks_audit_log")
    op.drop_table("picks_audit_log")
