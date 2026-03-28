from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:3002"
    DEBUG: bool = True
    SESSION_COOKIE_NAME: str = "session"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/launchfree"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
