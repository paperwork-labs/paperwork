"""Add encrypted BYOK user key column.

Revision ID: 0058
Revises: 0057
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fernet ciphertext of a 2048-char plaintext exceeds 2048 chars (Fernet
    # overhead is ~1.33x + 57 bytes), so we use Text to avoid silent
    # truncation of valid BYOK keys.
    op.add_column(
        "users",
        sa.Column("llm_provider_key_encrypted", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "llm_provider_key_encrypted")
