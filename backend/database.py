"""
AxiomFolio V1 - Database Configuration
======================================

Central database configuration and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys
from typing import Generator

# Shared test DB safety checks (used by both app and pytest)
from backend.utils.db_safety import check_test_database_url

# Database URL from environment or default
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://axiomfolio:axiomfolio@localhost:5432/axiomfolio"
)

# Fail-closed test safety:
# If pytest is running and any code imports backend.database, we refuse to even construct
# an engine unless TEST_DATABASE_URL is present and unambiguously safe. This prevents
# accidental connections to (or destructive operations against) a dev DB during test
# collection/import time.
_PYTEST_RUNNING = "pytest" in sys.modules
if _PYTEST_RUNNING:
    test_db_url = os.getenv("TEST_DATABASE_URL", "")
    if not test_db_url:
        raise RuntimeError(
            "Running under pytest: TEST_DATABASE_URL must be set. "
            "Refusing to create an application engine that could touch a dev DB."
        )
    expected_host = os.getenv("TEST_DB_EXPECTED_HOST", "postgres_test")
    required_user = os.getenv("POSTGRES_TEST_USER") or None
    chk = check_test_database_url(
        test_db_url, expected_host=expected_host, required_user=required_user
    )
    if not chk.ok:
        raise RuntimeError(
            f"Running under pytest: unsafe TEST_DATABASE_URL ({chk.reason}). Refusing to start."
        )
    # Ensure all code paths see the same DB URL in tests.
    os.environ["DATABASE_URL"] = test_db_url
    DATABASE_URL = test_db_url

APP_DATABASE_URL = DATABASE_URL

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DEBUG", "false").lower() == "true",
    pool_pre_ping=True,
    pool_recycle=300,
)

# Raw factory kept private; SessionLocal wrapper enforces test safety in pytest
_RAW_SESSION_FACTORY = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _assert_test_db_guard():
    """Abort if pytest tries to use the app database.

    Rules:
    - If running under pytest (PYTEST_CURRENT_TEST or AXIOMFOLIO_TESTING), require TEST_DATABASE_URL.
    - Require TEST_DATABASE_URL is an unambiguously-safe test DB (postgres_test + *_test).
    - Extra paranoia: require DATABASE_URL == TEST_DATABASE_URL so *any* accidental use of
      backend.database.engine/SessionLocal still targets the test DB.
    """
    is_testing = bool(
        os.getenv("PYTEST_CURRENT_TEST") or os.getenv("AXIOMFOLIO_TESTING")
    )
    if not is_testing:
        return
    test_db_url = os.getenv("TEST_DATABASE_URL", "")
    if not test_db_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is required for tests; refusing to use APP_DATABASE_URL"
        )

    expected_host = os.getenv("TEST_DB_EXPECTED_HOST", "postgres_test")
    required_user = os.getenv("POSTGRES_TEST_USER") or None
    chk = check_test_database_url(
        test_db_url,
        expected_host=expected_host,
        required_user=required_user,
    )
    if not chk.ok:
        raise RuntimeError(
            f"Unsafe TEST_DATABASE_URL ({chk.reason}); refusing to run tests"
        )

    if APP_DATABASE_URL != test_db_url:
        raise RuntimeError(
            "In tests, DATABASE_URL must equal TEST_DATABASE_URL so accidental engine usage stays isolated. "
            f"DATABASE_URL={APP_DATABASE_URL!r} TEST_DATABASE_URL={test_db_url!r}"
        )


def SessionLocal():
    """Guarded session factory. In tests, refuses to hit the app DB."""
    _assert_test_db_guard()
    return _RAW_SESSION_FACTORY()

# Base class for all models (re-export from models)
from backend.models import Base


# Dependency for getting database sessions
def get_db() -> Generator:
    """Database session dependency for FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Direct session creation for scripts
def create_session():
    """Create a database session for scripts and services."""
    return SessionLocal()


# Database initialization
def init_db():
    """Initialize database.

    Production/dev: rely on Alembic migrations exclusively.
    Tests: table lifecycle is handled in backend/tests/conftest.py against TEST_DATABASE_URL.
    """
    # No-op intentionally to avoid schema drift; migrations run on startup.
    return


# Health check
def check_db_health() -> bool:
    """Check if database is accessible."""
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return True
    except Exception:
        return False
