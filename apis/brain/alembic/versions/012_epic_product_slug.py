"""Add nullable product_slug to epics for Studio product hub linking.

Revision ID: 012
Revises: 011
"""

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    ALTER TABLE epics
      ADD COLUMN IF NOT EXISTS product_slug TEXT;
    """
    )
    op.execute(
        """
    CREATE INDEX IF NOT EXISTS idx_epics_product_slug_lower
      ON epics (LOWER(product_slug));
    """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_epics_product_slug_lower;")
    op.execute("ALTER TABLE epics DROP COLUMN IF EXISTS product_slug;")
