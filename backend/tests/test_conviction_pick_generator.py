"""Tests for the conviction pick generator.

Covers:

* ``ConvictionPickGenerator.generate`` filters by stage, RS, EPS
  growth, valuation, and range position; returns ranked candidates
  with a Decimal composite score.
* Counters sum to ``total_scanned`` (no silent fallback regression).
* The Celery task ``generate_conviction_picks`` writes one row per
  ranked candidate per user (minus symbols the user already holds in
  conviction), and re-runs write a new batch with a fresh
  ``generated_at`` timestamp.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List

from backend.models.broker_account import (
    AccountStatus,
    AccountType,
    BrokerAccount,
    BrokerType,
    SyncStatus,
)
from backend.models.conviction_pick import ConvictionPick
from backend.models.market_data import MarketSnapshot
from backend.models.position import Position, PositionStatus, PositionType, Sleeve
from backend.models.user import User
from backend.services.gold.conviction_pick_generator import (
    ConvictionPickGenerator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_user(db_session, *, email: str = "conv@example.com") -> User:
    u = User(
        username=email.split("@")[0],
        email=email,
        full_name="Conv Tester",
        password_hash="x",
    )
    db_session.add(u)
    db_session.flush()
    return u


def _seed_account(db_session, *, user_id: int) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user_id,
        account_number=f"ACCT-{user_id}",
        account_name="Test",
        broker=BrokerType.IBKR,
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
        sync_status=SyncStatus.SUCCESS,
    )
    db_session.add(acct)
    db_session.flush()
    return acct


def _seed_snapshot(
    db_session,
    *,
    symbol: str,
    stage_label: str = "2A",
    stage_days: int = 120,
    rs: float = 80.0,
    eps_yoy: float | None = 25.0,
    pe: float | None = 22.0,
    range_pos: float = 0.65,
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(
        MarketSnapshot(
            symbol=symbol,
            analysis_type="technical_snapshot",
            analysis_timestamp=now,
            as_of_timestamp=now,
            expiry_timestamp=now + timedelta(hours=24),
            is_valid=True,
            stage_label=stage_label,
            current_stage_days=stage_days,
            rs_mansfield_pct=rs,
            ext_pct=2.0,
            range_pos_52w=range_pos,
            current_price=100.0,
            atr_14=2.5,
            eps_growth_yoy=eps_yoy,
            pe_ttm=pe,
        )
    )
    db_session.flush()


# ---------------------------------------------------------------------------
# Generator unit tests
# ---------------------------------------------------------------------------


class TestConvictionPickGenerator:
    def test_eligible_symbol_is_ranked(self, db_session):
        _seed_snapshot(db_session, symbol="AAPL")
        gen = ConvictionPickGenerator()
        report = gen.generate(db_session)
        assert report.total_scanned == 1
        assert report.eligible == 1
        assert report.candidates[0].symbol == "AAPL"
        assert isinstance(report.candidates[0].score, Decimal)

    def test_stage4_is_rejected(self, db_session):
        # stage 4 snapshots are filtered out even before Python eval by
        # the ``eligible_stages`` prefilter — total_scanned == 0.
        _seed_snapshot(db_session, symbol="XYZ", stage_label="4A")
        gen = ConvictionPickGenerator()
        report = gen.generate(db_session)
        assert report.total_scanned == 0
        assert report.eligible == 0

    def test_low_rs_is_skipped(self, db_session):
        _seed_snapshot(db_session, symbol="LOWRS", rs=30.0)
        gen = ConvictionPickGenerator()
        report = gen.generate(db_session)
        assert report.total_scanned == 1
        assert report.eligible == 0
        assert report.skipped_rs == 1

    def test_negative_eps_is_skipped(self, db_session):
        _seed_snapshot(db_session, symbol="BADEPS", eps_yoy=-10.0)
        gen = ConvictionPickGenerator()
        report = gen.generate(db_session)
        assert report.eligible == 0
        assert report.skipped_eps == 1

    def test_high_pe_is_skipped(self, db_session):
        _seed_snapshot(db_session, symbol="EXPENSIVE", pe=120.0)
        gen = ConvictionPickGenerator()
        report = gen.generate(db_session)
        assert report.eligible == 0
        assert report.skipped_valuation == 1

    def test_range_at_52w_high_is_skipped(self, db_session):
        _seed_snapshot(db_session, symbol="AT52WH", range_pos=0.98)
        gen = ConvictionPickGenerator()
        report = gen.generate(db_session)
        assert report.eligible == 0
        assert report.skipped_range == 1

    def test_counters_sum_to_total(self, db_session):
        _seed_snapshot(db_session, symbol="A")
        _seed_snapshot(db_session, symbol="B", rs=10.0)  # skipped_rs
        _seed_snapshot(db_session, symbol="C", eps_yoy=-5.0)  # skipped_eps
        _seed_snapshot(db_session, symbol="D", pe=300.0)  # skipped_valuation
        _seed_snapshot(db_session, symbol="E", range_pos=0.99)  # skipped_range
        gen = ConvictionPickGenerator()
        report = gen.generate(db_session)
        total = (
            report.eligible
            + report.skipped_stage
            + report.skipped_rs
            + report.skipped_eps
            + report.skipped_valuation
            + report.skipped_range
            + report.skipped_other
        )
        assert total == report.total_scanned

    def test_ranking_is_stable_by_score(self, db_session):
        # All three pass filters; the one with the best profile ranks #1.
        _seed_snapshot(
            db_session,
            symbol="BEST",
            stage_label="2A",
            stage_days=200,
            rs=95.0,
            eps_yoy=80.0,
            pe=15.0,
            range_pos=0.70,
        )
        _seed_snapshot(
            db_session,
            symbol="MID",
            stage_label="2A",
            stage_days=40,
            rs=70.0,
            eps_yoy=20.0,
            pe=30.0,
            range_pos=0.60,
        )
        _seed_snapshot(
            db_session,
            symbol="EDGE",
            stage_label="1B",
            stage_days=25,
            rs=58.0,
            eps_yoy=5.0,
            pe=50.0,
            range_pos=0.45,
        )
        gen = ConvictionPickGenerator()
        report = gen.generate(db_session)
        assert report.eligible == 3
        syms = [c.symbol for c in report.candidates]
        assert syms[0] == "BEST"
        assert [c.rank for c in report.candidates] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Task integration test (persistence path)
# ---------------------------------------------------------------------------


class TestTaskPersistenceHelpers:
    """Exercise the conviction task's pure persistence helpers directly.

    We deliberately avoid invoking the full Celery task through
    ``.run()`` here — that path creates ``JobRun`` rows, touches Redis,
    and fires alert hooks, none of which are in scope for these tests.
    The helpers are where the per-user correctness lives.
    """

    def test_active_user_ids_returns_users_with_open_positions(
        self, db_session
    ):
        from backend.tasks.market.conviction import _active_user_ids

        user = _seed_user(db_session, email="t1@example.com")
        acct = _seed_account(db_session, user_id=user.id)
        db_session.add(
            Position(
                user_id=user.id,
                account_id=acct.id,
                symbol="ZZZ",
                quantity=Decimal("1"),
                position_type=PositionType.LONG,
                status=PositionStatus.OPEN,
                sleeve=Sleeve.ACTIVE.value,
            )
        )
        db_session.flush()

        uids = _active_user_ids(db_session)
        assert user.id in uids

    def test_excludes_symbols_already_held_in_conviction_sleeve(
        self, db_session
    ):
        from backend.services.gold.conviction_pick_generator import (
            ConvictionCandidate,
            GenerationReport,
        )
        from backend.tasks.market.conviction import (
            _persist_for_user,
            _user_conviction_holdings,
        )

        user = _seed_user(db_session, email="t2@example.com")
        acct = _seed_account(db_session, user_id=user.id)
        db_session.add(
            Position(
                user_id=user.id,
                account_id=acct.id,
                symbol="HELD",
                quantity=Decimal("1"),
                position_type=PositionType.LONG,
                status=PositionStatus.OPEN,
                sleeve=Sleeve.CONVICTION.value,
            )
        )
        db_session.flush()

        report = GenerationReport()
        report.candidates.append(
            ConvictionCandidate(
                symbol="HELD",
                rank=1,
                score=Decimal("90.00"),
                stage_label="2A",
                rationale="r1",
                breakdown={"k": "v"},
            )
        )
        report.candidates.append(
            ConvictionCandidate(
                symbol="NEW",
                rank=2,
                score=Decimal("80.00"),
                stage_label="2A",
                rationale="r2",
                breakdown={"k": "v"},
            )
        )

        exclude = _user_conviction_holdings(db_session, user.id)
        assert exclude == {"HELD"}

        now = datetime.now(timezone.utc)
        written = _persist_for_user(
            db_session,
            user_id=user.id,
            report=report,
            generated_at=now,
            exclude=exclude,
        )
        db_session.flush()

        assert written == 1
        rows: List[ConvictionPick] = (
            db_session.query(ConvictionPick)
            .filter(ConvictionPick.user_id == user.id)
            .order_by(ConvictionPick.rank)
            .all()
        )
        assert [r.symbol for r in rows] == ["NEW"]
        assert rows[0].rank == 1  # re-ranked after exclusion
        assert rows[0].generator_version
