from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://brain:brain_dev@localhost:5432/brain_dev"

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        """Neon provides postgresql:// URLs; asyncpg needs the +asyncpg driver."""
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

    REDIS_URL: str = "redis://localhost:6379/1"
    SECRET_KEY: str = "change-me-to-a-random-64-char-string"
    ENCRYPTION_KEY: str = "change-me-generate-with-fernet"

    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    VAULT_API_KEY: str = ""
    BRAIN_API_SECRET: str = ""
    STUDIO_URL: str = "https://paperworklabs.com"

    FRONTEND_URL: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    APP_VERSION: str = "0.1.0"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def check_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT != "development":
            if self.SECRET_KEY == "change-me-to-a-random-64-char-string":
                raise ValueError("SECRET_KEY must be changed from default in production")
            if self.ENCRYPTION_KEY == "change-me-generate-with-fernet":
                raise ValueError("ENCRYPTION_KEY must be changed from default in production")
        return self


settings = Settings()
