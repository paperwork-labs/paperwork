"""
AxiomFolio - FastAPI Application
"""

from fastapi import FastAPI, Request, Depends
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import os
import logging
import logging.config
from datetime import datetime, timezone
import uuid

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.api.rate_limit import limiter

# Route imports - organized by domain
from backend.api.routes.admin import picks as admin_picks_routes
from backend.api.routes.picks import router as picks_public_router
from backend.api.routes.trade_cards import router as trade_cards_router
from backend.api.routes import (
    # Auth
    auth,
    # Portfolio (from portfolio/ folder)
    portfolio,
    portfolio_live,
    portfolio_dashboard,
    portfolio_stocks,
    portfolio_statements,
    portfolio_options,
    portfolio_categories,
    portfolio_dividends,
    portfolio_income,
    portfolio_orders,
    portfolio_tax_export,
    portfolio_options_tax,
    portfolio_allocation,
    # Strategy
    strategies,
    # Admin (from admin/ folder)
    admin,
    admin_scheduler,
    admin_agent,
    admin_autoops,
    admin_corporate_actions,
    admin_data_quality,
    admin_deploy_health,
    admin_jobs,
    # Settings (from settings/ folder)
    account_management,
    app_settings,
    historical_import,
    # Root-level
    activity,
    aggregator,
    watchlist,
    oauth,
)
from backend.api.routes import connections as connections_routes
# Market data (from market/ package)
from backend.api.routes.market import router as market_router
# Webhooks
from backend.api.routes.webhooks import router as webhooks_router
from backend.api.routes.risk import router as risk_router
from backend.api.routes.account_risk_profile import router as account_risk_profile_router
from backend.api.routes.entitlements import router as entitlements_router
from backend.api.routes.public.stats import router as public_stats_router
from backend.api.routes.pricing import router as pricing_router
from backend.api.routes.brain_tools import router as brain_tools_router
from backend.api.routes.agent_trade_decision import router as agent_trade_decision_router
from backend.api.routes.symbols import router as symbols_router
from backend.api.routes.signals import router as signals_router
from backend.api.routes.execution import router as execution_router
from backend.api.routes.exits import router as exits_router
from backend.api.routes.pipeline import router as pipeline_router
from backend.api.routes.backtest import router as backtest_router
from backend.api.routes.options import router as options_chain_router
from backend.api.routes.shadow_trades import router as shadow_trades_router
from backend.api.routes.portfolio.narrative import router as portfolio_narrative
from backend.api.middleware.rss_observability import RssObservabilityMiddleware
from backend.api.middleware.rate_limit import TenantRateLimitMiddleware
from backend.api.routes.multitenant import (
    admin_costs_router,
    gdpr_router,
)
from backend.api.routes.portfolio.connection_options import (
    router as portfolio_connection_options,
)
from backend.api.routes.positions import router as positions_router
from backend.api.routes.notify import router as notify_router
from backend.api.routes.mcp import router as mcp_router
from backend.api.dependencies import require_non_market_access

# Model imports
from backend.models import Base
from backend.database import engine, SessionLocal
from backend.config import settings, validate_production_settings, LOGGING_CONFIG
from backend.utils.request_context import set_request_id, reset_request_id
from backend.models.user import User, UserRole
from backend.services.portfolio.account_config_service import account_config_service
from backend.api.routes.auth import get_password_hash

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AxiomFolio V1 API",
    description="Professional Trading Platform API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# OpenTelemetry: install tracer + meter providers and attach
# auto-instrumentation to this app instance. When OTEL_EXPORTER_OTLP_ENDPOINT
# is unset the SDK runs in no-op mode (spans created, none exported) so dev
# runs don't need a collector. See backend/observability/tracing.py for
# env-var configuration.
#
# Skip bootstrap during pytest (AXIOMFOLIO_TESTING): importing this module
# would otherwise pin a global TracerProvider and patch httpx/SQLAlchemy
# before observability tests install their own provider or before mocks run.
if os.getenv("AXIOMFOLIO_TESTING") == "1":
    pass
else:
    try:
        from backend.observability import init_metrics, init_tracing

        _otel_environment = "production" if not settings.DEBUG else "dev"
        init_tracing(
            service_name="axiomfolio-api",
            environment=_otel_environment,
            fastapi_app=app,
        )
        init_metrics(service_name="axiomfolio-api")
    except Exception as _otel_exc:  # noqa: BLE001 — observability must never crash boot
        logger.warning(
            "OTel initialization failed (continuing without instrumentation): %s",
            _otel_exc,
            exc_info=True,
        )


