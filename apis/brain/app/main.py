import logging
import subprocess
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.database import async_session_factory, engine
from app.mcp_server import create_mcp_app
from app.rate_limit import limiter
from app.redis import close_redis, get_redis, init_redis
from app.routers import admin, brain, health, webhooks
from app.services.observability import init_langfuse
from app.tools import memory_tools
from app.utils.correlation import CorrelationIdMiddleware
from app.utils.exceptions import AppException, app_exception_handler
from app.utils.pii_scrubber import setup_pii_scrubbing

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
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
            timeout=30,
            cwd=api_dir,
        )
        if result.returncode == 0:
            logger.info("Alembic migrations applied successfully")
        else:
            logger.error(
                "Alembic migration failed (exit code %s): %s",
                result.returncode,
                result.stderr[:500],
            )
            raise RuntimeError(f"Alembic migration failed with exit code {result.returncode}")
    except Exception:
        logger.error("Could not run Alembic migrations", exc_info=True)
        raise


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    setup_pii_scrubbing()
    db_url = settings.DATABASE_URL
    masked = db_url[:30] + "..." if len(db_url) > 30 else db_url
    logger.info("Brain API starting up (env=%s, db=%s)", settings.ENVIRONMENT, masked)
    _run_migrations()
    await init_redis()
    init_langfuse()
    redis_client = get_redis()
    memory_tools.configure(async_session_factory, redis_client)
    logger.info("Memory tools configured with DB session factory and Redis")
    yield
    await close_redis()
    await engine.dispose()
    logger.info("Brain API shut down")


app = FastAPI(
    title="Brain API",
    description="Paperwork Labs Brain — memory, intelligence, and agent orchestration",
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
if settings.DEBUG and settings.FRONTEND_URL != "http://localhost:3000":
    allowed_origins.append("http://localhost:3000")

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", str(exc))
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "An unexpected error occurred"},
    )


app.include_router(health.router)
app.include_router(brain.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")

mcp_app = create_mcp_app()


@app.middleware("http")
async def mcp_auth_middleware(request: Request, call_next):
    """Validate MCP token on /mcp endpoints. Reject unauthenticated requests."""
    if request.url.path.startswith("/mcp"):
        token = settings.BRAIN_MCP_TOKEN
        if token:
            auth_header = request.headers.get("authorization", "")
            if not auth_header.endswith(token) and request.headers.get("x-mcp-token") != token:
                return JSONResponse(status_code=401, content={"error": "Invalid MCP token"})
    return await call_next(request)


app.mount("/mcp", mcp_app)
logger.info("FastMCP server mounted at /mcp (22 tools, auth-protected)")
