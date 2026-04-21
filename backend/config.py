import logging
import os
from dataclasses import dataclass
from typing import Any, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


@dataclass(frozen=True)
class ProviderPolicy:
    """Tier-specific configuration for external data providers.

    All budget/rate/concurrency values derive from the selected tier.
    Change tier by setting MARKET_PROVIDER_POLICY env var (free/starter/paid/unlimited).
    """
    fmp_daily_budget: int
    fmp_cpm: int
    twelvedata_daily_budget: int
    twelvedata_cpm: int
    yfinance_daily_budget: int
    yfinance_cpm: int
    backfill_concurrency: int
    deep_backfill_allowed: bool
    full_historical_cron: bool
    auto_ops_backfill: bool


PROVIDER_POLICIES: dict[str, ProviderPolicy] = {
    "free":      ProviderPolicy(200,    250,  100, 7,  5000,  30,   5, False, False, False),
    "starter":   ProviderPolicy(3000,   280,  800, 7, 10000,  30,  25, False, False, False),
    "paid":      ProviderPolicy(100000, 700,  800, 7, 10000,  30,  50, False, False, False),
    "unlimited": ProviderPolicy(999999, 2800, 800, 7, 10000,  30, 100, True,  True,  True),
}

logger = logging.getLogger(__name__)
# Dedupe unrecognized MARKET_PROVIDER_POLICY warnings (property may be read often).
_unrecognized_market_provider_policy_logged: set[str] = set()


