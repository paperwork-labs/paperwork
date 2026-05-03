import logging
import os
import subprocess
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from api_foundation import (
    LoggingMiddleware,
    RequestIDMiddleware,
    register_exception_handlers,
    register_healthcheck,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from observability.logging import configure_structured_logging
from observability.metrics import configure_metrics
from observability.tracing import configure_tracing
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.database import engine
from app.rate_limit import limiter
from app.redis import close_redis, init_redis
from app.routers import auth, documents, filings, health, tax, waitlist
from app.utils.exceptions import AppException, app_exception_handler
from app.utils.pii_scrubber import setup_pii_scrubbing

logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Run Alembic migrations on startup. Safe for single-instance deploys."""
    if "localhost" in settings.DATABASE_URL or "127.0.0.1" in settings.DATABASE_URL:
        logger.info("Skipping auto-migration (local/default DATABASE_URL)")
        return
    import pathlib

    api_dir = str(pathlib.Path(__file__).resolve().parent.parent)
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=api_dir,
        )
        if result.returncode == 0:
            logger.info("Alembic migrations applied successfully")
        else:
            logger.warning("Alembic migration failed: %s", result.stderr[:500])
    except Exception:
        logger.warning("Could not run Alembic migrations", exc_info=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    configure_structured_logging(
        "filefree",
        log_level="DEBUG" if settings.DEBUG else "INFO",
        extra_fields={"environment": settings.ENVIRONMENT},
    )
    otlp = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip() or None
    configure_metrics("filefree", otlp_endpoint=otlp)
    configure_tracing("filefree", otlp_endpoint=otlp)

    setup_pii_scrubbing()
    db_url = settings.DATABASE_URL
    masked = db_url[:30] + "..." if len(db_url) > 30 else db_url
    logger.info("FileFree API starting up (env=%s, db=%s)", settings.ENVIRONMENT, masked)
    _run_migrations()
    await init_redis()
    yield
    await close_redis()
    await engine.dispose()
    logger.info("FileFree API shut down")


app = FastAPI(
    title="FileFree API",
    description="AI-powered free tax filing — snap your W-2, done in minutes",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

allowed_origins = [settings.FRONTEND_URL]
if settings.FRONTEND_URL.startswith("https://"):
    from urllib.parse import urlparse

    parsed = urlparse(settings.FRONTEND_URL)
    host = parsed.hostname or ""
    if host.startswith("www."):
        allowed_origins.append(f"{parsed.scheme}://{host[4:]}")
    else:
        allowed_origins.append(f"{parsed.scheme}://www.{host}")
if settings.ENVIRONMENT == "development" and settings.FRONTEND_URL != "http://localhost:3000":
    allowed_origins.append("http://localhost:3000")

app.state.limiter = limiter
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-CSRF-Token",
        "X-Correlation-ID",
        "X-Request-Id",
    ],
)
app.add_middleware(SlowAPIMiddleware)

app.include_router(health.router)
app.include_router(waitlist.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(filings.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(tax.router, prefix="/api/v1")

FastAPIInstrumentor.instrument_app(app)
register_exception_handlers(app)
register_healthcheck(app)

app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,  # type: ignore[arg-type]
)
