"""medallion: ops"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, formations, health
from app.routes import filing_status

app = FastAPI(
    title="LaunchFree API",
    description="LaunchFree LLC formation backend scaffold",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

allowed_origins = [settings.FRONTEND_URL]
if settings.ENVIRONMENT == "development":
    origins_to_add = ["http://localhost:3002"]
    for origin in origins_to_add:
        if origin != settings.FRONTEND_URL:
            allowed_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Correlation-ID"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(formations.router, prefix="/api/v1")
app.include_router(filing_status.router)