def _method_order(method: str) -> int:
    order = {
        "get": 0,
        "post": 1,
        "put": 2,
        "patch": 3,
        "delete": 4,
        "options": 5,
        "head": 6,
        "trace": 7,
    }
    return order.get(method.lower(), 99)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["paths"] = {
        path: dict(sorted(ops.items(), key=lambda item: _method_order(item[0])))
        for path, ops in sorted(schema.get("paths", {}).items(), key=lambda item: item[0])
    }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

# Rate limiting (default limit applies to all routes; see settings.RATE_LIMIT_DEFAULT)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Innermost: runs closest to route handlers, after CORS / gzip / rate-limit in the
# stack — records per-request peak RSS (ru_maxrss) when enabled.
app.add_middleware(RssObservabilityMiddleware)
app.add_middleware(SlowAPIMiddleware)

# Per-tenant rate limit (token-bucket, Redis-backed, fail-CLOSED).
# Sits in front of SlowAPI so a per-tenant 429 wins over the global IP
# default. Allowlists health/auth/webhooks (see middleware module).
app.add_middleware(TenantRateLimitMiddleware)

# GZip responses (>1KB)
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in (settings.CORS_ORIGINS or "").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    token = set_request_id(request_id)
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
    finally:
        reset_request_id(token)


def _auto_warm_if_stale():
    """Check if market data is stale and queue the nightly pipeline.

    Runs on startup when AUTO_WARM_ON_STARTUP=true. Checks the freshest
    MarketSnapshot timestamp — if older than AUTO_WARM_STALE_MINUTES, fires
    the full nightly pipeline via Celery (non-blocking).
    """
    from backend.models.market_data import MarketSnapshot
    from sqlalchemy import func as sqlfunc, select

    db = SessionLocal()
    try:
        latest_ts = db.execute(
            select(sqlfunc.max(MarketSnapshot.analysis_timestamp))
        ).scalar()

        stale_threshold = settings.AUTO_WARM_STALE_MINUTES
        needs_warm = True

        if latest_ts:
            from datetime import timedelta
            age_minutes = (datetime.now(timezone.utc) - latest_ts).total_seconds() / 60
            if age_minutes < stale_threshold:
                logger.info(
                    "Auto-warm: data is fresh (%.0f min old, threshold=%d min). Skipping.",
                    age_minutes, stale_threshold,
                )
                needs_warm = False
            else:
                logger.info(
                    "Auto-warm: data is stale (%.0f min old, threshold=%d min). Queuing pipeline.",
                    age_minutes, stale_threshold,
                )
        else:
            logger.info("Auto-warm: empty DB (cold start). Queuing %d-year deep backfill.", settings.HISTORY_TARGET_YEARS)

        if needs_warm:
            from backend.tasks.celery_app import celery_app
            if latest_ts is None:
                from datetime import date, timedelta
                history_start = (date.today() - timedelta(days=settings.HISTORY_TARGET_YEARS * 365)).isoformat()
                result = celery_app.send_task(
                    "backend.tasks.market.backfill.full_historical",
                    kwargs={"since_date": history_start},
                )
                logger.info("Auto-warm: deep backfill queued (since=%s, task_id=%s)", history_start, result.id)
            else:
                result = celery_app.send_task(
                    "backend.tasks.market.coverage.daily_bootstrap",
                    kwargs={"history_days": 5, "history_batch_size": 25},
                )
                logger.info("Auto-warm: nightly pipeline queued (task_id=%s)", result.id)
    finally:
        db.close()


