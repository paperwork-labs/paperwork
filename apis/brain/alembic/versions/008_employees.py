"""Unified employees table — canonical source of truth for all personas.

Revision ID: 008
Revises: 007
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS employees (
      slug                  TEXT PRIMARY KEY,
      kind                  TEXT NOT NULL,
      role_title            TEXT NOT NULL,
      team                  TEXT NOT NULL,

      -- Personality (set during naming ceremony)
      display_name          TEXT,
      tagline               TEXT,
      avatar_emoji          TEXT,
      voice_signature       TEXT,
      named_at              TIMESTAMPTZ,
      named_by_self         BOOLEAN NOT NULL DEFAULT true,

      -- Org graph
      reports_to            TEXT,
      manages               JSONB NOT NULL DEFAULT '[]'::jsonb,

      -- Brain runtime config
      description           TEXT NOT NULL,
      default_model         TEXT NOT NULL,
      escalation_model      TEXT,
      escalate_if           JSONB NOT NULL DEFAULT '[]'::jsonb,
      requires_tools        BOOLEAN NOT NULL DEFAULT false,
      daily_cost_ceiling_usd NUMERIC(10, 2),
      owner_channel         TEXT,
      mode                  TEXT,
      tone_prefix           TEXT,
      proactive_cadence     TEXT,
      max_output_tokens     INTEGER,
      requests_per_minute   INTEGER,

      -- Cursor IDE config
      cursor_description    TEXT,
      cursor_globs          JSONB NOT NULL DEFAULT '[]'::jsonb,
      cursor_always_apply   BOOLEAN NOT NULL DEFAULT false,

      -- Ownership
      owned_rules           JSONB NOT NULL DEFAULT '[]'::jsonb,
      owned_runbooks        JSONB NOT NULL DEFAULT '[]'::jsonb,
      owned_workflows       JSONB NOT NULL DEFAULT '[]'::jsonb,
      owned_skills          JSONB NOT NULL DEFAULT '[]'::jsonb,

      -- Body markdown for .mdc generation
      body_markdown         TEXT,

      created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
      metadata              JSONB NOT NULL DEFAULT '{}'::jsonb
    );
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS employees_kind_idx ON employees (kind);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS employees_team_idx ON employees (team);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS employees_named_at_idx ON employees (named_at) WHERE named_at IS NOT NULL;"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS employees CASCADE;")
