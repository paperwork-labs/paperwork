"""Update category unique constraint to include category_type

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-02-23

"""
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE categories SET category_type = 'custom' WHERE category_type IS NULL")
    op.execute("ALTER TABLE categories DROP CONSTRAINT IF EXISTS uq_category_user_name")
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE categories
                ADD CONSTRAINT uq_category_user_name_type UNIQUE (user_id, name, category_type);
        EXCEPTION WHEN duplicate_table OR duplicate_object THEN
            NULL;
        END $$;
    """)


def downgrade() -> None:
    op.drop_constraint("uq_category_user_name_type", "categories", type_="unique")
    op.create_unique_constraint(
        "uq_category_user_name",
        "categories",
        ["user_id", "name"],
    )
