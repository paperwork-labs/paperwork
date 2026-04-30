from pydantic import model_validator
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
    # J2/J3: Studio `/admin/brain-learning` + Brain `GET /api/v1/admin/brain/*` observability.
    # When false, those routes return 403 (scheduler unchanged).
    BRAIN_LEARNING_DASHBOARD_ENABLED: bool = True
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
    # Cheap-agent 1-day sprint planner (``brain_agent_sprint_planner`` job).
    BRAIN_OWNS_AGENT_SPRINT_SCHEDULER: bool = False
    BRAIN_AGENT_SPRINT_MAX_TASKS: int = 8
    BRAIN_AGENT_SPRINT_DAY_CAP_MINUTES: int = 480
    # When true, append a digest entry to ``apps/studio/src/data/tracker-index.json``
    # on each sprint (requires writable ``REPO_ROOT`` checkout).
    BRAIN_AGENT_SPRINT_WRITE_TRACKER: bool = False
    # --- Scheduler env split (Render / ``brain-api``, not all mirrored here) ---
    #
    # * **Former n8n crons** — daily/weekly briefings, weekly strategy, sprint
    #   kickoff/close, infra heartbeat/health, credential expiry, and P2.8-P2.10
    #   data jobs register whenever ``BRAIN_SCHEDULER_ENABLED`` is true (Track K
    #   cutover flags retired; see ``chore/brain-delete-legacy-owns-flags``).
    #
    # * **J1 ambient learning** — sprint auto-logger, merged-PR / decision /
    #   postmortem ingest cadences register whenever ``BRAIN_SCHEDULER_ENABLED``
    #   is true (``BRAIN_OWNS_SPRINT_AUTO_LOGGER`` and legacy ``BRAIN_OWNS_*``
    #   ingester keys retired; WS-18 / J1).
    #
    # * **Net-new / always on** — PR sweep, proactive cadence, CFO/QA
    #   jobs, etc. register whenever ``BRAIN_SCHEDULER_ENABLED`` is true.
    #
    # * **n8n (left behind on purpose)** — non-cron workflows only (webhooks,
    #   slash commands, error triggers). Cron-portable schedules were migrated
    #   to APScheduler; do not reintroduce parallel n8n crons for those.
    #
    # Track: sprint-lessons ingest cadence (hours). Bullets under
    # ``## What we learned`` in docs/sprints/*.md become memory episodes.
    # 6h is plenty — sprint markdown changes ship via PR, not continuously.
    SCHEDULER_SPRINT_LESSONS_HOURS: int = 6
    # Merged-PR memory episodes (``source=merged_pr``), GitHub API.
    SCHEDULER_MERGED_PRS_HOURS: int = 6
    BRAIN_PR_REVIEW_MODEL: str = ""
    # When true, Brain's PR sweep runs optional triage classifiers
    # (stale nudge, thin ready review, rebase assist). Default off; founders
    # enable when the workflow/ Actions split is ready.
    BRAIN_OWNS_PR_TRIAGE: bool = False
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
    RENDER_PIPELINE_MINUTES_INCLUDED: float = 500.0
    VERCEL_API_TOKEN: str = ""
    NEON_API_KEY: str = ""
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""
    # Vercel team id (optional; Vercel REST calls may require it for multi-team accounts).
    VERCEL_TEAM_ID: str = ""
    # Internal Bearer for Studio → Brain webhooks and `/internal/secrets/*` (set on both sides).
    BRAIN_INTERNAL_TOKEN: str = ""
    # JSON: app slug → Vercel project id or name, e.g. `{"studio":"prj_xxx"}`.
    BRAIN_SECRETS_VERCEL_APP_PROJECTS: str = ""
    # JSON: service label → Render service id, e.g. `{"brain-api":"srv-xxx"}`.
    BRAIN_SECRETS_RENDER_SERVICE_IDS: str = ""
    # JSON: service label → GET URL for `secrets_health_probe`, e.g. `{"studio":"https://.../api/health"}`.
    BRAIN_SECRETS_SERVICE_HEALTH_URLS: str = ""
    # Gmail SMTP fallback (WS-69 PR J) — required for high/critical conversation email delivery.
    # Generate an app password at Google Account → Security → 2-Step Verification → App passwords.
    GMAIL_USERNAME: str = ""
    GMAIL_APP_PASSWORD: str = ""
    FOUNDER_FALLBACK_EMAIL: str = ""

    # Net-new schedulers: default on (set false to disable without removing code).
    BRAIN_OWNS_SECRETS_DRIFT_AUDIT: bool = True
    BRAIN_OWNS_SECRETS_ROTATION_MONITOR: bool = True
    BRAIN_OWNS_SECRETS_HEALTH_PROBE: bool = True
    # Sprint planning (Mondays PT) — :func:`app.schedulers.sprint_planner.install` also
    # reads :envvar:`BRAIN_OWNS_SPRINT_PLANNER` from the process environment first.
    BRAIN_OWNS_SPRINT_PLANNER: bool = False

    # Cloudflare — account-wide write + optional per-zone DNS read (see cloudflare_client).
    # Account-wide fallback (legacy); prefer per-zone write tokens below.
    CLOUDFLARE_API_TOKEN: str = ""
    # Per-zone read-only tokens (issued by scripts/cloudflare_issue_readonly_tokens.py).
    CLOUDFLARE_READONLY_TOKEN_PAPERWORKLABS: str = ""
    CLOUDFLARE_READONLY_TOKEN_AXIOMFOLIO: str = ""
    CLOUDFLARE_READONLY_TOKEN_FILEFREE: str = ""
    CLOUDFLARE_READONLY_TOKEN_LAUNCHFREE: str = ""
    CLOUDFLARE_READONLY_TOKEN_DISTILL_TAX: str = ""
    # Per-zone write tokens (WS-47): Zone:Read + DNS:Edit + Cache Purge:Edit only.
    # Resolver in cloudflare_token_resolver.py reads these via os.environ directly
    # (extra="ignore" means pydantic-settings silently drops unknown keys, so we
    # declare each one explicitly here so IDE tooling + env-check can validate them).
    CLOUDFLARE_TOKEN_PAPERWORKLABS_COM: str = ""
    CLOUDFLARE_TOKEN_AXIOMFOLIO_COM: str = ""
    CLOUDFLARE_TOKEN_FILEFREE_AI: str = ""
    CLOUDFLARE_TOKEN_LAUNCHFREE_AI: str = ""
    CLOUDFLARE_TOKEN_DISTILL_TAX: str = ""

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