class Settings(BaseSettings):
    # Application Configuration
    APP_NAME: str = "AxiomFolio Trading Platform"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | staging | production

    # Database Configuration - using SQLite for development
    DATABASE_URL: str = "sqlite:///./axiomfolio.db"

    # Redis Configuration (Docker defaults; override via env in non-Docker)
    REDIS_URL: str = "redis://:redispassword@redis:6379/0"
    CELERY_BROKER_URL: str = "redis://:redispassword@redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://:redispassword@redis:6379/0"
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3500
    CELERY_TASK_TIME_LIMIT: int = 3600

    # API Keys
    ALPHA_VANTAGE_API_KEY: Optional[str] = None
    FINNHUB_API_KEY: Optional[str] = None
    TWELVE_DATA_API_KEY: Optional[str] = None
    FMP_API_KEY: Optional[str] = None
    
    # LLM / Agent API Keys
    OPENAI_API_KEY: Optional[str] = None
    # Service-to-service key for Brain tool HTTP routes (header X-Brain-Api-Key)
    BRAIN_API_KEY: Optional[str] = None
    # DEPRECATED. Used as a last-resort fallback ONLY when no
    # X-Axiom-User-Id header was supplied AND the caller authenticated
    # with the global Brain API key. New M2M callers MUST set
    # ``X-Axiom-User-Id`` so we can scope downstream calls to the
    # correct tenant. See backend/api/middleware/rate_limit.py.
    BRAIN_TOOLS_USER_ID: int = 1
    # GDPR / data-subject-rights configuration
    GDPR_EXPORT_LOCAL_DIR: str = "/tmp/axiomfolio-gdpr-exports"
    GDPR_EXPORT_TTL_DAYS: int = 7
    GDPR_DELETE_CONFIRM_TTL_HOURS: int = 24
    S3_GDPR_BUCKET: Optional[str] = None
    S3_GDPR_REGION: Optional[str] = None
    S3_GDPR_ENDPOINT_URL: Optional[str] = None
    S3_GDPR_ACCESS_KEY_ID: Optional[str] = None
    S3_GDPR_SECRET_ACCESS_KEY: Optional[str] = None
    # Per-tenant rate limit middleware kill switch (default ON in prod).
    TENANT_RATE_LIMIT_ENABLED: bool = True
    BRAIN_WEBHOOK_URL: Optional[str] = None
    BRAIN_WEBHOOK_SECRET: Optional[str] = None
    # Agent autonomy level: "full" (auto-execute all), "safe" (auto-execute safe only), "ask" (always ask)
    AGENT_AUTONOMY_LEVEL: str = "safe"

    # TastyTrade Configuration (OAuth — v12+ SDK)
    # Dev fallback only; production credentials stored per-user in account_credentials table
    TASTYTRADE_CLIENT_SECRET: Optional[str] = None
    TASTYTRADE_REFRESH_TOKEN: Optional[str] = None
    TASTYTRADE_IS_TEST: bool = False
    # Legacy credentials (ignored by SDK v12+; kept for backward-compat env files)
    TASTYTRADE_USERNAME: Optional[str] = None
    TASTYTRADE_PASSWORD: Optional[str] = None

    # IBKR Configuration
    IBKR_HOST: str = "127.0.0.1"
    IBKR_PORT: int = 7497
    IBKR_CLIENT_ID: int = 1
    IBKR_TRADING_MODE: str = "paper"  # paper | live
    IBKR_ACCOUNTS: Optional[str] = None  # Comma separated account numbers
    IBKR_DISCOVER_ON_SEED: bool = False
    IBKR_FLEX_TOKEN: Optional[str] = None
    IBKR_FLEX_QUERY_ID: Optional[str] = None
    IBKR_FLEX_LOOKBACK_YEARS: int = (
        10  # Intended history window; configure FlexQuery accordingly
    )
    # IBKR Gateway TOTP (for automated 2FA login via IBC)
    IBKR_TOTP_SECRET: Optional[str] = None  # Base32 TOTP secret from IBKR Authenticator setup
    IBKR_USERNAME: Optional[str] = None  # Gateway login username
    IBKR_PASSWORD: Optional[str] = None  # Gateway login password (use secrets manager in prod)

    # E*TRADE OAuth 1.0a (sandbox-first; live keys require formal app approval)
    # Used by backend.services.oauth.etrade.ETradeSandboxAdapter. The sandbox
    # base URL is fixed; only the consumer key/secret + callback URL vary.
    ETRADE_SANDBOX_KEY: Optional[str] = None
    ETRADE_SANDBOX_SECRET: Optional[str] = None
    # Registered OAuth redirect URI at the provider (must match request_token).
    # When set, /oauth/{etrade}/initiate rejects callback_url values that differ.
    ETRADE_OAUTH_CALLBACK_URL: Optional[str] = None
    # Comma-separated absolute callback URLs allowed for /oauth/*/initiate.
    # When non-empty, client callback_url must match one entry exactly.
    OAUTH_ALLOWED_CALLBACK_URLS: Optional[str] = None
    ETRADE_OAUTH_REQUEST_TIMEOUT_S: float = 15.0

    # Schwab (optional) - comma-separated account numbers for seeding
    SCHWAB_ACCOUNTS: Optional[str] = None
    SCHWAB_CLIENT_ID: Optional[str] = None
    SCHWAB_CLIENT_SECRET: Optional[str] = None
    SCHWAB_REDIRECT_URI: Optional[str] = None
    SCHWAB_AUTH_BASE: Optional[str] = None
    SCHWAB_CLIENT_ID_SUFFIX: Optional[str] = None

    # Legacy Discord env vars (unused by app code; notifications use BRAIN_WEBHOOK_URL).
    DISCORD_WEBHOOK_SIGNALS: Optional[str] = None
    DISCORD_WEBHOOK_PORTFOLIO_DIGEST: Optional[str] = None
    DISCORD_WEBHOOK_MORNING_BREW: Optional[str] = None
    DISCORD_WEBHOOK_PLAYGROUND: Optional[str] = None
    DISCORD_WEBHOOK_SYSTEM_STATUS: Optional[str] = None
    DISCORD_BOT_TOKEN: Optional[str] = None
    DISCORD_BOT_DEFAULT_CHANNEL_ID: Optional[str] = None

    # Security Configuration
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    OAUTH_STATE_SECRET: Optional[str] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: Optional[str] = None
    # OAuth broker token encryption (separate key + retired keys for rotation).
    # Falls back to ENCRYPTION_KEY / SECRET_KEY at the encryption-service layer
    # so dev environments work out-of-the-box; production should set this
    # explicitly so OAuth credential rotation is independent of the app key.
    OAUTH_TOKEN_ENCRYPTION_KEY: Optional[str] = None
    OAUTH_TOKEN_ENCRYPTION_KEYS_RETIRED: Optional[str] = None  # comma-separated
    ENABLE_TRADING: bool = False
    ALLOW_LIVE_ORDERS: bool = False
    ENABLE_AUTO_TRADING: bool = False
    SEED_ACCOUNTS_ON_STARTUP: bool = False
    AUTO_MIGRATE_ON_STARTUP: bool = False
    AUTO_WARM_ON_STARTUP: bool = False
    AUTO_WARM_STALE_MINUTES: int = 120

    # Pipeline DAG orchestrator (replaces monolithic daily_bootstrap)
    PIPELINE_DAG_ENABLED: bool = True

    # Risk management
    MAX_SINGLE_POSITION_PCT: float = 0.15
    ENABLE_ACCOUNT_AWARE_RISK: bool = False

    # Trade approval settings (Tier 3 / human-in-the-loop)
    TRADE_APPROVAL_MODE: str = "all"  # all | threshold | analyst_only | none
    TRADE_APPROVAL_THRESHOLD: float = 5000.0  # USD value threshold

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

    # Apple Sign-In
    APPLE_CLIENT_ID: Optional[str] = None
    APPLE_TEAM_ID: Optional[str] = None
    APPLE_KEY_ID: Optional[str] = None
    APPLE_PRIVATE_KEY: Optional[str] = None
    APPLE_REDIRECT_URI: Optional[str] = None

    # Email verification (Resend)
    RESEND_API_KEY: Optional[str] = None

    # Stripe billing (test-mode keys in dev/staging, live in prod).
    # All keys are optional; the webhook returns HTTP 402 if unconfigured.
    STRIPE_API_KEY: Optional[str] = None
    STRIPE_API_VERSION: Optional[str] = None  # e.g. "2024-06-20"
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None  # safe to ship to frontend
    # Price ID -> tier mapping (one env var per tier+interval).
    # See backend/services/billing/price_catalog.py for the full list.
    STRIPE_PRICE_PRO_MONTHLY: Optional[str] = None
    STRIPE_PRICE_PRO_ANNUAL: Optional[str] = None
    STRIPE_PRICE_PRO_PLUS_MONTHLY: Optional[str] = None
    STRIPE_PRICE_PRO_PLUS_ANNUAL: Optional[str] = None
    STRIPE_PRICE_QUANT_DESK_MONTHLY: Optional[str] = None
    STRIPE_PRICE_QUANT_DESK_ANNUAL: Optional[str] = None
    STRIPE_PRICE_ENTERPRISE_MONTHLY: Optional[str] = None
    STRIPE_PRICE_ENTERPRISE_ANNUAL: Optional[str] = None

    # Postmark inbound (picks newsletter forwarding)
    POSTMARK_INBOUND_SECRET: Optional[str] = None
    PICKS_INBOUND_ALLOWLIST: List[str] = Field(default_factory=list)
    PICKS_INBOUND_REQUIRE_SIGNATURE: bool = True

    # Frontend origin for OAuth redirects (falls back to first CORS_ORIGINS entry)
    FRONTEND_ORIGIN: Optional[str] = None

    # API / CORS / rate limiting
    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://0.0.0.0:3000,"
        "https://axiomfolio.com,"
        "https://staging.axiomfolio.com"
    )
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_STORAGE_URL: Optional[str] = None

    # Deprecated toggles (no longer functional). Kept for backward-compat only.
    # DB + Render API sync is now the schedule source-of-truth.
    ENABLE_CELERY_BEAT: bool = False
    ENABLE_REDBEAT: bool = False

    # Render API (schedule sync — production only)
    RENDER_API_KEY: Optional[str] = None
    RENDER_OWNER_ID: Optional[str] = None
    RENDER_SYNC_ON_STARTUP: bool = False
    RENDER_REPO_URL: str = "https://github.com/sankalp404/axiomfolio.git"

    # Deploy-health guardrail (G28, D120). Comma-separated Render service ids
    # polled every 5 minutes by :mod:`backend.tasks.deploys.poll_deploy_health`.
    # Leave empty in dev / CI — the poll task is a no-op when unset.
    # Prod default monitors the web service + both workers + the static site:
    #   srv-d64mkqi4d50c73eite20  -> axiomfolio-api
    #   srv-d64mkqi4d50c73eite10  -> axiomfolio-worker
    #   srv-d7hpo2v7f7vs738o9p80  -> axiomfolio-worker-heavy
    #   srv-d64mkhi4d50c73eit7ng  -> axiomfolio-frontend
    DEPLOY_HEALTH_SERVICE_IDS: str = ""

    # Admin seeding (development convenience)
    ADMIN_USERNAME: Optional[str] = None
    ADMIN_EMAIL: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None
    ADMIN_SEED_ENABLED: bool = False

    # Application Settings
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Scanner Configuration
    MAX_SCANNER_TICKERS: int = 508  # Maximum tickers to scan in ATR Matrix

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json | text

    # Market data bootstrap
    DEFAULT_PRICE_SYMBOLS: Optional[str] = (
        None  # Comma-separated list to prefetch on startup
    )

    # Market data provider policy and caching
    # Values: "paid" (prefer paid providers like FMP), "free" (prefer free/fallbacks)
    MARKET_PROVIDER_POLICY: str = "paid"
    # Default cache TTL for market-data service (seconds)
    MARKET_DATA_CACHE_TTL: int = 300
    # Daily backfill throughput controls (safe defaults; override via env in infra/env.dev)
    # Max concurrency cap; effective concurrency comes from ProviderPolicy.backfill_concurrency.
    MARKET_BACKFILL_CONCURRENCY_MAX: int = 100
    # Provider retry/backoff (applies to transient provider failures like 429/5xx)
    MARKET_BACKFILL_RETRY_ATTEMPTS: int = 6
    MARKET_BACKFILL_RETRY_MAX_DELAY_SECONDS: float = 60.0
    # Deprecated for runtime release gating.
    # Keep as a bootstrap env flag only for legacy deployments; DB app_settings are
    # the authoritative source for portfolio/strategy rollout decisions.
    MARKET_DATA_SECTION_PUBLIC: bool = False
    # Coverage UI sampling only (must NOT affect correctness/backfills).
    # Number of stale symbols to include in API/UI sample lists (full counts are computed separately).
    COVERAGE_STALE_SAMPLE: int = 200
    # Coverage fill-by-date lookback (calendar days). Used for daily.fill_by_date and snapshot_fill_by_date series.
    COVERAGE_FILL_LOOKBACK_DAYS: int = 90
    # How many *trading days* to render in the UI histogram (frontend reads this from /market-data/coverage meta).
    COVERAGE_FILL_TRADING_DAYS_WINDOW: int = 50

    ALLOW_DEEP_BACKFILL: bool = False

    # Retention defaults for intraday data
    RETENTION_MAX_DAYS_5M: int = 90
    # Alert when retention deletes exceed this count in a run.
    RETENTION_DELETE_WARN_THRESHOLD: int = 250000

    # Snapshot computation window (daily bars). Needs to be large enough for:
    # - 200D SMA
    # - ~52-week RS computations on weekly resample
    SNAPSHOT_DAILY_BARS_LIMIT: int = 400

    # Deep backfill target (years). One-time operation; nightly pipeline is delta-only.
    HISTORY_TARGET_YEARS: int = 10

    # Maximum trading days for snapshot-history rebuild in safe_recompute.
    # SPY has ~8,400 trading days since 1993; 10,000 gives headroom for growth.
    RECOMPUTE_HISTORY_MAX_DAYS: int = 10000

    # Weinstein Stage thresholds (percent units)
    # - slope thresholds are % change of 30W SMA vs 5 weeks ago
    # - distance thresholds are % from 30W SMA
    STAGE_SLOPE_PCT_UP: float = 0.05
    STAGE_SLOPE_PCT_DOWN: float = -0.05
    STAGE_SLOPE_PCT_FLAT: float = 0.05
    STAGE_DIST_PCT_FLAT: float = 5.0
    STAGE_DIST_PCT_STAGE2_A: float = 5.0
    STAGE_DIST_PCT_STAGE2_B: float = 15.0

    # Source of truth should be runtime environment variables injected by Docker Compose
    # (`infra/env.dev` via Makefile). We keep optional env-file support only when explicitly
    # provided for non-Docker workflows (do not implicitly load a repo root `.env`).
    @field_validator("PICKS_INBOUND_ALLOWLIST", mode="before")
    @classmethod
    def _parse_picks_inbound_allowlist(cls, v: Any) -> List[str]:
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return [str(x).strip().lower() for x in v if str(x).strip()]
        s = str(v).strip()
        if not s:
            return []
        return [part.strip().lower() for part in s.split(",") if part.strip()]

    model_config = {
        "env_file": os.getenv("QM_ENV_FILE") or None,
        "case_sensitive": True,
        "extra": "ignore",  # Ignore extra fields from env / optional env_file
    }

    @property
    def provider_policy(self) -> ProviderPolicy:
        """Return the ProviderPolicy for the current MARKET_PROVIDER_POLICY tier."""
        policy_name = str(self.MARKET_PROVIDER_POLICY or "").strip().lower()
        policy = PROVIDER_POLICIES.get(policy_name)
        if policy is not None:
            return policy
        if policy_name not in _unrecognized_market_provider_policy_logged:
            _unrecognized_market_provider_policy_logged.add(policy_name)
            logger.warning(
                "Unrecognized MARKET_PROVIDER_POLICY=%r (normalized=%r); "
                "falling back to tier %r. Valid tiers: %s",
                self.MARKET_PROVIDER_POLICY,
                policy_name,
                "paid",
                ", ".join(sorted(PROVIDER_POLICIES.keys())),
            )
        return PROVIDER_POLICIES["paid"]


