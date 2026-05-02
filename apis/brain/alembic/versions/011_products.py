"""Products table — Studio registry backed by Brain (WS-82).

Revision ID: 011
Revises: 010
"""

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS products (
      id VARCHAR(100) PRIMARY KEY,
      name VARCHAR(200) NOT NULL,
      tagline TEXT,
      status VARCHAR(50) NOT NULL DEFAULT 'active',
      domain VARCHAR(200),
      repo_path VARCHAR(200),
      vercel_project VARCHAR(200),
      render_services JSONB NOT NULL DEFAULT '[]'::jsonb,
      tech_stack JSONB NOT NULL DEFAULT '[]'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      metadata JSONB NOT NULL DEFAULT '{}'::jsonb
    );
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS products_status_idx ON products (status);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS products;")
