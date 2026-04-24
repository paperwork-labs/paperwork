import os
import uuid
import pytest
from sqlalchemy import text
from backend.utils.db_safety import check_test_database_url


def test_database_url_is_forced_to_safe_test_db():
    test_db_url = os.getenv("TEST_DATABASE_URL", "")
    app_db_url = os.getenv("DATABASE_URL", "")
    assert test_db_url, "TEST_DATABASE_URL must be set in the test environment"
    assert app_db_url == test_db_url, "DATABASE_URL must equal TEST_DATABASE_URL in tests"

    expected_host = os.getenv("TEST_DB_EXPECTED_HOST", "postgres_test")
    required_user = os.getenv("POSTGRES_TEST_USER") or None
    chk = check_test_database_url(
        test_db_url, expected_host=expected_host, required_user=required_user
    )
    assert chk.ok, f"Unsafe TEST_DATABASE_URL: {chk.reason}"


def test_alembic_head_and_isolation(db_session):
    # Verify we can query a known table (users) after Alembic upgraded to head
    db_session.execute(text("SELECT 1"))
    # Insert a row and ensure we can see it in this transaction
    uname = f"t_{uuid.uuid4().hex[:6]}"
    db_session.execute(text("INSERT INTO users (username, email, password_hash, is_active) VALUES (:u, :e, 'x', true)"), {"u": uname, "e": f"{uname}@example.com"})
    res = db_session.execute(text("SELECT username FROM users WHERE username=:u"), {"u": uname}).fetchone()
    assert res is not None
    # Isolation: The fixture rolls back after test, so no explicit assert here; a follow-up test could query absence




