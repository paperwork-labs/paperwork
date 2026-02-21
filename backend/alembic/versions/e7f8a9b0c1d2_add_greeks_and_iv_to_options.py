"""add greeks and iv to options

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-02-19

"""

from alembic import op
import sqlalchemy as sa

revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("options"):
        return
    existing = {c["name"] for c in insp.get_columns("options")}
    cols = [
        ("delta", sa.Numeric(10, 6), True),
        ("gamma", sa.Numeric(10, 6), True),
        ("theta", sa.Numeric(10, 6), True),
        ("vega", sa.Numeric(10, 6), True),
        ("implied_volatility", sa.Numeric(10, 4), True),
    ]
    for name, col_type, nullable in cols:
        if name not in existing:
            op.add_column("options", sa.Column(name, col_type, nullable=nullable))


def downgrade() -> None:
    with op.batch_alter_table("options") as batch_op:
        batch_op.drop_column("implied_volatility")
        batch_op.drop_column("vega")
        batch_op.drop_column("theta")
        batch_op.drop_column("gamma")
        batch_op.drop_column("delta")
