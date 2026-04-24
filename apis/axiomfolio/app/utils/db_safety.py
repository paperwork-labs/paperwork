from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.engine.url import make_url


@dataclass(frozen=True)
class DbUrlCheck:
    ok: bool
    reason: str


def check_test_database_url(
    url: str,
    *,
    expected_host: str = "postgres_test",
    required_db_suffix: str = "_test",
    required_user: Optional[str] = None,
) -> DbUrlCheck:
    """Validate that a DB URL is *unambiguously* a test DB URL.

    We intentionally keep this strict: if it can't be proven safe, we reject it.
    """
    if not url:
        return DbUrlCheck(False, "url_empty")
    try:
        u = make_url(url)
    except Exception as e:
        return DbUrlCheck(False, f"url_parse_error:{type(e).__name__}")

    drivername = (u.drivername or "").lower()
    if not (drivername.startswith("postgresql") or drivername.startswith("postgres")):
        return DbUrlCheck(False, f"unsupported_driver:{drivername}")

    if not u.host:
        return DbUrlCheck(False, "missing_host")
    if u.host != expected_host:
        return DbUrlCheck(False, f"host_mismatch:{u.host}!= {expected_host}")

    if not u.database:
        return DbUrlCheck(False, "missing_database")
    if not u.database.endswith(required_db_suffix):
        return DbUrlCheck(False, f"database_not_test:{u.database}")

    if required_user is not None:
        if not u.username:
            return DbUrlCheck(False, "missing_username")
        if u.username != required_user:
            return DbUrlCheck(False, f"user_mismatch:{u.username}!= {required_user}")

    return DbUrlCheck(True, "ok")


