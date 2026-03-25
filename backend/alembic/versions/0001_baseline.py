"""Greenfield baseline — creates all tables from current ORM models.

Revision ID: 0001
Revises: (none)
Create Date: 2026-03-24
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    from backend.models import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    raise RuntimeError(
        "Downgrading past the baseline revision 0001 is disabled to avoid "
        "dropping the entire database schema."
    )
