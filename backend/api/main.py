"""
AxiomFolio V1 - Clean FastAPI Application
Replaces the massive monolithic API routes with focused, organized endpoints.
"""

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import logging.config
from datetime import datetime
import uuid

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# Route imports - TEMPORARY: Only core routes for FlexQuery sync stabilization
from backend.api.routes import (
    auth,
    portfolio,
    portfolio_live,
    portfolio_dashboard,
    portfolio_stocks,
    portfolio_statements,
    portfolio_options,
    portfolio_dividends,
    atr,
    # strategies,      # DISABLED: Causing import errors with strategy_manager
    market_data,
    # notifications,   # DISABLED: Non-essential for FlexQuery sync
    # admin           # DISABLED: Non-essential for FlexQuery sync
)
from backend.api.routes import activity as activity_routes
from backend.api.routes import aggregator as aggregator_routes

# Import new account management routes
from backend.api.routes import account_management

# Model imports
from backend.models import Base
from backend.database import engine, SessionLocal
from backend.config import settings, validate_production_settings, LOGGING_CONFIG
from backend.utils.request_context import set_request_id, reset_request_id
from backend.models.broker_account import (
    BrokerAccount,
    BrokerType,
    AccountType,
    AccountStatus,
    SyncStatus,
)
from backend.models.user import User, UserRole
from backend.services.clients.tastytrade_client import (
    TastyTradeClient,
    TASTYTRADE_AVAILABLE,
)
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


# Create database tables
@app.on_event("startup")
async def startup_event():
    """Initialize database and services."""
    try:
        validate_production_settings()
        # Apply Alembic migrations automatically on startup
        try:
            import os
            from alembic import command as _alembic_command
            from alembic.config import Config as _AlembicConfig

            if settings.AUTO_MIGRATE_ON_STARTUP:
                backend_dir = os.path.dirname(os.path.dirname(__file__))
                alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
                cfg = _AlembicConfig(alembic_ini_path)
                # Force script_location to absolute path to avoid '/app/alembic' resolution
                cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
                _alembic_command.upgrade(cfg, "head")
                logger.info("✅ Alembic migrations applied (upgrade head)")
            else:
                logger.info("Alembic migrations skipped (AUTO_MIGRATE_ON_STARTUP=false)")
        except Exception as mig_e:
            logger.warning(f"Alembic migration skipped/failed: {mig_e}")

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
                            role=UserRole.ADMIN,
                            is_active=True,
                            is_verified=True,
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

        # Optional: TastyTrade autodiscovery (opt-in only)
        try:
            if (
                TASTYTRADE_AVAILABLE
                and getattr(settings, "TASTYTRADE_DISCOVER_ON_STARTUP", False)
                and getattr(settings, "TASTYTRADE_USERNAME", None)
                and getattr(settings, "TASTYTRADE_PASSWORD", None)
            ):
                client = TastyTradeClient()
                ok = await client.connect_with_retry()
                if ok:
                    accounts = await client.get_accounts()
                    if accounts:
                        db = SessionLocal()
                        created = 0
                        updated = 0
                        for acc in accounts:
                            acct_num = acc.get("account_number") or acc.get("account")
                            if not acct_num:
                                continue
                            existing = (
                                db.query(BrokerAccount)
                                .filter(
                                    BrokerAccount.user_id == 1,
                                    BrokerAccount.broker == BrokerType.TASTYTRADE,
                                    BrokerAccount.account_number == acct_num,
                                )
                                .first()
                            )
                            if existing:
                                existing.account_name = (
                                    acc.get("nickname")
                                    or existing.account_name
                                    or f"TastyTrade ({acct_num})"
                                )
                                existing.account_type = AccountType.TAXABLE
                                updated += 1
                            else:
                                new_acc = BrokerAccount(
                                    user_id=1,
                                    broker=BrokerType.TASTYTRADE,
                                    account_number=acct_num,
                                    account_name=acc.get("nickname")
                                    or f"TastyTrade ({acct_num})",
                                    account_type=AccountType.TAXABLE,
                                    status=AccountStatus.ACTIVE,
                                    is_enabled=True,
                                    sync_status=SyncStatus.NEVER_SYNCED,
                                    currency="USD",
                                )
                                db.add(new_acc)
                                created += 1
                        db.commit()
                        db.close()
                        logger.info(
                            f"🔎 TastyTrade autodiscovery: {created} created, {updated} updated"
                        )
                await client.disconnect()
        except Exception as e:
            logger.warning(f"TastyTrade autodiscovery skipped: {e}")

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

    except Exception as e:
        logger.error(f"❌ Startup error: {e}")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "api": "AxiomFolio V1",
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
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["Portfolio"])
app.include_router(
    portfolio_live.router, prefix="/api/v1/portfolio", tags=["Portfolio"]
)
app.include_router(
    portfolio_dividends.router, prefix="/api/v1/portfolio", tags=["Portfolio"]
)
app.include_router(
    portfolio_dashboard.router, prefix="/api/v1/portfolio", tags=["Portfolio"]
)
app.include_router(
    portfolio_stocks.router, prefix="/api/v1/portfolio", tags=["Portfolio"]
)
app.include_router(
    portfolio_statements.router, prefix="/api/v1/portfolio", tags=["Portfolio"]
)
app.include_router(
    portfolio_options.router, prefix="/api/v1/portfolio/options", tags=["Portfolio"]
)
# app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["Strategies"])  # DISABLED: Import errors
# ATR endpoints remain disabled
# app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])  # DISABLED: Non-essential
from backend.api.routes import admin
from backend.api.routes import admin_scheduler
app.include_router(account_management.router)
app.include_router(market_data.router, prefix="/api/v1/market-data", tags=["Market Data & Technicals"])
app.include_router(activity_routes.router, prefix="/api/v1/portfolio", tags=["Activity"])
app.include_router(aggregator_routes.router, prefix="/api/v1/aggregator", tags=["Aggregator"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(admin_scheduler.router, prefix="/api/v1/admin", tags=["Admin"])


# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for better error responses."""
    logger.error(f"❌ Global exception: {exc}")

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "timestamp": datetime.now().isoformat(),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
