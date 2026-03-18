"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=True),
        sa.Column("full_name_encrypted", sa.Text, nullable=True),
        sa.Column("referral_code", sa.String(20), unique=True, nullable=False),
        sa.Column(
            "referred_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "role",
            sa.Enum("user", "admin", name="user_role"),
            nullable=False,
            server_default="user",
        ),
        sa.Column(
            "advisor_tier",
            sa.Enum("free", "premium", name="advisor_tier"),
            nullable=False,
            server_default="free",
        ),
        sa.Column(
            "auth_provider",
            sa.Enum("local", "google", "apple", name="auth_provider"),
            nullable=False,
            server_default="local",
        ),
        sa.Column("auth_provider_id", sa.String(255), nullable=True),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("attribution", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "filings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tax_year", sa.Integer, nullable=False),
        sa.Column(
            "filing_status_type",
            sa.Enum(
                "single",
                "married_joint",
                "married_separate",
                "head_of_household",
                name="filing_status_type",
            ),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "documents_uploaded",
                "data_confirmed",
                "calculated",
                "review",
                "submitted",
                "accepted",
                "rejected",
                name="filing_status",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "filing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("filings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_type",
            sa.Enum("w2", "drivers_license", "1099_misc", "1099_nec", name="document_type"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.Text, nullable=True),
        sa.Column(
            "extraction_status",
            sa.Enum("pending", "processing", "completed", "failed", name="extraction_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("extraction_data", postgresql.JSONB, nullable=True),
        sa.Column("confidence_scores", postgresql.JSONB, nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "tax_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "filing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("filings.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("ssn_encrypted", sa.Text, nullable=True),
        sa.Column("full_name_encrypted", sa.Text, nullable=True),
        sa.Column("address_encrypted", postgresql.JSONB, nullable=True),
        sa.Column("date_of_birth_encrypted", sa.Text, nullable=True),
        sa.Column("total_wages", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_federal_withheld", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_state_withheld", sa.Integer, nullable=False, server_default="0"),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "tax_calculations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "filing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("filings.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("adjusted_gross_income", sa.Integer, nullable=False, server_default="0"),
        sa.Column("standard_deduction", sa.Integer, nullable=False, server_default="0"),
        sa.Column("taxable_income", sa.Integer, nullable=False, server_default="0"),
        sa.Column("federal_tax", sa.Integer, nullable=False, server_default="0"),
        sa.Column("state_tax", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_withheld", sa.Integer, nullable=False, server_default="0"),
        sa.Column("refund_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("owed_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_insights", postgresql.JSONB, nullable=True),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "filing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("filings.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("transmitter_partner", sa.String(50), nullable=False),
        sa.Column("submission_id_external", sa.String(255), nullable=True),
        sa.Column(
            "irs_status",
            sa.Enum("submitted", "accepted", "rejected", name="irs_status"),
            nullable=False,
            server_default="submitted",
        ),
        sa.Column("rejection_codes", postgresql.JSONB, nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "waitlist",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="landing"),
        sa.Column("attribution", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("waitlist")
    op.drop_table("submissions")
    op.drop_table("tax_calculations")
    op.drop_table("tax_profiles")
    op.drop_table("documents")
    op.drop_table("filings")
    op.drop_table("users")
    sa.Enum(name="user_role").drop(op.get_bind())
    sa.Enum(name="advisor_tier").drop(op.get_bind())
    sa.Enum(name="auth_provider").drop(op.get_bind())
    sa.Enum(name="filing_status_type").drop(op.get_bind())
    sa.Enum(name="filing_status").drop(op.get_bind())
    sa.Enum(name="document_type").drop(op.get_bind())
    sa.Enum(name="extraction_status").drop(op.get_bind())
    sa.Enum(name="irs_status").drop(op.get_bind())
