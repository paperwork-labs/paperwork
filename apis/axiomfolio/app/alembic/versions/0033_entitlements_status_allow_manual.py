"""Allow ``manual`` value in ``entitlements.status`` CHECK constraint.

The original 0031 migration tightened ``entitlements.status`` with a
CHECK constraint mirroring Stripe's subscription status values
(``active``, ``trialing``, ``past_due``, ``canceled``, ``incomplete``)
but omitted ``manual``, which the model already supports
(``EntitlementStatus.MANUAL``) for internal grants such as the founding
hedge-fund partner, validator pseudonym holders, and employee comp
accounts.

The omission was caught by the entitlements service test suite once
0031 hit main, so this hotfix migration drops and re-creates the
constraint with the full enum, in line with the deliberate trade-off
documented in 0031: "adding a value requires a follow-up migration that
rewrites the CHECK".

Revision ID: 0033
Revises: 0031
Create Date: 2026-04-18
"""

from alembic import op


revision = "0033"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_entitlements_status", "entitlements", type_="check"
    )
    op.create_check_constraint(
        "ck_entitlements_status",
        "entitlements",
        "status IN ('active','trialing','past_due','canceled','incomplete','manual')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_entitlements_status", "entitlements", type_="check"
    )
    op.create_check_constraint(
        "ck_entitlements_status",
        "entitlements",
        "status IN ('active','trialing','past_due','canceled','incomplete')",
    )
