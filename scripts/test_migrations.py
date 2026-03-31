#!/usr/bin/env python3
"""
Test Migrations Script
======================

Validates that all Alembic migrations can be applied cleanly.
Run this before deploying to catch migration issues early.

Usage:
    python scripts/test_migrations.py

Exit codes:
    0 - All migrations passed
    1 - Migration test failed
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR.parent))


def run_command(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run a command and return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        cwd=cwd or str(BACKEND_DIR.parent),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_migrations_forward():
    """Test that all migrations can be applied from scratch."""
    print("=" * 60)
    print("Testing migrations (upgrade to head)...")
    print("=" * 60)
    
    # Use a test database URL or in-memory SQLite
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "sqlite:///./test_migrations.db"
    )
    
    env = os.environ.copy()
    env["DATABASE_URL"] = test_db_url
    
    # Run alembic upgrade head
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        env=env,
    )
    
    if result.returncode != 0:
        print("FAILED: alembic upgrade head")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        return False
    
    print("PASSED: All migrations applied successfully")
    print(f"Output: {result.stdout}")
    return True


def test_migrations_roundtrip():
    """Test upgrade -> downgrade -> upgrade cycle."""
    print("\n" + "=" * 60)
    print("Testing migration roundtrip (down to base, up to head)...")
    print("=" * 60)
    
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "sqlite:///./test_migrations.db"
    )
    
    env = os.environ.copy()
    env["DATABASE_URL"] = test_db_url
    
    # Downgrade to base
    result = subprocess.run(
        ["alembic", "downgrade", "base"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        env=env,
    )
    
    if result.returncode != 0:
        print("FAILED: alembic downgrade base")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        return False
    
    print("PASSED: Downgrade to base successful")
    
    # Upgrade back to head
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        env=env,
    )
    
    if result.returncode != 0:
        print("FAILED: alembic upgrade head (after downgrade)")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        return False
    
    print("PASSED: Roundtrip migration successful")
    return True


def check_model_server_defaults():
    """Audit models for missing server_default on NOT NULL columns with Python defaults."""
    print("\n" + "=" * 60)
    print("Auditing models for missing server_default...")
    print("=" * 60)
    
    import re
    from pathlib import Path
    
    models_dir = BACKEND_DIR / "models"
    issues = []
    
    # Pattern to find Column definitions with nullable=False and default= but no server_default
    # This is a simplified check - the explore subagent found the full list
    pattern = re.compile(
        r'Column\([^)]*nullable\s*=\s*False[^)]*default\s*=[^)]*\)',
        re.MULTILINE | re.DOTALL
    )
    
    for py_file in models_dir.glob("*.py"):
        content = py_file.read_text()
        
        # Look for created_at without server_default
        if "created_at" in content:
            if "server_default" not in content:
                # Check if it's actually nullable=False
                if re.search(r'created_at.*nullable\s*=\s*False', content, re.DOTALL):
                    issues.append(f"{py_file.name}: created_at may need server_default")
    
    if issues:
        print(f"WARNINGS ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
        print("\nThese columns may fail on INSERT if SQLAlchemy defaults don't fire.")
        print("Consider adding server_default=func.now() or server_default='value'")
    else:
        print("PASSED: No obvious server_default issues found")
    
    return True  # This is advisory, not a hard failure


def cleanup_test_db():
    """Remove test database file if it exists."""
    test_db = Path("./test_migrations.db")
    if test_db.exists():
        test_db.unlink()
        print("Cleaned up test database")


def main():
    """Run all migration tests."""
    print("AxiomFolio Migration Test Suite")
    print("=" * 60)
    
    all_passed = True
    
    try:
        # Clean up any previous test DB
        cleanup_test_db()
        
        # Test forward migrations
        if not test_migrations_forward():
            all_passed = False
        
        # Test roundtrip (only if forward passed)
        if all_passed and not test_migrations_roundtrip():
            all_passed = False
        
        # Advisory check for server_defaults
        check_model_server_defaults()
        
    finally:
        # Always clean up
        cleanup_test_db()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED")
        return 0
    else:
        print("SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
