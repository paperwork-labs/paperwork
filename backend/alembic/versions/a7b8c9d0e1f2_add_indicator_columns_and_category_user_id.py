"""Add indicator columns and category user_id

Revision ID: a7b8c9d0e1f2
Revises: f4e5d6c7b8a9
Create Date: 2026-02-23

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "a7b8c9d0e1f2"
down_revision = "f4e5d6c7b8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add indicator columns to market_snapshot (IF NOT EXISTS for idempotency with create_all / reruns)
    for col in [
        "macd_histogram",
        "adx",
        "plus_di",
        "minus_di",
        "bollinger_upper",
        "bollinger_lower",
        "bollinger_width",
        "high_52w",
        "low_52w",
        "stoch_rsi",
        "volume_avg_20d",
    ]:
        op.execute(
            f"ALTER TABLE market_snapshot ADD COLUMN IF NOT EXISTS {col} DOUBLE PRECISION"
        )
        op.execute(
            f"ALTER TABLE market_snapshot_history ADD COLUMN IF NOT EXISTS {col} DOUBLE PRECISION"
        )

    # Drop old unique on name (IF EXISTS – baseline create_all may already use the final schema)
    op.execute("ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_name_key")

    # Add user_id to categories
    op.execute(
        "ALTER TABLE categories ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)"
    )

    # Add unique constraint on (user_id, name) – skip if it already exists
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE categories
                ADD CONSTRAINT uq_category_user_name UNIQUE (user_id, name);
        EXCEPTION WHEN duplicate_table OR duplicate_object THEN
            NULL;
        END $$;
    """)


def downgrade() -> None:
    op.drop_constraint("uq_category_user_name", "categories", type_="unique")
    op.drop_column("categories", "user_id")

    # Restore original unique on name
    op.create_unique_constraint("categories_name_key", "categories", ["name"])

    for col in [
        "volume_avg_20d",
        "stoch_rsi",
        "low_52w",
        "high_52w",
        "bollinger_width",
        "bollinger_lower",
        "bollinger_upper",
        "minus_di",
        "plus_di",
        "adx",
        "macd_histogram",
    ]:
        op.drop_column("market_snapshot_history", col)
        op.drop_column("market_snapshot", col)
