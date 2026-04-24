"""Add entitlements table (six-tier subscription mirror).

Adds the single source of truth for tier-gated feature access. One row per
user, with a unique constraint on user_id (1:1 with users). Stripe webhook
handlers and the EntitlementService write to this table; nothing else does.

Backfill: every existing user gets a FREE/ACTIVE row in the same migration
so the tier-gating dependency never sees a NULL on first call (which would
otherwise force a flush mid-request and complicate transaction boundaries).

Revision ID: 0031
Revises: 0021
Create Date: 2026-04-18

REBASE NOTE (for the merger):
This migration is intentionally numbered 0031 and chains directly off 0021
(the current `main` head as of branch creation) to keep this PR independently
mergeable while PR #321 (which adds 0022) and the picks PR #327 (0030) are
also in flight. When merging, pick whichever order works and renumber the
revision + down_revision so the chain ends up linear (0022 -> 0023 ... ->
final). The table contents are unaffected by the renumber.
"""

from alembic import op
import sqlalchemy as sa


revision = "0031"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entitlements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SubscriptionTier enum stored as VARCHAR (matches engineering.mdc
        # convention: avoid PostgreSQL native enums so adding a value never
        # requires an ALTER TYPE).
        sa.Column(
            "tier",
            sa.String(20),
            nullable=False,
            server_default="free",
        ),
        sa.Column(
            "status",
            sa.String(24),
            nullable=False,
            server_default="active",
        ),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
        sa.Column("stripe_price_id", sa.String(64), nullable=True),
        sa.Column("current_period_start", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("metadata", sa.JSON(), nullable=True),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", name="uq_entitlements_user_id"),
        # CHECK constraints mirror the SubscriptionTier / EntitlementStatus
        # enums in backend/models/entitlement.py. Adding a value to either
        # enum requires a follow-up migration that rewrites the CHECK -- a
        # deliberate trade-off so a typo in code can't widen the allowed set
        # silently. (We avoid native Postgres ENUM so we don't pay the
        # ALTER TYPE round-trip; CHECK gives the same safety with cheaper
        # evolution.)
        sa.CheckConstraint(
            "tier IN ('free','lite','pro','pro_plus','quant_desk','enterprise')",
            name="ck_entitlements_tier",
        ),
        # ``manual`` is intentionally included: it covers internal grants
        # (validator pseudonym holders, founding hedge-fund partner,
        # employee comp accounts) that should not be overwritten by
        # Stripe webhook drift. See backend/models/entitlement.py.
        # Hotfix 0033 widens this constraint on environments that already
        # ran 0031 with the narrower set; new envs get the right list
        # directly here.
        sa.CheckConstraint(
            "status IN ('active','trialing','past_due','canceled','incomplete','manual')",
            name="ck_entitlements_status",
        ),
        # stripe_subscription_id is unique when set; partial unique below
    )
    op.create_index(
        "ix_entitlements_user_id", "entitlements", ["user_id"], unique=True
    )
    op.create_index(
        "ix_entitlements_stripe_customer_id",
        "entitlements",
        ["stripe_customer_id"],
    )
    op.create_index(
        "ix_entitlements_tier_status",
        "entitlements",
        ["tier", "status"],
    )
    # Partial unique index: stripe_subscription_id must be unique when not
    # NULL. We can't use a plain UniqueConstraint because every FREE-tier
    # user has NULL here and Postgres treats NULLs as distinct (fine) but
    # SQLAlchemy's UniqueConstraint surfaces nulls inconsistently across
    # backends.
    op.create_index(
        "uq_entitlements_stripe_sub_id",
        "entitlements",
        ["stripe_subscription_id"],
        unique=True,
        postgresql_where=sa.text("stripe_subscription_id IS NOT NULL"),
    )

    # Backfill: every existing user gets a FREE/ACTIVE entitlement row.
    # We use raw SQL rather than the ORM so this works in the smallest
    # alembic context (no Base import dance, no risk of model drift while
    # the migration runs).
    op.execute(
        """
        INSERT INTO entitlements (user_id, tier, status, metadata, created_at, updated_at)
        SELECT
            u.id,
            'free',
            'active',
            '{"source": "0031_backfill"}'::json,
            NOW(),
            NOW()
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM entitlements e WHERE e.user_id = u.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("uq_entitlements_stripe_sub_id", table_name="entitlements")
    op.drop_index("ix_entitlements_tier_status", table_name="entitlements")
    op.drop_index(
        "ix_entitlements_stripe_customer_id", table_name="entitlements"
    )
    op.drop_index("ix_entitlements_user_id", table_name="entitlements")
    op.drop_table("entitlements")
