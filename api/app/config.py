from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://filefree:filefree_dev@localhost:5432/filefree_dev"

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        """Neon/Supabase provide postgresql:// URLs; asyncpg needs the +asyncpg driver."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            object.__setattr__(self, "DATABASE_URL", url.replace("postgresql://", "postgresql+asyncpg://", 1))
        elif url.startswith("postgres://"):
            object.__setattr__(self, "DATABASE_URL", url.replace("postgres://", "postgresql+asyncpg://", 1))
        return self
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me-to-a-random-64-char-string"
    ENCRYPTION_KEY: str = "change-me-generate-with-fernet"

    OPENAI_API_KEY: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GCS_BUCKET_NAME: str = "filefree-uploads-dev"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    APPLE_CLIENT_ID: str = ""
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY_PATH: str = ""

    FRONTEND_URL: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    APP_VERSION: str = "0.1.0"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
