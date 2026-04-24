"""Auth helpers for integration tests.

Pass ``db`` only when register/login run against that same ORM session (for example
``app.dependency_overrides[get_db]`` yields the test ``db_session``). If the client
uses the app's default ``SessionLocal`` for auth, omit ``db`` so approval commits on a
separate connection and login can see it.
"""

from __future__ import annotations

from sqlalchemy.orm import Session


def approve_user_for_login_tests(username: str, db: Session | None = None) -> None:
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


def approve_user_only_for_login_tests(username: str, db: Session | None = None) -> None:
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
