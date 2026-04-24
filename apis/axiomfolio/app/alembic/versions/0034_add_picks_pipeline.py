"""Add picks pipeline tables.

Creates the data layer for the v1 Validated Picks product:

* email_inbox          — raw incoming validator emails
* email_parses         — LLM parse attempts (1:N per email per schema)
* candidates           — system-generated trade candidates
* validated_picks      — published picks (the actual product)
* pick_engagements     — per-user interactions (viewed, executed, ...)
* source_attributions  — N:M provenance for any published artifact
* macro_outlooks       — "I think we're in R3" calls
* position_changes     — standalone trim/add guidance

All tables use VARCHAR for enums (engineering.mdc convention; avoid PG
native enum types so adding a value never requires ALTER TYPE).

REBASE NOTE
-----------
Originally numbered 0030/0021 when the picks branch was cut. After
PR #326 (entitlements, 0031) and PR #338 (entitlements hotfix, 0033)
merged ahead of this branch, this migration is renumbered to 0034 and
chained off 0033 so the chain stays linear:
0021 -> 0031 -> 0033 -> 0034.

Revision ID: 0034
Revises: 0033
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # email_inbox
    # ------------------------------------------------------------------
    op.create_table(
        "email_inbox",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("source_label", sa.String(64), nullable=False),
        sa.Column("sender", sa.String(255), nullable=False),
        sa.Column("recipients", sa.JSON(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "has_pdf",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "attachment_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("attachments_meta", sa.JSON(), nullable=True),
        sa.Column("raw_blob_url", sa.String(512), nullable=True),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # RFC 5322 Message-ID is intended to be globally unique; we dedupe
        # raw ingestion on it so the same MIME message is not stored twice.
        sa.UniqueConstraint("message_id", name="uq_email_inbox_message_id"),
    )
    op.create_index("ix_email_inbox_message_id", "email_inbox", ["message_id"], unique=True)
    op.create_index("ix_email_inbox_source_label", "email_inbox", ["source_label"])
    op.create_index("ix_email_inbox_sender", "email_inbox", ["sender"])
    op.create_index("ix_email_inbox_received_at", "email_inbox", ["received_at"])
    op.create_index(
        "ix_email_inbox_source_received", "email_inbox", ["source_label", "received_at"]
    )
    op.create_index(
        "ix_email_inbox_sender_received", "email_inbox", ["sender", "received_at"]
    )

    # ------------------------------------------------------------------
    # email_parses
    # ------------------------------------------------------------------
    op.create_table(
        "email_parses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "email_id",
            sa.Integer(),
            sa.ForeignKey("email_inbox.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("parser_model", sa.String(64), nullable=False),
        sa.Column("parser_provider", sa.String(32), nullable=True),
        sa.Column("parser_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("parser_tokens_in", sa.Integer(), nullable=True),
        sa.Column("parser_tokens_out", sa.Integer(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("structured_output", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "parsed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "email_id", "schema_version", "parser_model",
            name="uq_email_parse_schema_model",
        ),
    )
    op.create_index("ix_email_parses_email_id", "email_parses", ["email_id"])
    op.create_index(
        "ix_email_parse_status_parsed", "email_parses", ["status", "parsed_at"]
    )

    # ------------------------------------------------------------------
    # validated_picks (created before candidates because candidates carries
    # an FK back to validated_picks for promoted picks)
    # ------------------------------------------------------------------
    op.create_table(
        "validated_picks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_email_parse_id",
            sa.Integer(),
            sa.ForeignKey("email_parses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # The candidate FK is added in a second pass below to break the
        # circular dependency with the candidates table.
        sa.Column("promoted_from_candidate_id", sa.Integer(), nullable=True),
        sa.Column(
            "validator_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "validator_pseudonym",
            sa.String(64),
            nullable=False,
            server_default="Twisted Slice",
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column(
            "conviction", sa.Integer(), nullable=False, server_default=sa.text("3")
        ),
        sa.Column("reason_summary", sa.Text(), nullable=False),
        sa.Column("full_rationale", sa.Text(), nullable=True),
        sa.Column("suggested_entry", sa.Numeric(18, 6), nullable=True),
        sa.Column("suggested_stop", sa.Numeric(18, 6), nullable=True),
        sa.Column("suggested_target", sa.Numeric(18, 6), nullable=True),
        sa.Column("suggested_size_pct", sa.Numeric(6, 4), nullable=True),
        sa.Column(
            "validity_window_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("10"),
        ),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "superseded_by_id",
            sa.Integer(),
            sa.ForeignKey("validated_picks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_validated_picks_source_email_parse_id",
        "validated_picks",
        ["source_email_parse_id"],
    )
    op.create_index(
        "ix_validated_picks_promoted_from_candidate_id",
        "validated_picks",
        ["promoted_from_candidate_id"],
    )
    op.create_index(
        "ix_validated_picks_validator_user_id",
        "validated_picks",
        ["validator_user_id"],
    )
    op.create_index("ix_validated_picks_symbol", "validated_picks", ["symbol"])
    op.create_index("ix_validated_picks_status", "validated_picks", ["status"])
    op.create_index(
        "ix_validated_picks_expires_at", "validated_picks", ["expires_at"]
    )
    op.create_index(
        "ix_picks_symbol_status_published",
        "validated_picks",
        ["symbol", "status", "published_at"],
    )
    op.create_index(
        "ix_picks_status_expires",
        "validated_picks",
        ["status", "expires_at"],
    )

    # ------------------------------------------------------------------
    # candidates (FK to validated_picks for promoted)
    # ------------------------------------------------------------------
    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("generator_name", sa.String(64), nullable=False),
        sa.Column("generator_version", sa.String(32), nullable=False),
        sa.Column("score", sa.Numeric(10, 4), nullable=True),
        sa.Column("action_suggestion", sa.String(16), nullable=False),
        sa.Column("signals", sa.JSON(), nullable=True),
        sa.Column("rationale_summary", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(24),
            nullable=False,
            server_default="pending_review",
        ),
        sa.Column(
            "promoted_to_pick_id",
            sa.Integer(),
            sa.ForeignKey("validated_picks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_candidates_symbol", "candidates", ["symbol"])
    op.create_index("ix_candidates_generator_name", "candidates", ["generator_name"])
    op.create_index("ix_candidates_status", "candidates", ["status"])
    op.create_index(
        "ix_candidates_symbol_generated", "candidates", ["symbol", "generated_at"]
    )
    op.create_index(
        "ix_candidates_status_score", "candidates", ["status", "score"]
    )

    # Now backfill the FK from validated_picks → candidates.
    op.create_foreign_key(
        "fk_validated_picks_promoted_from_candidate_id",
        "validated_picks",
        "candidates",
        ["promoted_from_candidate_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # pick_engagements
    # ------------------------------------------------------------------
    op.create_table(
        "pick_engagements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "pick_id",
            sa.Integer(),
            sa.ForeignKey("validated_picks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("engagement_type", sa.String(24), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "pick_id", "user_id", "engagement_type",
            name="uq_pick_engagement_user_type",
        ),
    )
    op.create_index("ix_pick_engagements_pick_id", "pick_engagements", ["pick_id"])
    op.create_index("ix_pick_engagements_user_id", "pick_engagements", ["user_id"])
    op.create_index(
        "ix_pick_engagement_user_occurred",
        "pick_engagements",
        ["user_id", "occurred_at"],
    )

    # ------------------------------------------------------------------
    # source_attributions
    # ------------------------------------------------------------------
    op.create_table(
        "source_attributions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("artifact_kind", sa.String(32), nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(24), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column(
            "source_email_id",
            sa.Integer(),
            sa.ForeignKey("email_inbox.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_attribution_artifact_kind", "source_attributions", ["artifact_kind"]
    )
    op.create_index(
        "ix_attribution_artifact",
        "source_attributions",
        ["artifact_kind", "artifact_id"],
    )
    op.create_index(
        "ix_attribution_source_email", "source_attributions", ["source_email_id"]
    )

    # ------------------------------------------------------------------
    # macro_outlooks
    # ------------------------------------------------------------------
    op.create_table(
        "macro_outlooks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_email_parse_id",
            sa.Integer(),
            sa.ForeignKey("email_parses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "validator_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "validator_pseudonym",
            sa.String(64),
            nullable=False,
            server_default="Twisted Slice",
        ),
        sa.Column("regime_call", sa.String(8), nullable=True),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("time_horizon_days", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_macro_outlooks_source_email_parse_id",
        "macro_outlooks",
        ["source_email_parse_id"],
    )
    op.create_index(
        "ix_macro_outlooks_validator_user_id",
        "macro_outlooks",
        ["validator_user_id"],
    )
    op.create_index("ix_macro_outlooks_status", "macro_outlooks", ["status"])
    op.create_index("ix_macro_outlook_published", "macro_outlooks", ["published_at"])

    # ------------------------------------------------------------------
    # position_changes
    # ------------------------------------------------------------------
    op.create_table(
        "position_changes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_email_parse_id",
            sa.Integer(),
            sa.ForeignKey("email_parses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "validator_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "validator_pseudonym",
            sa.String(64),
            nullable=False,
            server_default="Twisted Slice",
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("size_change_pct", sa.Numeric(6, 4), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_position_changes_source_email_parse_id",
        "position_changes",
        ["source_email_parse_id"],
    )
    op.create_index(
        "ix_position_changes_validator_user_id",
        "position_changes",
        ["validator_user_id"],
    )
    op.create_index("ix_position_changes_symbol", "position_changes", ["symbol"])
    op.create_index("ix_position_changes_status", "position_changes", ["status"])
    op.create_index(
        "ix_position_change_symbol_published",
        "position_changes",
        ["symbol", "published_at"],
    )


def downgrade() -> None:
    op.drop_table("position_changes")
    op.drop_table("macro_outlooks")
    op.drop_table("source_attributions")
    op.drop_table("pick_engagements")
    op.drop_constraint(
        "fk_validated_picks_promoted_from_candidate_id",
        "validated_picks",
        type_="foreignkey",
    )
    op.drop_table("candidates")
    op.drop_table("validated_picks")
    op.drop_table("email_parses")
    op.drop_table("email_inbox")
