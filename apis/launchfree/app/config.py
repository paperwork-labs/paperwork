"""medallion: ops"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:3002"
    DEBUG: bool = True
    SESSION_COOKIE_NAME: str = "session"
    # Filing-engine POST /filings/{id}/status — send header X-Filing-Internal-Token
    FILING_STATUS_INTERNAL_SECRET: str | None = None

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/launchfree"

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        """Neon/Supabase provide postgresql:// URLs; asyncpg needs the +asyncpg driver.
        Also strips query params unsupported by asyncpg (e.g. channel_binding)."""
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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
