"""Migrate users.role and user_invites.role from PG enum to VARCHAR (owner/analyst/viewer).

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role_new", sa.String(length=20), nullable=True))
    op.add_column("user_invites", sa.Column("role_new", sa.String(length=20), nullable=True))

    op.execute(
        """
        UPDATE users SET role_new = CASE role::text
            WHEN 'ADMIN' THEN 'owner'
            WHEN 'USER' THEN 'analyst'
            WHEN 'READONLY' THEN 'viewer'
            WHEN 'ANALYST' THEN 'analyst'
            ELSE 'analyst'
        END
        """
    )
    op.execute(
        """
        UPDATE user_invites SET role_new = CASE role::text
            WHEN 'ADMIN' THEN 'owner'
            WHEN 'USER' THEN 'analyst'
            WHEN 'READONLY' THEN 'viewer'
            WHEN 'ANALYST' THEN 'analyst'
            ELSE 'viewer'
        END
        """
    )

    op.drop_column("users", "role")
    op.drop_column("user_invites", "role")
    op.execute("DROP TYPE IF EXISTS userrole")

    op.execute("ALTER TABLE users RENAME COLUMN role_new TO role")
    op.execute("ALTER TABLE user_invites RENAME COLUMN role_new TO role")

    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default="analyst",
    )
    op.alter_column(
        "user_invites",
        "role",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default="viewer",
    )


def downgrade() -> None:
    from sqlalchemy.dialects import postgresql

    bind = op.get_bind()
    userrole = postgresql.ENUM(
        "ADMIN",
        "USER",
        "READONLY",
        "ANALYST",
        name="userrole",
        create_type=True,
    )
    userrole.create(bind, checkfirst=True)

    op.add_column("users", sa.Column("role_old", userrole, nullable=True))
    op.add_column("user_invites", sa.Column("role_old", userrole, nullable=True))

    op.execute(
        """
        UPDATE users SET role_old = CASE role
            WHEN 'owner' THEN 'ADMIN'::userrole
            WHEN 'analyst' THEN 'USER'::userrole
            WHEN 'viewer' THEN 'READONLY'::userrole
            ELSE 'USER'::userrole
        END
        """
    )
    op.execute(
        """
        UPDATE user_invites SET role_old = CASE role
            WHEN 'owner' THEN 'ADMIN'::userrole
            WHEN 'analyst' THEN 'ANALYST'::userrole
            WHEN 'viewer' THEN 'READONLY'::userrole
            ELSE 'READONLY'::userrole
        END
        """
    )

    op.drop_column("users", "role")
    op.drop_column("user_invites", "role")
    op.execute("ALTER TABLE users RENAME COLUMN role_old TO role")
    op.execute("ALTER TABLE user_invites RENAME COLUMN role_old TO role")
    op.alter_column(
        "users",
        "role",
        existing_type=userrole,
        nullable=False,
        server_default=sa.text("'USER'"),
    )
    op.alter_column(
        "user_invites",
        "role",
        existing_type=userrole,
        nullable=False,
        server_default=sa.text("'READONLY'"),
    )
