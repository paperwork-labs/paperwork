from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://brain:brain_dev@localhost:5432/brain_dev"

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        """Neon provides postgresql:// URLs; asyncpg needs the +asyncpg driver."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)

        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params.pop("channel_binding", None)
        if "sslmode" in params:
            params["ssl"] = params.pop("sslmode")
        clean_query = urlencode(params, doseq=True)
        url = urlunparse(parsed._replace(query=clean_query))

        object.__setattr__(self, "DATABASE_URL", url)
        return self

    REDIS_URL: str = "redis://localhost:6379/1"
    SECRET_KEY: str = "change-me-to-a-random-64-char-string"
    ENCRYPTION_KEY: str = "change-me-generate-with-fernet"

    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = "paperwork-labs/paperwork"
    SECRETS_API_KEY: str = ""
    BRAIN_API_SECRET: str = ""
    BRAIN_MCP_TOKEN: str = ""
    STUDIO_URL: str = "https://paperworklabs.com"
    BRAIN_URL: str = "https://brain.paperworklabs.com"
    AXIOMFOLIO_API_URL: str = "http://localhost:8100"
    AXIOMFOLIO_API_KEY: str = ""
    AXIOMFOLIO_WEBHOOK_SECRET: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    # Track B: Brain-owned PR automation. When true (default in prod),
    # register the in-process APScheduler job that sweeps open PRs every
    # SCHEDULER_PR_SWEEP_MINUTES minutes. Set to False to disable during
    # migration windows or when running multi-instance.
    BRAIN_SCHEDULER_ENABLED: bool = True
    SCHEDULER_PR_SWEEP_MINUTES: int = 30
    # Track: sprint-lessons ingest cadence (hours). Bullets under
    # ``## What we learned`` in docs/sprints/*.md become memory episodes.
    # 6h is plenty — sprint markdown changes ship via PR, not continuously.
    SCHEDULER_SPRINT_LESSONS_HOURS: int = 6
    # Merged-PR memory episodes (``source=merged_pr``), GitHub API.
    SCHEDULER_MERGED_PRS_HOURS: int = 6
    # T2.2: when true, register shadow APScheduler jobs mirroring n8n crons
    # (#engineering-cron-shadow only) — default off until cutover ready.
    SCHEDULER_N8N_MIRROR_ENABLED: bool = False
    # #engineering Slack channel ID for per-PR Brain review summaries.
    SLACK_ENGINEERING_CHANNEL_ID: str = ""
    # Track I: #cfo Slack channel ID for the daily cost dashboard.
    # Falls back to #engineering if unset so the dashboard isn't silent.
    SLACK_CFO_CHANNEL_ID: str = ""
    # Track G: #qa Slack channel ID for the weekly agent-health digest
    # and nightly golden-suite summary. Falls back to #engineering.
    SLACK_QA_CHANNEL_ID: str = ""
    # Track M.2: #trading Slack channel ID. Where the trading persona
    # wakes up for risk-gate, approval-required, and stop-triggered
    # events received via AxiomFolio webhooks. Falls back to #engineering
    # so we don't swallow events silently.
    SLACK_TRADING_CHANNEL_ID: str = ""
    SLACK_BOT_TOKEN: str = ""
    # Track C: Slack signing secret used to verify slash-command payloads
    # (/persona, etc). Leave empty in dev to skip verification.
    SLACK_SIGNING_SECRET: str = ""
    BRAIN_PR_REVIEW_MODEL: str = ""
    MAX_ITERATIONS: int = 5
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://langfuse.paperworklabs.com"

    FRONTEND_URL: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    APP_VERSION: str = "0.1.0"

    # Infra health tools (optional; empty = tool reports not configured)
    RENDER_API_KEY: str = ""
    VERCEL_TOKEN: str = Field(
        default="",
        validation_alias=AliasChoices("VERCEL_TOKEN", "VERCEL_API_TOKEN"),
    )
    NEON_API_KEY: str = ""
    N8N_URL: str = "https://n8n.paperworklabs.com"
    N8N_API_KEY: str = ""
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def check_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT != "development":
            if self.SECRET_KEY == "change-me-to-a-random-64-char-string":
                raise ValueError("SECRET_KEY must be changed from default in production")
            if self.ENCRYPTION_KEY == "change-me-generate-with-fernet":
                raise ValueError("ENCRYPTION_KEY must be changed from default in production")
        return self


settings = Settings()