def _run_migrations() -> None:
    """Run Alembic migrations synchronously. Aborts startup on failure.

    Fast-path: if the DB is already at the script head revision, skip the
    full Alembic upgrade machinery (saves ~5-6 seconds on remote Postgres).
    """
    import os
    from alembic.config import Config as _AlembicConfig

    if not settings.AUTO_MIGRATE_ON_STARTUP:
        logger.info("Alembic migrations skipped (AUTO_MIGRATE_ON_STARTUP=false)")
        return

    backend_dir = os.path.dirname(os.path.dirname(__file__))
    alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
    cfg = _AlembicConfig(alembic_ini_path)
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))

    try:
        from sqlalchemy import text as _text
        from alembic.script import ScriptDirectory
        with engine.connect() as conn:
            current = conn.execute(_text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
        if current:
            script = ScriptDirectory.from_config(cfg)
            head = script.get_current_head()
            if current == head:
                logger.info("Alembic: already at head (%s), skipping upgrade", head)
                return
            logger.info("Alembic: DB at %s, head is %s -- running upgrade", current, head)
    except Exception as e:
        logger.info("Alembic fast-check skipped (%s), running full upgrade", e)

    from alembic import command as _alembic_command
    logger.info("Starting Alembic migration (lock_timeout=10s, statement_timeout=30s)...")
    _alembic_command.upgrade(cfg, "head")
    logger.info("Alembic migrations applied (upgrade head)")


def _sync_deferred_startup() -> None:
    """Non-critical startup work that runs after /health is available.

    Advisory-locked so multi-worker deploys don't race on seeding.
    All failures are logged as warnings and never abort the process.
    """
    from sqlalchemy import text as _sa_text

    _startup_conn = engine.connect()
    _got_lock = False
    try:
        _got_lock = _startup_conn.execute(
            _sa_text("SELECT pg_try_advisory_lock(42)")
        ).scalar()

        if not _got_lock:
            logger.info("Startup lock held by another worker -- skipping seed/admin")
            return

        # Seed schedules from catalog
        try:
            from backend.scripts.seed_schedules import seed
            _db = SessionLocal()
            try:
                seed_result = seed(_db)
                logger.info("Schedule seed: %s", seed_result)
            finally:
                _db.close()
        except Exception as seed_e:
            logger.warning("Schedule seed skipped/failed: %s", seed_e)

        # Seed admin user if explicitly enabled
        try:
            if settings.ADMIN_SEED_ENABLED:
                admin_user = getattr(settings, "ADMIN_USERNAME", None)
                admin_email = getattr(settings, "ADMIN_EMAIL", None)
                admin_password = getattr(settings, "ADMIN_PASSWORD", None)
                if admin_user and admin_email and admin_password:
                    db = SessionLocal()
                    try:
                        existing = (
                            db.query(User)
                            .filter((User.username == admin_user) | (User.email == admin_email))
                            .first()
                        )
                        if not existing:
                            u = User(
                                username=admin_user,
                                email=admin_email,
                                password_hash=get_password_hash(admin_password),
                                role=UserRole.OWNER,
                                is_active=True,
                                is_verified=True,
                                is_approved=True,
                            )
                            db.add(u)
                            db.commit()
                            logger.info("Seeded admin user '%s'", admin_user)
                    finally:
                        db.close()
                else:
                    logger.info("Admin seeding skipped (ADMIN_* not set)")
            else:
                logger.info("Admin seeding disabled (ADMIN_SEED_ENABLED=false)")
        except Exception as se:
            logger.warning("Admin seeding skipped/failed: %s", se)

        # Seed broker accounts
        try:
            if getattr(settings, "SEED_ACCOUNTS_ON_STARTUP", False):
                seeding = account_config_service.seed_broker_accounts(user_id=1)
                logger.info("Account seeding: %s", seeding)
            else:
                logger.info("Account seeding disabled (SEED_ACCOUNTS_ON_STARTUP=false)")
        except Exception as se:
            logger.warning("Account seeding skipped/failed: %s", se)

        # Instruments normalization (gated behind account seeding flag)
        if getattr(settings, "SEED_ACCOUNTS_ON_STARTUP", False):
            try:
                from backend.services.portfolio.ibkr_sync_service import portfolio_sync_service
                db = SessionLocal()
                try:
                    norm = portfolio_sync_service.normalize_instruments_from_activity(db)
                    db.commit()
                    logger.info("Instrument normalization: %s", norm)
                finally:
                    db.close()
            except Exception as ne:
                logger.warning("Instrument normalization skipped: %s", ne)

        # Auto-warm: queue nightly pipeline if market data is stale
        if settings.AUTO_WARM_ON_STARTUP:
            try:
                _auto_warm_if_stale()
            except Exception as warm_e:
                logger.warning("Auto-warm skipped/failed: %s", warm_e)
        else:
            logger.info("Auto-warm disabled (AUTO_WARM_ON_STARTUP=false)")

        # One-shot OptionTaxLot backfill (D140). Broker-agnostic — enqueues
        # the Celery task that iterates every enabled broker account.
        # Idempotent, but heavy, so this flag should be flipped off again
        # after the backfill run completes on the first deploy.
        if getattr(settings, "BACKFILL_OPTION_TAX_LOTS_ON_STARTUP", False):
            try:
                from backend.tasks.celery_app import celery_app as _celery
                res = _celery.send_task(
                    "backend.tasks.portfolio.reconciliation.backfill_option_tax_lots",
                    kwargs={},
                )
                logger.info(
                    "OptionTaxLot backfill enqueued on startup: task_id=%s",
                    res.id,
                )
            except Exception as bf_e:
                logger.warning(
                    "OptionTaxLot startup backfill skipped/failed: %s", bf_e
                )
        else:
            logger.info(
                "OptionTaxLot backfill disabled (BACKFILL_OPTION_TAX_LOTS_ON_STARTUP=false)"
            )

    finally:
        if _got_lock:
            _startup_conn.execute(_sa_text("SELECT pg_advisory_unlock(42)"))
        _startup_conn.close()

    logger.info("Deferred startup complete")


async def _deferred_startup() -> None:
    """Run non-critical startup in a background thread."""
    try:
        await asyncio.to_thread(_sync_deferred_startup)
    except Exception as e:
        logger.warning("Deferred startup error (non-fatal): %s", e)


@app.on_event("startup")
async def startup_event():
    """Initialize database and services.

    Only migration runs synchronously (schema must be correct before
    serving).  Everything else is deferred to a background task so
    /health becomes available immediately.
    """
    validate_production_settings()

    try:
        _run_migrations()
    except Exception as mig_e:
        logger.error(
            "Alembic migration FAILED -- refusing to start with stale schema: %s",
            mig_e, exc_info=True,
        )
        raise SystemExit(1)

    logger.info("AxiomFolio V1 API starting up...")
    asyncio.create_task(_deferred_startup())


# Lightweight health check for Render probes (no DB, instant response)
@app.get("/health")
async def health_check():
    """Fast health check for load balancers. No DB queries."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "api": "AxiomFolio V1",
    }


# Detailed health check with DB validation (admin use)
@app.get("/health/full")
async def health_check_full():
    """Full health check with DB connectivity. Use /health for probes."""
    from backend.database import SessionLocal
    from sqlalchemy import text

    db_ok = False
    db_error = None
    db_tables = 0
    alembic_version = None

    try:
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"))
            db_tables = result.scalar()

            try:
                ver = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                row = ver.fetchone()
                alembic_version = row[0] if row else "no-row"
            except Exception:
                alembic_version = "no-table"

            db_ok = True
        finally:
            db.close()
    except Exception as e:
        db_error = str(e)[:200]

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "api": "AxiomFolio V1",
        "db": {
            "connected": db_ok,
            "tables": db_tables,
            "alembic_version": alembic_version,
            "error": db_error,
        },
    }


# API root
@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "message": "AxiomFolio V1 - Professional Trading Platform API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "api_base": "/api/v1",
    }


# Include route modules - TEMPORARY: Only core routes for FlexQuery sync stabilization
app.include_router(auth, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(
    portfolio,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_live,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_dividends,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_income,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_dashboard,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_stocks,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_statements,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_options,
    prefix="/api/v1/portfolio/options",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_options_tax,
    prefix="/api/v1/portfolio/options",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_categories,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_orders,
    prefix="/api/v1",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_tax_export,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_narrative,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_connection_options,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    portfolio_allocation,
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    positions_router,
    prefix="/api/v1",
    tags=["Positions"],
    dependencies=[Depends(require_non_market_access)],
)
# Notify-me waitlist: tiny POST endpoint backing the "Notify me" CTAs on
# coming-soon broker cards. Authentication required; no payload persistence
# in this PR (logged at WARNING level (operator pulls from logs); email
# delivery deferred to future PR; see route docstring).
app.include_router(
    notify_router,
    prefix="/api/v1/notify",
    tags=["Notify"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    risk_router,
    prefix="/api/v1",
    tags=["Risk"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    account_risk_profile_router,
    prefix="/api/v1",
    tags=["Risk"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    execution_router,
    prefix="/api/v1",
    tags=["Execution"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    exits_router,
    prefix="/api/v1",
    tags=["Exits"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(strategies, prefix="/api/v1/strategies", tags=["Strategies"])
app.include_router(
    account_management, dependencies=[Depends(require_non_market_access)]
)
app.include_router(
    historical_import, dependencies=[Depends(require_non_market_access)]
)
app.include_router(app_settings, prefix="/api/v1", tags=["App Settings"])
app.include_router(market_router, prefix="/api/v1/market-data", tags=["Market Data & Technicals"])
app.include_router(
    activity,
    prefix="/api/v1/portfolio",
    tags=["Activity"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    aggregator,
    prefix="/api/v1/aggregator",
    tags=["Aggregator"],
)
app.include_router(
    watchlist,
    prefix="/api/v1",
    tags=["Watchlist"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    options_chain_router,
    prefix="/api/v1",
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    shadow_trades_router,
    prefix="/api/v1",
    tags=["Shadow Trades"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    oauth,
    prefix="/api/v1/oauth",
    tags=["OAuth Brokers"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    connections_routes.router,
    prefix="/api/v1/connections",
    tags=["Connections"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    admin,
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    admin_scheduler,
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    admin_jobs,
    prefix="/api/v1/admin",
    tags=["Admin Jobs"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    admin_agent,
    prefix="/api/v1/admin",
    tags=["Agent"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    admin_autoops,
    prefix="/api/v1/admin",
    tags=["Agent"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    admin_corporate_actions,
    prefix="/api/v1/admin",
    tags=["Corporate Actions"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    admin_data_quality,
    prefix="/api/v1/admin",
    tags=["Admin Data Quality"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    admin_deploy_health,
    prefix="/api/v1",
    tags=["Admin Deploy Health"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    admin_picks_routes.router,
    prefix="/api/v1/admin",
    tags=["Admin Picks"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    picks_public_router,
    prefix="/api/v1/picks",
    tags=["Picks"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    trade_cards_router,
    prefix="/api/v1/trade-cards",
    tags=["Trade Cards"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    pipeline_router,
    prefix="/api/v1/pipeline",
    tags=["Pipeline"],
    dependencies=[Depends(require_non_market_access)],
)
app.include_router(
    webhooks_router,
    prefix="/api/v1/webhooks",
    tags=["Webhooks"],
)
app.include_router(
    brain_tools_router,
    prefix="/api/v1/tools",
    tags=["Brain Tools"],
)
app.include_router(
    agent_trade_decision_router,
    prefix="/api/v1/agent",
    tags=["Agent — Trade Decisions"],
)
# Symbol master: read-only resolution + audit endpoints. The master
# table is global (no user_id) — auth still required so the catalog
# can't be scraped anonymously, but no tenant filter is applied
# because none would be meaningful here.
app.include_router(
    symbols_router,
    prefix="/api/v1",
    tags=["Symbols"],
)
# Auxiliary Finviz/Zacks-style context (symbol-level; not tenant-scoped rows).
app.include_router(
    signals_router,
    prefix="/api/v1",
    tags=["Signals"],
)
# Entitlements: tier-gating source of truth.
# /catalog is intentionally not behind require_non_market_access because the
# pricing page must render for users who don't have portfolio access.
app.include_router(
    entitlements_router,
    prefix="/api/v1",
    tags=["Entitlements"],
)
app.include_router(
    public_stats_router,
    prefix="/api/v1/public",
)
# MCP (Model Context Protocol): per-user bearer-token gateway for read-only
# AI agent access. Token CRUD is JWT-authed via the route handlers; the
# /jsonrpc transport is bearer-authed. Not behind require_non_market_access
# because token management must remain available even for users on tiers
# without market data access.
app.include_router(
    mcp_router,
    prefix="/api/v1/mcp",
    tags=["MCP"],
)
# Backtest analysis: walk-forward (tier: research.walk_forward_optimizer) and
# Monte Carlo (research.monte_carlo) share ``/api/v1/backtest`` via the
# aggregated router in ``backend.api.routes.backtest``.

# Public pricing catalog: tier display data + features per tier.
# No auth — the marketing /pricing page renders the exact same payload
# logged-in users see in their upgrade prompts. Intentionally NOT behind
# require_non_market_access (logged-out visitors must reach this).
app.include_router(
    pricing_router,
    prefix="/api/v1/pricing",
    tags=["Pricing"],
)
app.include_router(
    backtest_router,
    prefix="/api/v1/backtest",
    tags=["Backtest"],
    dependencies=[Depends(require_non_market_access)],
)

# GDPR data-subject rights (per-tenant, scoped to current_user).
app.include_router(
    gdpr_router,
    dependencies=[Depends(require_non_market_access)],
)
# Admin: per-tenant cost rollup view.
app.include_router(
    admin_costs_router,
    dependencies=[Depends(require_non_market_access)],
)


# Global error handler — inject CORS headers on unhandled errors so browsers
# surface JSON instead of masking ALB/worker failures as "CORS blocked".
@app.exception_handler(Exception)
async def cors_safe_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception path=%s error=%s",
        request.url.path,
        exc,
        exc_info=True,
    )
    origin = request.headers.get("origin") or ""
    allowed = [
        o.strip()
        for o in (settings.CORS_ORIGINS or "").split(",")
        if o.strip()
    ]
    allow_origin = origin if origin in allowed else ""
    cors_headers = (
        {
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
        if allow_origin
        else {}
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "internal_server_error",
            "path": str(request.url.path),
        },
        headers=cors_headers,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
