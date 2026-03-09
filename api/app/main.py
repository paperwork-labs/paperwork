import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import settings
from app.database import engine
from app.routers import auth, documents, filings, health, tax, waitlist
from app.utils.correlation import CorrelationIdMiddleware
from app.utils.exceptions import AppException, app_exception_handler
from app.utils.pii_scrubber import setup_pii_scrubbing

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    setup_pii_scrubbing()
    logger.info("FileFree API starting up (env=%s)", settings.ENVIRONMENT)
    yield
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
if settings.FRONTEND_URL != "http://localhost:3000":
    allowed_origins.append("http://localhost:3000")

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
limiter = Limiter(key_func=get_remote_address)
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
app.include_router(waitlist.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(filings.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(tax.router, prefix="/api/v1")
