import os
from typing import Optional
from pydantic_settings import BaseSettings


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
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300
    CELERY_TASK_TIME_LIMIT: int = 360

    # API Keys
    ALPHA_VANTAGE_API_KEY: Optional[str] = None
    FINNHUB_API_KEY: Optional[str] = None
    TWELVE_DATA_API_KEY: Optional[str] = None
    FMP_API_KEY: Optional[str] = None

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

    # Alpaca Configuration
    ALPACA_API_KEY: Optional[str] = None
    ALPACA_API_SECRET: Optional[str] = None
    ALPACA_TRADING_MODE: str = "paper"  # paper | live

    # Schwab (optional) - comma-separated account numbers for seeding
    SCHWAB_ACCOUNTS: Optional[str] = None
    SCHWAB_CLIENT_ID: Optional[str] = None
    SCHWAB_CLIENT_SECRET: Optional[str] = None
    SCHWAB_REDIRECT_URI: Optional[str] = None
    SCHWAB_AUTH_BASE: Optional[str] = None
    SCHWAB_CLIENT_ID_SUFFIX: Optional[str] = None

    # Discord Configuration (5 separate webhooks for different purposes)
    DISCORD_WEBHOOK_SIGNALS: Optional[str] = None  # Entry/exit signals
    DISCORD_WEBHOOK_PORTFOLIO_DIGEST: Optional[str] = None  # Portfolio summaries
    DISCORD_WEBHOOK_MORNING_BREW: Optional[str] = None  # Daily scans & market updates
    DISCORD_WEBHOOK_PLAYGROUND: Optional[str] = None  # Test notifications
    DISCORD_WEBHOOK_SYSTEM_STATUS: Optional[str] = None  # System status updates

    # Discord Bot API (token + channel IDs). Prefer this for production-ready, scheduled messaging.
    DISCORD_BOT_TOKEN: Optional[str] = None
    DISCORD_BOT_DEFAULT_CHANNEL_ID: Optional[str] = None

    # Security Configuration
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    OAUTH_STATE_SECRET: Optional[str] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENCRYPTION_KEY: Optional[str] = None
    ENABLE_TRADING: bool = False
    ALLOW_LIVE_ORDERS: bool = False
    SEED_ACCOUNTS_ON_STARTUP: bool = False
    AUTO_MIGRATE_ON_STARTUP: bool = False

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
    RENDER_SYNC_ON_STARTUP: bool = True
    RENDER_REPO_URL: str = "https://github.com/sankalp404/axiomfolio.git"

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
    # - paid: higher concurrency (FMP is the primary provider)
    # - free: lower concurrency (avoid hammering free-tier sources)
    MARKET_BACKFILL_CONCURRENCY_PAID: int = 25
    MARKET_BACKFILL_CONCURRENCY_FREE: int = 5
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

    # Retention defaults for intraday data
    RETENTION_MAX_DAYS_5M: int = 90
    # Alert when retention deletes exceed this count in a run.
    RETENTION_DELETE_WARN_THRESHOLD: int = 250000

    # Snapshot computation window (daily bars). Needs to be large enough for:
    # - 200D SMA
    # - ~52-week RS computations on weekly resample
    SNAPSHOT_DAILY_BARS_LIMIT: int = 400

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
    model_config = {
        "env_file": os.getenv("QM_ENV_FILE") or None,
        "case_sensitive": True,
        "extra": "ignore",  # Ignore extra fields from env / optional env_file
    }


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


# Keep settings as provided; rely on .env and docker-compose. No band-aid normalization here.

# Market Data Configuration
MARKET_DATA_PROVIDERS = {"primary": "yfinance", "fallback": "alpha_vantage"}

# Technical Indicators Configuration
INDICATORS_CONFIG = {
    "sma_periods": [10, 20, 50, 200],
    "ema_periods": [12, 26],
    "rsi_period": 14,
    "bollinger_period": 20,
    "bollinger_std": 2,
}

# Portfolio Configuration
PORTFOLIO_CONFIG = {
    "default_currency": "USD",
    "risk_free_rate": 0.02,  # 2% risk-free rate
    "benchmark_symbol": "SPY",
}

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
