"""
Test configuration for AxiomFolio backend tests.
"""

import pytest
import sys
import os
import inspect as pyinspect

from sqlalchemy import text

from backend.utils.db_safety import check_test_database_url


@pytest.fixture(autouse=True, scope="session")
def _enable_fast_test_mode():
    """Ensure code runs in fast test mode across the suite."""
    os.environ["AXIOMFOLIO_TESTING"] = "1"
    yield
    os.environ.pop("AXIOMFOLIO_TESTING", None)


# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Fix imports to use correct model names from __init__.py
try:
    from backend.models import Base, User, BrokerAccount, Instrument  # Fixed imports
    from sqlalchemy import inspect
    from sqlalchemy.exc import ProgrammingError
    from sqlalchemy.engine import Engine
    MODELS_AVAILABLE = True
except ImportError as e:
    MODELS_AVAILABLE = False
    IMPORT_ERROR = str(e)


@pytest.fixture(scope="session")
def test_db(request):
    """Create an isolated test database engine and metadata.

    Safety:
    - Requires TEST_DATABASE_URL. If missing, skip DB tests.
    - Requires TEST_DATABASE_URL is unambiguously a test DB URL (postgres_test + *_test).
    - Extra paranoia: requires DATABASE_URL == TEST_DATABASE_URL so accidental engine usage stays isolated.
    """
    if not MODELS_AVAILABLE:
        pytest.skip(
            f"Models not available: {IMPORT_ERROR if not MODELS_AVAILABLE else ''}"
        )

    import os
    from sqlalchemy import create_engine
    from backend.database import DATABASE_URL as APP_DATABASE_URL
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_command

    TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
    if not TEST_DATABASE_URL:
        pytest.skip(
            "TEST_DATABASE_URL not set; skipping DB tests to protect development database"
        )

    expected_host = os.getenv("TEST_DB_EXPECTED_HOST", "postgres_test")
    required_user = os.getenv("POSTGRES_TEST_USER") or None
    chk = check_test_database_url(
        TEST_DATABASE_URL, expected_host=expected_host, required_user=required_user
    )
    if not chk.ok:
        raise pytest.UsageError(
            f"Unsafe TEST_DATABASE_URL ({chk.reason}). "
            "Refusing to run any DB tests."
        )
    if APP_DATABASE_URL != TEST_DATABASE_URL:
        raise pytest.UsageError(
            "In tests, DATABASE_URL must equal TEST_DATABASE_URL so accidental engine usage stays isolated. "
            f"DATABASE_URL={APP_DATABASE_URL!r} TEST_DATABASE_URL={TEST_DATABASE_URL!r}"
        )

    test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    # Run Alembic migrations on the test database
    cfg = AlembicConfig(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    # script_location must point to backend/alembic
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    # override URL to TEST DB
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    alembic_command.upgrade(cfg, "heads")

    # Extra safety for test schema completeness:
    # Some models may exist ahead of Alembic coverage. In tests we prefer a usable schema
    # (isolated DB) over failing with missing tables during collection.
    Base.metadata.create_all(bind=test_engine)

    # Canary/sentinel: prove we're on a dedicated test database (and keep it that way).
    sentinel_marker = os.getenv("TEST_DB_SENTINEL_MARKER", "axiomfolio_pytest_sentinel_v1")
    # Use Engine.begin() to avoid clashing with SQLAlchemy's autobegin behavior.
    with test_engine.begin() as conn:
        dbname = conn.execute(text("SELECT current_database()")).scalar()
        if not (dbname and str(dbname).endswith("_test")):
            raise pytest.UsageError(
                f"Refusing to run: connected database {dbname!r} does not end with '_test'"
            )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS axiomfolio_test_sentinel (
                  id INTEGER PRIMARY KEY,
                  marker TEXT NOT NULL,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO axiomfolio_test_sentinel (id, marker)
                VALUES (1, :marker)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"marker": sentinel_marker},
        )
        marker = conn.execute(
            text("SELECT marker FROM axiomfolio_test_sentinel WHERE id=1")
        ).scalar()
        if marker != sentinel_marker:
            raise pytest.UsageError(
                "Test DB sentinel mismatch; refusing to proceed. "
                f"Expected {sentinel_marker!r}, got {marker!r}"
            )

    try:
        yield test_engine
    finally:
        # Schema remains for session; per-test transactions provide isolation
        pass


def pytest_addoption(parser):
    parser.addoption(
        "--allow-destructive-tests",
        action="store_true",
        default=False,
        help="Allow tests marked as destructive to run",
    )


@pytest.fixture
def db_session(test_db, request):
    """Session per test with transaction + nested savepoint, rolls back after test."""
    if request.node.get_closest_marker("no_db"):
        yield None
        return
    if test_db is None:
        # Session-scoped fixture opted out of DB; provide None for this test
        yield None
        return
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import event
    connection = test_db.connect()
    transaction = connection.begin()
    SessionForTests = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = SessionForTests()
    # Start a SAVEPOINT so code under test can call session.commit safely
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        # When the nested transaction ends, open a new one
        if trans.nested and not getattr(trans._parent, "nested", False):  # type: ignore[attr-defined]
            sess.begin_nested()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _no_global_cleanup_marker():
    """No-op cleanup; isolation handled via transaction per test."""
    yield


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")

    return User(username="testuser", email="test@example.com", full_name="Test User")


@pytest.fixture(autouse=True)
def _schema_guard(db_session):
    """Skip DB tests if core tables are missing in the test database."""
    if db_session is None:
        return
    inspector = inspect(db_session.bind)
    required = ["users", "broker_accounts"]
    missing = [t for t in required if not inspector.has_table(t)]
    if missing:
        pytest.skip(f"Test DB not migrated; missing tables: {', '.join(missing)}")


def pytest_collection_modifyitems(items):
    """Fail fast on forbidden DB imports and mark destructive tests for skipping unless enabled."""
    violations = []
    destructive_items = []

    def _is_forbidden(obj, name: str) -> bool:
        if name == "SessionLocal":
            return True
        if name == "engine":
            try:
                from sqlalchemy.engine import Engine as _Engine
                return isinstance(obj, _Engine)
            except Exception:
                return False
        if name == "create_engine":
            return callable(obj) and getattr(obj, "__module__", "").startswith("sqlalchemy")
        return False

    for item in items:
        mod = item.module
        for name in ("SessionLocal", "engine", "create_engine"):
            if name in mod.__dict__ and _is_forbidden(mod.__dict__[name], name):
                violations.append(f"{mod.__name__}:{name}")
        if item.get_closest_marker("destructive"):
            destructive_items.append(item)

    if violations:
        uniq = sorted(set(violations))
        raise pytest.UsageError(
            "Tests must use db_session fixture; forbidden DB handles detected in: "
            + ", ".join(uniq)
        )

    if items:
        cfg = items[0].config
        allow_destructive = (
            os.getenv("ALLOW_DESTRUCTIVE_TESTS") == "1"
            or cfg.getoption("--allow-destructive-tests", default=False)
        )
        if destructive_items and not allow_destructive:
            skip_marker = pytest.mark.skip(
                reason="Destructive tests disabled; set ALLOW_DESTRUCTIVE_TESTS=1 or use --allow-destructive-tests"
            )
            for it in destructive_items:
                it.add_marker(skip_marker)
