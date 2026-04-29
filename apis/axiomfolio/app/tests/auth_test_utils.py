"""Auth helpers for integration tests.

Pass ``db`` only when register/login run against that same ORM session (for example
``app.dependency_overrides[get_db]`` yields the test ``db_session``). If the client
uses the app's default ``SessionLocal`` for auth, omit ``db`` so approval commits on a
separate connection and login can see it.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session


def make_user_dependency_override(username: str):
    """Return a FastAPI dependency callable for ``app.dependency_overrides[get_current_user]``.

    The returned callable depends on ``get_db`` (the *same* session as the route
    handler), so the ``User`` object is properly attached to the request's DB session.
    This means ``db.commit()`` and ``db.refresh(user)`` inside routes work correctly.
    Suitable for any test that needs to call protected endpoints without a real Clerk JWT.

    Usage::

        from app.api.dependencies import get_current_user
        from app.tests.auth_test_utils import make_user_dependency_override

        app.dependency_overrides[get_current_user] = make_user_dependency_override(username)
        try:
            ...  # make requests
        finally:
            app.dependency_overrides.pop(get_current_user, None)
    """
    from fastapi import Depends
    from sqlalchemy.orm import Session as _Session
    from app.database import get_db
    from app.models.user import User

    async def _override(db: _Session = Depends(get_db)) -> User:
        return db.query(User).filter(User.username == username).first()

    return _override


def approve_user_for_login_tests(username: str, db: Optional[Session] = None) -> None:
    """Approve and verify a user for login tests.

    Args:
        username: The username to approve.
        db: Optional session. If provided, uses this session without committing;
            flushes so other ORM operations in the same transaction see updates.
            If None, creates a new SessionLocal and commits (legacy behavior).
    """
    from app.models.user import User

    if db is not None:
        user = db.query(User).filter(User.username == username).first()
        if user is not None:
            user.is_approved = True
            user.is_verified = True
            db.flush()
        return

    from app.database import SessionLocal

    own = SessionLocal()
    try:
        user = own.query(User).filter(User.username == username).first()
        if user is not None:
            user.is_approved = True
            user.is_verified = True
            own.commit()
    finally:
        own.close()


def approve_user_only_for_login_tests(username: str, db: Optional[Session] = None) -> None:
    """Set is_approved=True only; leaves is_verified unchanged (e.g. False after register).

    Args:
        username: The username to approve.
        db: Optional session. If provided, uses this session without committing;
            flushes so other ORM operations in the same transaction see updates.
            If None, creates a new SessionLocal and commits (legacy behavior).
    """
    from app.models.user import User

    if db is not None:
        user = db.query(User).filter(User.username == username).first()
        if user is not None:
            user.is_approved = True
            db.flush()
        return

    from app.database import SessionLocal

    own = SessionLocal()
    try:
        user = own.query(User).filter(User.username == username).first()
        if user is not None:
            user.is_approved = True
            own.commit()
    finally:
        own.close()