# Global settings instance
settings = Settings()


def is_production() -> bool:
    return str(settings.ENVIRONMENT or "").lower() == "production"


_GLOBAL_BROKER_CREDS_FORBIDDEN_IN_PROD = [
    "TASTYTRADE_CLIENT_SECRET",
    "TASTYTRADE_REFRESH_TOKEN",
    "IBKR_FLEX_TOKEN",
    "IBKR_FLEX_QUERY_ID",
]


def validate_production_settings() -> None:
    if not is_production():
        return
    if settings.SECRET_KEY == "your-secret-key-here-change-in-production":
        raise RuntimeError("SECRET_KEY must be set to a secure value in production.")
    if not settings.DATABASE_URL or "sqlite:///" in settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL must point to Postgres in production.")
    if "localhost" in settings.DATABASE_URL or "127.0.0.1" in settings.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL points to localhost — this is the dev default, not a real "
            "Render Postgres connection string. Check the service's env vars in the "
            "Render dashboard (fromDatabase reference may be missing)."
        )
    if not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL must be set in production.")
    if "localhost" in settings.REDIS_URL or "127.0.0.1" in settings.REDIS_URL:
        raise RuntimeError(
            "REDIS_URL points to localhost — check the Render dashboard for the "
            "fromService reference to axiomfolio-redis."
        )
    leaked = [k for k in _GLOBAL_BROKER_CREDS_FORBIDDEN_IN_PROD if getattr(settings, k, None)]
    if leaked:
        raise RuntimeError(
            f"Global broker credentials must NOT be set in production "
            f"(use per-user encrypted credentials instead): {', '.join(leaked)}"
        )
    if settings.ALLOW_DEEP_BACKFILL:
        raise RuntimeError(
            "ALLOW_DEEP_BACKFILL must be False in production. "
            "Deep backfills risk exhausting FMP bandwidth (48.5/50 GB)."
        )
    if not settings.ENCRYPTION_KEY or not str(settings.ENCRYPTION_KEY).strip():
        logger.warning(
            "ENCRYPTION_KEY is unset or empty in production; "
            "per-credential encryption may be unavailable or insecure."
        )
    if settings.ADMIN_SEED_ENABLED:
        logger.warning(
            "ADMIN_SEED_ENABLED is True in production; "
            "disable admin seeding for real deployments."
        )
    cors_origins = settings.CORS_ORIGINS or ""
    cors_lower = cors_origins.lower()
    if "localhost" in cors_lower or "127.0.0.1" in cors_lower:
        logger.warning(
            "CORS_ORIGINS includes localhost or 127.0.0.1 in production; "
            "remove dev origins from the deployed CORS allowlist."
        )
    if not settings.OAUTH_STATE_SECRET or not str(settings.OAUTH_STATE_SECRET).strip():
        logger.warning(
            "OAUTH_STATE_SECRET is unset or empty in production; "
            "OAuth CSRF/state signing should use a strong secret."
        )


# Keep settings as provided; rely on .env and docker-compose. No band-aid normalization here.

# Logging Configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "backend.utils.request_context.RequestIdFilter",
        }
    },
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
        },
        "text": {
            "format": "[%(asctime)s] %(levelname)s %(name)s req=%(request_id)s: %(message)s",
        },
    },
    "handlers": {
        "default": {
            "level": "INFO",
            "formatter": "json" if settings.LOG_FORMAT == "json" else "text",
            "filters": ["request_id"],
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        }
    },
    "root": {"level": "INFO", "handlers": ["default"]},
}

# Note: Use only `settings` for configuration access throughout the codebase.
