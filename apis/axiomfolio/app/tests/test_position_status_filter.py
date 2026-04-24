"""Regression tests for Position.status enum filter usage.

The Postgres ``positionstatus`` enum stores uppercase values (``OPEN``, ``CLOSED``,
``EXPIRED``). Comparing with the lowercase string literal ``"open"`` produced
``psycopg2.errors.InvalidTextRepresentation: invalid input value for enum
positionstatus: "open"`` and crashed the exit_cascade step of the nightly
pipeline (every nightly run finished ``partial`` rather than ``success``).

These tests assert that the SQL emitted by Position.status filters always uses
the enum member, not a raw lowercase string.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.position import Position, PositionStatus


def _compiled_sql(stmt) -> str:
    return str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_position_status_open_filter_emits_uppercase_enum() -> None:
    """Filtering by PositionStatus.OPEN must emit 'OPEN', not 'open'."""
    stmt = select(Position).where(Position.status == PositionStatus.OPEN)
    sql = _compiled_sql(stmt)
    assert "'OPEN'" in sql, sql
    assert "'open'" not in sql, sql


def test_position_status_closed_filter_emits_uppercase_enum() -> None:
    stmt = select(Position).where(Position.status == PositionStatus.CLOSED)
    sql = _compiled_sql(stmt)
    assert "'CLOSED'" in sql, sql
    assert "'closed'" not in sql, sql


def test_position_status_enum_member_names_are_uppercase() -> None:
    """Sanity guard: if anyone renames members to lowercase, this fails loudly."""
    assert PositionStatus.OPEN.name == "OPEN"
    assert PositionStatus.CLOSED.name == "CLOSED"
    assert PositionStatus.EXPIRED.name == "EXPIRED"
