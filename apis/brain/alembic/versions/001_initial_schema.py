"""Initial Brain schema — all tables from BRAIN_ARCHITECTURE.md + FTS support.

Revision ID: 001
Create Date: 2026-03-23
"""

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_organizations (
        id SERIAL PRIMARY KEY,
        organization_id TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        plan TEXT DEFAULT 'free',
        parent_organization_id TEXT,
        settings JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_teams (
        id SERIAL PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES agent_organizations(organization_id),
        name TEXT NOT NULL,
        settings JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_user_profiles (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        organization_id TEXT NOT NULL REFERENCES agent_organizations(organization_id),
        team_id INTEGER REFERENCES agent_teams(id),
        display_name TEXT,
        role TEXT DEFAULT 'member',
        timezone TEXT DEFAULT 'America/Los_Angeles',
        preferences JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (user_id, organization_id)
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_episodes (
        id SERIAL PRIMARY KEY,
        organization_id TEXT NOT NULL,
        team_id INTEGER,
        circle_id INTEGER,
        user_id TEXT,
        visibility TEXT DEFAULT 'organization',
        verified BOOLEAN DEFAULT false,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        source TEXT NOT NULL,
        source_ref TEXT,
        channel TEXT,
        persona TEXT,
        persona_tier TEXT,
        product TEXT,
        summary TEXT NOT NULL,
        full_context TEXT,
        embedding vector(1536),
        embedding_model TEXT DEFAULT 'text-embedding-3-small',
        importance FLOAT DEFAULT 0.5,
        freshness FLOAT DEFAULT 1.0,
        quality_signal SMALLINT,
        model_used TEXT,
        tokens_in INTEGER,
        tokens_out INTEGER,
        confidence FLOAT,
        visual_context_url TEXT,
        metadata JSONB DEFAULT '{}'::jsonb,
        search_vector tsvector GENERATED ALWAYS AS (
            to_tsvector('english', coalesce(summary, '') || ' ' || coalesce(full_context, ''))
        ) STORED
    )
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_episodes_search_vector
    ON agent_episodes USING GIN (search_vector)
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_episodes_org_created
    ON agent_episodes (organization_id, created_at DESC)
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_episodes_embedding
    ON agent_episodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_entities (
        id SERIAL PRIMARY KEY,
        organization_id TEXT NOT NULL,
        name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        properties JSONB DEFAULT '{}'::jsonb,
        first_seen TIMESTAMPTZ DEFAULT NOW(),
        last_seen TIMESTAMPTZ DEFAULT NOW(),
        mention_count INTEGER DEFAULT 1,
        UNIQUE (organization_id, name, entity_type)
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_summaries (
        id SERIAL PRIMARY KEY,
        organization_id TEXT NOT NULL,
        summary_type TEXT NOT NULL,
        period_start TIMESTAMPTZ,
        period_end TIMESTAMPTZ,
        content TEXT NOT NULL,
        key_decisions JSONB DEFAULT '[]'::jsonb,
        key_entities JSONB DEFAULT '[]'::jsonb,
        episode_count INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_cost_tracking (
        id SERIAL PRIMARY KEY,
        organization_id TEXT NOT NULL,
        episode_id INTEGER,
        model TEXT NOT NULL,
        provider TEXT NOT NULL,
        tokens_in INTEGER DEFAULT 0,
        tokens_out INTEGER DEFAULT 0,
        cost_usd FLOAT DEFAULT 0.0,
        latency_ms INTEGER,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_audit_log (
        id SERIAL PRIMARY KEY,
        organization_id TEXT NOT NULL,
        user_id TEXT,
        action TEXT NOT NULL,
        resource_type TEXT,
        resource_id TEXT,
        details JSONB DEFAULT '{}'::jsonb,
        ip_address TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_api_keys (
        id SERIAL PRIMARY KEY,
        organization_id TEXT NOT NULL,
        key_hash TEXT NOT NULL UNIQUE,
        name TEXT DEFAULT 'Brain',
        scopes JSONB DEFAULT '[]'::jsonb,
        is_active BOOLEAN DEFAULT true,
        last_used_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_connections (
        id SERIAL PRIMARY KEY,
        organization_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        scopes JSONB DEFAULT '[]'::jsonb,
        credentials_encrypted TEXT,
        iv TEXT,
        auth_tag TEXT,
        last_sync_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (organization_id, user_id, provider)
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS brain_user_vault (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        organization_id TEXT NOT NULL,
        name TEXT NOT NULL,
        encrypted_value TEXT NOT NULL,
        iv TEXT NOT NULL,
        auth_tag TEXT NOT NULL,
        service TEXT,
        description TEXT,
        expires_at TIMESTAMPTZ,
        last_rotated_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (user_id, organization_id, name)
    )
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_brain_user_vault_user_org
    ON brain_user_vault (user_id, organization_id)
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS brain_skills (
        id SERIAL PRIMARY KEY,
        skill_id TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT,
        tier TEXT DEFAULT 'free',
        connector_id TEXT,
        tools JSONB DEFAULT '[]'::jsonb,
        knowledge_domains JSONB DEFAULT '[]'::jsonb,
        requires_connection BOOLEAN DEFAULT false,
        owner_organization_id TEXT DEFAULT 'platform',
        status TEXT DEFAULT 'active',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS brain_user_skills (
        user_id TEXT NOT NULL,
        organization_id TEXT NOT NULL,
        skill_id TEXT NOT NULL REFERENCES brain_skills(skill_id),
        enabled_at TIMESTAMPTZ DEFAULT NOW(),
        config JSONB DEFAULT '{}'::jsonb,
        PRIMARY KEY (user_id, organization_id, skill_id)
    )
    """)

    # Seed data: platform org + paperwork-labs org
    op.execute("""
    INSERT INTO agent_organizations (organization_id, name, plan, parent_organization_id)
    VALUES
        ('platform', 'Platform Brain', 'enterprise', NULL),
        ('paperwork-labs', 'Paperwork Labs', 'team', 'platform')
    ON CONFLICT (organization_id) DO NOTHING
    """)

    # Seed data: initial skills (D62)
    op.execute("""
    INSERT INTO brain_skills (skill_id, name, tier, category, connector_id, requires_connection)
    VALUES
        ('tax-filing', 'Tax Filing', 'free', 'financial', NULL, false),
        ('llc-formation', 'LLC Formation', 'free', 'financial', NULL, false),
        ('financial-calculators', 'Financial Calculators', 'free', 'financial', NULL, false),
        ('email-metadata', 'Email Intelligence', 'free', 'financial', 'google-workspace', true),
        ('email-full', 'Deep Email Analysis', 'personal', 'financial', 'google-workspace', true),
        ('calendar-insights', 'Calendar Insights', 'free', 'lifestyle', 'google-workspace', true),
        ('location-history', 'Location Intelligence', 'personal', 'lifestyle', 'google-maps', true),
        ('bank-transactions', 'Bank Transactions', 'personal', 'financial', 'plaid', true),
        ('browser-context', 'Shopping & Browsing', 'personal', 'shopping', 'chrome-extension', true),
        ('couple-brain', 'Shared Circle', 'personal', 'lifestyle', NULL, false)
    ON CONFLICT (skill_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS brain_user_skills CASCADE")
    op.execute("DROP TABLE IF EXISTS brain_skills CASCADE")
    op.execute("DROP TABLE IF EXISTS brain_user_vault CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_connections CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_api_keys CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_audit_log CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_cost_tracking CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_summaries CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_entities CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_episodes CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_user_profiles CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_teams CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_organizations CASCADE")
