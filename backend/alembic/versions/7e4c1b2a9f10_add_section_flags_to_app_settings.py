"""Add per-section release flags to app settings.

Revision ID: 7e4c1b2a9f10
Revises: f3b2c9d4e1a0
Create Date: 2026-02-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7e4c1b2a9f10"
down_revision = "f3b2c9d4e1a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Compatibility migration:
    # In some environments, revision f3b2c9d4e1a0 may have been applied before
    # section flags existed there. Keep this additive/idempotent backfill so
    # already-migrated DBs still receive portfolio/strategy flags.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "app_settings" not in set(inspector.get_table_names()):
        return

    cols = {col["name"] for col in inspector.get_columns("app_settings")}
    if "portfolio_enabled" not in cols:
        op.add_column(
            "app_settings",
            sa.Column(
                "portfolio_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if "strategy_enabled" not in cols:
        op.add_column(
            "app_settings",
            sa.Column(
                "strategy_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "app_settings" not in set(inspector.get_table_names()):
        return

    cols = {col["name"] for col in inspector.get_columns("app_settings")}
    if "strategy_enabled" in cols:
        op.drop_column("app_settings", "strategy_enabled")
    if "portfolio_enabled" in cols:
        op.drop_column("app_settings", "portfolio_enabled")
