"""
AxiomFolio - FastAPI Application
"""

from fastapi import FastAPI, Request, Depends
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import logging.config
from datetime import datetime, timezone
import uuid

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# Route imports - organized by domain
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
    portfolio_orders,
    # Strategy
    strategies,
    # Admin (from admin/ folder)
    admin,
    admin_scheduler,
    admin_agent,
    # Settings (from settings/ folder)
    account_management,
    app_settings,
    # Root-level
    activity,
    aggregator,
    watchlist,
)
# Market data (from market/ package)
from backend.api.routes.market import router as market_router
# Webhooks
from backend.api.routes.webhooks import router as webhooks_router
from backend.api.routes.risk import router as risk_router
from backend.api.routes.brain_tools import router as brain_tools_router
from backend.api.routes.execution import router as execution_router
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

# Rate limiting (default limit applies to all routes)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.RATE_LIMIT_STORAGE_URL or None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

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


# Create database tables
@app.on_event("startup")
async def startup_event():
    """Initialize database and services."""
    try:
        validate_production_settings()
        # Alembic migrations run at API startup when AUTO_MIGRATE_ON_STARTUP=true.
        # Render Docker services use this approach (preDeployCommand lacks reliable env injection).
        try:
            import os
            from alembic import command as _alembic_command
            from alembic.config import Config as _AlembicConfig

            if settings.AUTO_MIGRATE_ON_STARTUP:
                backend_dir = os.path.dirname(os.path.dirname(__file__))
                alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
                cfg = _AlembicConfig(alembic_ini_path)
                cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
                logger.info("Starting Alembic migration (lock_timeout=10s, statement_timeout=120s)...")
                _alembic_command.upgrade(cfg, "head")
                logger.info("✅ Alembic migrations applied (upgrade head)")
            else:
                logger.info("Alembic migrations skipped (AUTO_MIGRATE_ON_STARTUP=false)")
        except Exception as mig_e:
            logger.error("Alembic migration FAILED -- refusing to start with stale schema: %s", mig_e, exc_info=True)
            raise SystemExit(1)

        # Seed schedules from catalog and sync to Render (runs on every startup)
        try:
            from backend.scripts.seed_schedules import seed
            from backend.database import SessionLocal
            _db = SessionLocal()
            try:
                seed_result = seed(_db)
                logger.info("✅ Schedule seed: %s", seed_result)
            finally:
                _db.close()
        except Exception as seed_e:
            logger.warning("Schedule seed skipped/failed: %s", seed_e)
        logger.info("Scheduling: Celery Beat drives all schedules from job_catalog (Render crons retired)")

        # Initialize services
        logger.info("🚀 AxiomFolio V1 API starting up...")
        # Seed admin user if explicitly enabled
        try:
            if settings.ADMIN_SEED_ENABLED:
                admin_user = getattr(settings, "ADMIN_USERNAME", None)
                admin_email = getattr(settings, "ADMIN_EMAIL", None)
                admin_password = getattr(settings, "ADMIN_PASSWORD", None)
                if admin_user and admin_email and admin_password:
                    db = SessionLocal()
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
                        logger.info(f"👑 Seeded admin user '{admin_user}'")
                    db.close()
                else:
                    logger.info("Admin seeding skipped (ADMIN_* not set)")
            else:
                logger.info("Admin seeding disabled (ADMIN_SEED_ENABLED=false)")
        except Exception as se:
            logger.warning(f"Admin seeding skipped/failed: {se}")
        # Optional price bootstrap temporarily disabled until MarketDataService is stabilized
        # Seed default user and broker accounts from .env for dev convenience
        try:
            if getattr(settings, "SEED_ACCOUNTS_ON_STARTUP", False):
                seeding = account_config_service.seed_broker_accounts(user_id=1)
                logger.info(f"🌱 Account seeding: {seeding}")
            else:
                logger.info("🌱 Account seeding disabled (SEED_ACCOUNTS_ON_STARTUP=false)")
        except Exception as se:
            logger.warning(f"Account seeding skipped/failed: {se}")

        # Instruments normalization pass (make instruments table pristine after migrations)
        try:
            from backend.services.portfolio.ibkr_sync_service import portfolio_sync_service
            db = SessionLocal()
            norm = portfolio_sync_service.normalize_instruments_from_activity(db)
            db.commit()
            db.close()
            logger.info(f"🧹 Instrument normalization: {norm}")
        except Exception as ne:
            logger.warning(f"Instrument normalization skipped: {ne}")

        # Auto-warm: queue nightly pipeline if market data is stale
        if settings.AUTO_WARM_ON_STARTUP:
            try:
                _auto_warm_if_stale()
            except Exception as warm_e:
                logger.warning(f"Auto-warm skipped/failed: {warm_e}")
        else:
            logger.info("Auto-warm disabled (AUTO_WARM_ON_STARTUP=false)")

    except Exception as e:
        logger.error(f"❌ Startup error: {e}")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    from backend.database import SessionLocal
    from sqlalchemy import text

    db_ok = False
    db_error = None
    db_tables = 0
    alembic_version = None

    try:
        db = SessionLocal()
        result = db.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"))
        db_tables = result.scalar()

        try:
            ver = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = ver.fetchone()
            alembic_version = row[0] if row else "no-row"
        except Exception:
            alembic_version = "no-table"

        db_ok = True
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
    risk_router,
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
app.include_router(strategies, prefix="/api/v1/strategies", tags=["Strategies"])
app.include_router(
    account_management, dependencies=[Depends(require_non_market_access)]
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
    admin_agent,
    prefix="/api/v1/admin",
    tags=["Agent"],
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


# Global error handler — inject CORS headers so browsers can read error bodies
# instead of masking them as opaque "Network Error" / CORS violations.
def _cors_headers_for_origin(origin: str | None) -> dict[str, str]:
    allowed = {
        o.strip()
        for o in (settings.CORS_ORIGINS or "").split(",")
        if o.strip()
    }
    if origin and origin in allowed:
        return {
            "access-control-allow-origin": origin,
            "access-control-allow-credentials": "true",
            "vary": "Origin",
        }
    return {"vary": "Origin"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc):
    """Global exception handler for better error responses."""
    logger.exception("❌ Global exception")

    headers = _cors_headers_for_origin(request.headers.get("origin"))
    body: dict = {
        "error": "Internal server error",
        "timestamp": datetime.now().isoformat(),
    }
    if settings.DEBUG:
        body["message"] = str(exc)

    return JSONResponse(status_code=500, content=body, headers=headers)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
