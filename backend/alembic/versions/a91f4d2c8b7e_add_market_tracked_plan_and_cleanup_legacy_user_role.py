"""Add market tracked plan + cleanup legacy user role.

Revision ID: a91f4d2c8b7e
Revises: 7e4c1b2a9f10
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a91f4d2c8b7e"
down_revision = "7e4c1b2a9f10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "market_tracked_plan" not in table_names:
        op.create_table(
            "market_tracked_plan",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("symbol", sa.String(length=20), nullable=False),
            sa.Column("entry_price", sa.Float(), nullable=True),
            sa.Column("exit_price", sa.Float(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
            sa.UniqueConstraint("symbol", name="uq_market_tracked_plan_symbol"),
        )
    existing_indexes = {
        idx["name"] for idx in sa.inspect(bind).get_indexes("market_tracked_plan")
    } if "market_tracked_plan" in set(sa.inspect(bind).get_table_names()) else set()
    if "ix_market_tracked_plan_symbol" not in existing_indexes:
        op.create_index("ix_market_tracked_plan_symbol", "market_tracked_plan", ["symbol"])
    if "ix_market_tracked_plan_updated_by_user_id" not in existing_indexes:
        op.create_index("ix_market_tracked_plan_updated_by_user_id", "market_tracked_plan", ["updated_by_user_id"])

    # Canonical role cleanup: migrate legacy USER to READONLY.
    if "users" in table_names:
        op.execute("UPDATE users SET role = 'READONLY' WHERE role = 'USER'")
    if "user_invites" in table_names:
        op.execute("UPDATE user_invites SET role = 'READONLY' WHERE role = 'USER'")


def downgrade() -> None:
    op.drop_index("ix_market_tracked_plan_updated_by_user_id", table_name="market_tracked_plan")
    op.drop_index("ix_market_tracked_plan_symbol", table_name="market_tracked_plan")
    op.drop_table("market_tracked_plan")
