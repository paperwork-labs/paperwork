"""Add broker_oauth_connections table for generic OAuth broker foundation.

Stores per-user OAuth credentials for any broker that authenticates via an
OAuth flow (E*TRADE OAuth 1.0a sandbox is the first concrete adapter; future
brokers like Schwab/Fidelity OAuth 2.0 will reuse the same table).

Tokens are stored encrypted at-rest via Fernet (see
``app.services.oauth.encryption``); the ``access_token_encrypted`` and
``refresh_token_encrypted`` columns hold ciphertext, never plaintext. For
OAuth 1.0a brokers (E*TRADE) the ``refresh_token_encrypted`` column holds
the encrypted ``access_token_secret`` since OAuth 1.0a has no separate
refresh token.

Revision ID: 0043
Revises: 0040

Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0043"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broker_oauth_connections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("broker", sa.String(32), nullable=False),
        sa.Column("provider_account_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(16), nullable=False, server_default="sandbox"),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("rotation_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.CheckConstraint(
            "broker IN ('etrade_sandbox','etrade','schwab','fidelity','tastytrade','ibkr','alpaca','robinhood')",
            name="ck_broker_oauth_connections_broker",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','ACTIVE','EXPIRED','REVOKED','REFRESH_FAILED','ERROR')",
            name="ck_broker_oauth_connections_status",
        ),
        sa.CheckConstraint(
            "environment IN ('sandbox','live')",
            name="ck_broker_oauth_connections_environment",
        ),
        sa.UniqueConstraint(
            "user_id",
            "broker",
            "provider_account_id",
            name="uq_broker_oauth_user_broker_provider",
        ),
    )

    op.create_index(
        "idx_broker_oauth_user_broker",
        "broker_oauth_connections",
        ["user_id", "broker"],
    )
    op.create_index(
        "idx_broker_oauth_status_expiry",
        "broker_oauth_connections",
        ["status", "token_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_broker_oauth_status_expiry", table_name="broker_oauth_connections")
    op.drop_index("idx_broker_oauth_user_broker", table_name="broker_oauth_connections")
    op.drop_table("broker_oauth_connections")
