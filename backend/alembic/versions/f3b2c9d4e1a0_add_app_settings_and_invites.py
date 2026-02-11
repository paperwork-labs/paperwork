"""Add app settings + user invites + analyst role.

Revision ID: f3b2c9d4e1a0
Revises: 8c1f2e9b7a12
Create Date: 2026-02-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f3b2c9d4e1a0"
down_revision = "8c1f2e9b7a12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    # Add ANALYST role to enum (stored as enum name strings).
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'ANALYST'")

    if "app_settings" not in table_names:
        op.create_table(
            "app_settings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "market_only_mode",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "portfolio_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "strategy_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
        )
    existing_app_settings_cols = {
        col["name"] for col in sa.inspect(bind).get_columns("app_settings")
    } if "app_settings" in set(sa.inspect(bind).get_table_names()) else set()
    if "app_settings" in set(sa.inspect(bind).get_table_names()):
        if "portfolio_enabled" not in existing_app_settings_cols:
            op.add_column(
                "app_settings",
                sa.Column(
                    "portfolio_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
            )
        if "strategy_enabled" not in existing_app_settings_cols:
            op.add_column(
                "app_settings",
                sa.Column(
                    "strategy_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
            )

    if "user_invites" not in table_names:
        op.create_table(
            "user_invites",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column(
                "role",
                postgresql.ENUM(
                    "ADMIN",
                    "USER",
                    "READONLY",
                    "ANALYST",
                    name="userrole",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("token", sa.String(length=64), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.UniqueConstraint("email"),
            sa.UniqueConstraint("token"),
        )

    if "user_invites" in set(sa.inspect(bind).get_table_names()):
        existing_indexes = {
            idx["name"] for idx in sa.inspect(bind).get_indexes("user_invites")
        }
        if "ix_user_invites_email" not in existing_indexes:
            op.create_index("ix_user_invites_email", "user_invites", ["email"])
        if "ix_user_invites_token" not in existing_indexes:
            op.create_index("ix_user_invites_token", "user_invites", ["token"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "user_invites" in table_names:
        existing_indexes = {
            idx["name"] for idx in inspector.get_indexes("user_invites")
        }
        if "ix_user_invites_token" in existing_indexes:
            op.drop_index("ix_user_invites_token", table_name="user_invites")
        if "ix_user_invites_email" in existing_indexes:
            op.drop_index("ix_user_invites_email", table_name="user_invites")
        op.drop_table("user_invites")
    if "app_settings" in table_names:
        op.drop_table("app_settings")
    # NOTE: Postgres enums can't easily remove values; we intentionally leave ANALYST.
