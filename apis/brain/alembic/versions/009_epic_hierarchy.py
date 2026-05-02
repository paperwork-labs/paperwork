"""Goal/Epic/Sprint/Task hierarchy tables for project management.

Replaces flat workstreams.json with proper relational schema.
Brain becomes canonical source of truth for project management state.

Revision ID: 008
Revises: 007
"""

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS goals (
      id TEXT PRIMARY KEY,
      objective TEXT NOT NULL,
      horizon TEXT NOT NULL,
      metric TEXT NOT NULL,
      target TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      owner_employee_slug TEXT,
      written_at TIMESTAMPTZ NOT NULL,
      review_cadence_days INTEGER,
      notes TEXT,
      metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """
    )

    op.execute(
        """
    CREATE TABLE IF NOT EXISTS epics (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      goal_id TEXT REFERENCES goals(id),
      owner_employee_slug TEXT NOT NULL,
      status TEXT NOT NULL,
      priority INTEGER NOT NULL,
      percent_done INTEGER NOT NULL DEFAULT 0,
      brief_tag TEXT NOT NULL,
      description TEXT,
      related_plan TEXT,
      blockers JSONB NOT NULL DEFAULT '[]'::jsonb,
      last_activity TIMESTAMPTZ,
      last_dispatched_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      metadata JSONB NOT NULL DEFAULT '{}'::jsonb
    );
    """
    )

    op.execute(
        """
    CREATE TABLE IF NOT EXISTS sprints (
      id TEXT PRIMARY KEY,
      epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      goal TEXT,
      status TEXT NOT NULL,
      start_date DATE,
      end_date DATE,
      lead_employee_slug TEXT,
      ordinal INTEGER NOT NULL,
      metadata JSONB NOT NULL DEFAULT '{}'::jsonb
    );
    """
    )

    op.execute(
        """
    CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY,
      sprint_id TEXT REFERENCES sprints(id) ON DELETE SET NULL,
      epic_id TEXT REFERENCES epics(id),
      title TEXT NOT NULL,
      status TEXT NOT NULL,
      github_pr INTEGER,
      github_pr_url TEXT,
      owner_employee_slug TEXT,
      assignee TEXT,
      brief_tag TEXT,
      ordinal INTEGER,
      estimated_minutes INTEGER,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      merged_at TIMESTAMPTZ,
      metadata JSONB NOT NULL DEFAULT '{}'::jsonb
    );
    """
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_epics_goal ON epics(goal_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_epics_status ON epics(status, priority);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sprints_epic ON sprints(epic_id, ordinal);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_sprint ON tasks(sprint_id, ordinal);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_epic ON tasks(epic_id, status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_pr ON tasks(github_pr);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tasks CASCADE;")
    op.execute("DROP TABLE IF EXISTS sprints CASCADE;")
    op.execute("DROP TABLE IF EXISTS epics CASCADE;")
    op.execute("DROP TABLE IF EXISTS goals CASCADE;")
