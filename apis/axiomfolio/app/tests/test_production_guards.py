"""Tests that production environment guards reject unsafe configurations."""

from unittest.mock import patch
import pytest

from app.config import (
    validate_production_settings,
    _GLOBAL_BROKER_CREDS_FORBIDDEN_IN_PROD,
)


@pytest.fixture
def _prod_env(monkeypatch):
    """Minimal valid production config."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a-real-secret-key-not-default")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    monkeypatch.setenv("REDIS_URL", "redis://host:6379/0")
    for var in _GLOBAL_BROKER_CREDS_FORBIDDEN_IN_PROD:
        monkeypatch.delenv(var, raising=False)


def _reload_settings():
    """Re-instantiate settings from current env."""
    from app.config import Settings
    import app.config as cfg
    cfg.settings = Settings()


class TestGlobalBrokerCredsBlockedInProd:
    """Global broker credentials must never be set in production."""

    @pytest.mark.parametrize("var", _GLOBAL_BROKER_CREDS_FORBIDDEN_IN_PROD)
    def test_rejects_each_global_cred(self, _prod_env, monkeypatch, var):
        monkeypatch.setenv(var, "some-leaked-value")
        _reload_settings()
        with pytest.raises(RuntimeError, match="Global broker credentials must NOT"):
            validate_production_settings()

    def test_passes_when_no_global_creds(self, _prod_env):
        _reload_settings()
        validate_production_settings()


class TestProductionRequiresSecrets:
    def test_rejects_default_secret_key(self, _prod_env, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "your-secret-key-here-change-in-production")
        _reload_settings()
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            validate_production_settings()

    def test_rejects_sqlite_in_prod(self, _prod_env, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
        _reload_settings()
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            validate_production_settings()

    def test_rejects_missing_redis(self, _prod_env, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "")
        _reload_settings()
        with pytest.raises(RuntimeError, match="REDIS_URL"):
            validate_production_settings()
