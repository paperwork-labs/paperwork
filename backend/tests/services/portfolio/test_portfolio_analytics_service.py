"""Tests for the silver-layer portfolio analytics service.

Every test drives the real ``_compute_risk_metrics_core`` helper against
deterministic fixtures (``PortfolioSnapshot`` + ``MarketSnapshotHistory``)
so the regression beta / volatility / Sharpe / drawdown math is pinned to
known-answer references computed with NumPy.

Principle: no silent fallbacks. When coverage is insufficient, the helper
must return ``None`` — these tests assert that explicitly so future
regressions can't quietly re-introduce a synthetic ``1.0`` beta or ``15.0``
volatility default.
"""

from __future__ import annotations

import math
from datetime import datetime, time, timedelta, timezone
from typing import List

import numpy as np
import pytest

from backend.models.broker_account import AccountType, BrokerAccount, BrokerType
from backend.models.market_data import MarketSnapshotHistory
from backend.models.portfolio import PortfolioSnapshot
from backend.models.user import User
from backend.services.portfolio.portfolio_analytics_service import (
    MIN_DAYS_FOR_SHARPE,
    MIN_RETURNS_FOR_BETA,
    MIN_SNAPSHOTS_FOR_VOLATILITY,
    RISK_FREE_RATE,
    TRADING_DAYS_PER_YEAR,
    PortfolioAnalyticsService,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_user(session, *, username: str) -> User:
    user = session.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        email=f"{username}@example.test",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_account(session, *, user: User, account_number: str) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.IBKR,
        account_number=account_number,
        account_name=f"IBKR {account_number}",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    session.add(acct)
    session.commit()
    session.refresh(acct)
    return acct


def _seed_portfolio_series(
    session,
    account: BrokerAccount,
    *,
    start: datetime,
    values: List[float],
) -> None:
    for i, value in enumerate(values):
        snap = PortfolioSnapshot(
            account_id=account.id,
            snapshot_date=start + timedelta(days=i),
            total_value=value,
            total_cash=0.0,
            total_equity_value=value,
            unrealized_pnl=0.0,
        )
        session.add(snap)
    session.commit()


def _seed_benchmark_series(
    session,
    *,
    symbol: str,
    start: datetime,
    closes: List[float],
    analysis_type: str = "benchmark_price",
) -> None:
    for i, close in enumerate(closes):
        session.add(
            MarketSnapshotHistory(
                symbol=symbol,
                analysis_type=analysis_type,
                as_of_date=start + timedelta(days=i),
                current_price=close,
            )
        )
    session.commit()


def _seed_portfolio_series_intraday_utc(
    session,
    account: BrokerAccount,
    *,
    start: datetime,
    values: List[float],
) -> None:
    """``snapshot_date`` at 14:30 UTC; benchmark history remains midnight-only."""
    t_utc = time(14, 30, 0)
    for i, value in enumerate(values):
        d = (start + timedelta(days=i)).date()
        session.add(
            PortfolioSnapshot(
                account_id=account.id,
                snapshot_date=datetime.combine(d, t_utc),
                total_value=value,
                total_cash=0.0,
                total_equity_value=value,
                unrealized_pnl=0.0,
            )
        )
    session.commit()


def _values_from_returns(start_value: float, returns: List[float]) -> List[float]:
    values = [start_value]
    for r in returns:
        values.append(values[-1] * (1.0 + r))
    return values


def _recent_start(n_days: int) -> datetime:
    """Return a naive UTC datetime that is ``n_days`` in the past but well
    inside the service's default 252-day lookback. Avoids fixtures falling
    outside the query window when the test suite runs on different days.
    """
    today = datetime.now(timezone.utc).replace(tzinfo=None)
    # Pull start back by n_days plus a small safety buffer.
    return datetime(today.year, today.month, today.day) - timedelta(days=n_days + 1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_beta_regression_matches_known_fixture(db_session):
    """Regression beta must match NumPy's sample covariance / variance."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    user = _make_user(db_session, username="alice_beta")
    acct = _make_account(db_session, user=user, account_number="BETA-001")

    rng = np.random.default_rng(seed=42)
    n_returns = MIN_RETURNS_FOR_BETA + 30
    benchmark_returns = rng.normal(0.0005, 0.01, size=n_returns).tolist()
    # Portfolio = 1.3 * benchmark + idiosyncratic noise.
    idiosyncratic = rng.normal(0.0, 0.003, size=n_returns).tolist()
    portfolio_returns = [
        1.3 * b + e for b, e in zip(benchmark_returns, idiosyncratic)
    ]

    start = _recent_start(n_returns + 1)
    portfolio_values = _values_from_returns(100_000.0, portfolio_returns)
    benchmark_values = _values_from_returns(500.0, benchmark_returns)

    _seed_portfolio_series(db_session, acct, start=start, values=portfolio_values)
    _seed_benchmark_series(db_session, symbol="SPY", start=start, closes=benchmark_values)

    svc = PortfolioAnalyticsService()
    result = svc._compute_risk_metrics_core(db_session, [acct.id])

    expected_beta = float(
        np.cov(portfolio_returns, benchmark_returns, ddof=1)[0, 1]
        / np.var(benchmark_returns, ddof=1)
    )
    assert result.beta_portfolio_regression is not None
    assert result.beta_portfolio_regression == pytest.approx(expected_beta, abs=1e-3)
    assert result.benchmark_symbol == "SPY"
    assert result.benchmark_overlap_days == n_returns


def test_beta_regression_aligns_non_midnight_snapshot_dates(db_session):
    """14:30 UTC ``snapshot_date`` rows must key to the same calendar days
    as midnight ``as_of_date`` benchmark rows (non-empty overlap)."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    user = _make_user(db_session, username="alice_intra")
    acct = _make_account(db_session, user=user, account_number="INTRA-001")

    rng = np.random.default_rng(seed=99)
    n_returns = MIN_RETURNS_FOR_BETA + 8
    benchmark_returns = rng.normal(0.0004, 0.009, size=n_returns).tolist()
    idiosyncratic = rng.normal(0.0, 0.002, size=n_returns).tolist()
    portfolio_returns = [1.25 * b + e for b, e in zip(benchmark_returns, idiosyncratic)]

    start = _recent_start(n_returns + 1)
    portfolio_values = _values_from_returns(80_000.0, portfolio_returns)
    benchmark_values = _values_from_returns(480.0, benchmark_returns)

    _seed_portfolio_series_intraday_utc(db_session, acct, start=start, values=portfolio_values)
    _seed_benchmark_series(db_session, symbol="SPY", start=start, closes=benchmark_values)

    svc = PortfolioAnalyticsService()
    result = svc._compute_risk_metrics_core(db_session, [acct.id])

    expected_beta = float(
        np.cov(portfolio_returns, benchmark_returns, ddof=1)[0, 1]
        / np.var(benchmark_returns, ddof=1)
    )
    assert result.benchmark_overlap_days == n_returns
    assert result.beta_portfolio_regression is not None
    assert result.beta_portfolio_regression == pytest.approx(expected_beta, abs=1e-2)
    assert result.benchmark_symbol == "SPY"


def test_regression_uses_only_benchmark_price_rows_on_spy_date(db_session):
    """Contaminating ``technical_snapshot`` SPY history must not change beta."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    user = _make_user(db_session, username="alice_mixed_spy")
    acct = _make_account(db_session, user=user, account_number="MIXED-001")

    rng = np.random.default_rng(seed=3)
    n_returns = MIN_RETURNS_FOR_BETA + 6
    benchmark_returns = rng.normal(0.0, 0.008, size=n_returns).tolist()
    portfolio_returns = [1.1 * b for b in benchmark_returns]

    start = _recent_start(n_returns + 1)
    portfolio_values = _values_from_returns(70_000.0, portfolio_returns)
    benchmark_values = _values_from_returns(100.0, benchmark_returns)

    _seed_portfolio_series(db_session, acct, start=start, values=portfolio_values)
    _seed_benchmark_series(
        db_session, symbol="SPY", start=start, closes=benchmark_values, analysis_type="benchmark_price"
    )
    for i, _ in enumerate(benchmark_values):
        db_session.add(
            MarketSnapshotHistory(
                symbol="SPY",
                analysis_type="technical_snapshot",
                as_of_date=start + timedelta(days=i),
                current_price=999.0,
            )
        )
    db_session.commit()

    svc = PortfolioAnalyticsService()
    result = svc._compute_risk_metrics_core(db_session, [acct.id])

    expected_beta = 1.1
    assert result.beta_portfolio_regression is not None
    assert result.beta_portfolio_regression == pytest.approx(expected_beta, abs=0.02)
    assert result.benchmark_symbol == "SPY"


def test_beta_falls_back_to_gspc_when_spy_absent(db_session):
    """When SPY has no coverage, ``^GSPC`` is the fallback benchmark."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    user = _make_user(db_session, username="alice_fallback")
    acct = _make_account(db_session, user=user, account_number="FALLBACK-001")

    rng = np.random.default_rng(seed=7)
    n_returns = MIN_RETURNS_FOR_BETA + 10
    benchmark_returns = rng.normal(0.0, 0.01, size=n_returns).tolist()
    portfolio_returns = [0.8 * b for b in benchmark_returns]

    start = _recent_start(n_returns + 1)
    _seed_portfolio_series(
        db_session, acct, start=start,
        values=_values_from_returns(50_000.0, portfolio_returns),
    )
    _seed_benchmark_series(
        db_session, symbol="^GSPC", start=start,
        closes=_values_from_returns(4000.0, benchmark_returns),
    )

    svc = PortfolioAnalyticsService()
    result = svc._compute_risk_metrics_core(db_session, [acct.id])

    assert result.beta_portfolio_regression is not None
    assert result.beta_portfolio_regression == pytest.approx(0.8, abs=0.01)
    assert result.benchmark_symbol == "^GSPC"


def test_volatility_annualization_matches_daily_std_times_sqrt_252(db_session):
    """Annualized volatility = daily stdev * sqrt(252) * 100 (percent)."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    user = _make_user(db_session, username="alice_vol")
    acct = _make_account(db_session, user=user, account_number="VOL-001")

    rng = np.random.default_rng(seed=123)
    n = 60
    returns = rng.normal(0.0, 0.012, size=n).tolist()
    start = _recent_start(n + 1)
    _seed_portfolio_series(
        db_session, acct, start=start,
        values=_values_from_returns(100_000.0, returns),
    )

    svc = PortfolioAnalyticsService()
    result = svc._compute_risk_metrics_core(db_session, [acct.id])

    daily_std = float(np.std(returns, ddof=1))
    expected_vol = round(daily_std * math.sqrt(TRADING_DAYS_PER_YEAR) * 100, 2)
    assert result.volatility == pytest.approx(expected_vol, abs=0.05)


def test_sharpe_returns_none_below_90_days(db_session):
    """Sharpe must fail closed below the MIN_DAYS_FOR_SHARPE threshold."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    user = _make_user(db_session, username="alice_sharpe_short")
    acct = _make_account(db_session, user=user, account_number="SHARPE-SHORT")

    # Enough for volatility, but short of the Sharpe threshold.
    n = MIN_DAYS_FOR_SHARPE - 10
    assert n >= MIN_SNAPSHOTS_FOR_VOLATILITY
    rng = np.random.default_rng(seed=5)
    returns = rng.normal(0.001, 0.01, size=n).tolist()
    start = _recent_start(n + 1)
    _seed_portfolio_series(
        db_session, acct, start=start,
        values=_values_from_returns(100_000.0, returns),
    )

    svc = PortfolioAnalyticsService()
    result = svc._compute_risk_metrics_core(db_session, [acct.id])

    assert result.volatility is not None  # enough for volatility
    assert result.sharpe_ratio is None  # but not for Sharpe


def test_sharpe_formula_matches_reference(db_session):
    """When ≥90d history exists, Sharpe = (μ·252 − r_f) / (σ·√252)."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    user = _make_user(db_session, username="alice_sharpe_long")
    acct = _make_account(db_session, user=user, account_number="SHARPE-LONG")

    rng = np.random.default_rng(seed=9)
    n = MIN_DAYS_FOR_SHARPE + 20
    returns = rng.normal(0.0008, 0.011, size=n).tolist()
    start = _recent_start(n + 1)
    _seed_portfolio_series(
        db_session, acct, start=start,
        values=_values_from_returns(100_000.0, returns),
    )

    svc = PortfolioAnalyticsService()
    result = svc._compute_risk_metrics_core(db_session, [acct.id])

    mean_r = float(np.mean(returns))
    daily_std = float(np.std(returns, ddof=1))
    expected_sharpe = (
        (mean_r * TRADING_DAYS_PER_YEAR - RISK_FREE_RATE)
        / (daily_std * math.sqrt(TRADING_DAYS_PER_YEAR))
    )
    assert result.sharpe_ratio == pytest.approx(expected_sharpe, abs=0.01)


def test_beta_returns_none_when_benchmark_coverage_insufficient(db_session):
    """With < MIN_RETURNS_FOR_BETA aligned SPY rows, beta must be ``None``."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    user = _make_user(db_session, username="alice_short_bench")
    acct = _make_account(db_session, user=user, account_number="SHORT-BENCH-001")

    rng = np.random.default_rng(seed=1)
    portfolio_returns = rng.normal(0.0, 0.01, size=60).tolist()
    start = _recent_start(61)
    _seed_portfolio_series(
        db_session, acct, start=start,
        values=_values_from_returns(100_000.0, portfolio_returns),
    )
    # Only 5 SPY rows in the window — well under MIN_RETURNS_FOR_BETA.
    _seed_benchmark_series(
        db_session, symbol="SPY", start=start, closes=[500.0, 501.0, 499.0, 502.0, 503.0],
    )

    svc = PortfolioAnalyticsService()
    result = svc._compute_risk_metrics_core(db_session, [acct.id])

    assert result.beta_portfolio_regression is None
    assert result.benchmark_symbol is None


def test_max_drawdown_matches_peak_to_trough(db_session):
    """Drawdown = (trough - peak) / peak, always <= 0."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    user = _make_user(db_session, username="alice_dd")
    acct = _make_account(db_session, user=user, account_number="DD-001")

    # Hand-crafted series: climb to 120, crash to 60 (-50% peak-to-trough),
    # recover to 90. Pad with flats so we exceed MIN_SNAPSHOTS_FOR_VOLATILITY.
    values = (
        [100.0] * 5
        + list(range(100, 121, 5))
        + [120.0, 110.0, 100.0, 90.0, 80.0, 70.0, 60.0]
        + [65.0, 75.0, 85.0, 90.0]
        + [90.0] * 5
    )
    assert len(values) >= MIN_SNAPSHOTS_FOR_VOLATILITY
    start = _recent_start(len(values) + 1)
    _seed_portfolio_series(db_session, acct, start=start, values=values)

    svc = PortfolioAnalyticsService()
    result = svc._compute_risk_metrics_core(db_session, [acct.id])

    assert result.max_drawdown is not None
    # Peak 120 -> trough 60 -> -50%. Expressed as percent.
    assert result.max_drawdown == pytest.approx(-50.0, abs=0.1)


def test_user_id_scoping_ignores_other_tenant(db_session):
    """User B's snapshots must not leak into User A's metrics."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    user_a = _make_user(db_session, username="tenant_a")
    user_b = _make_user(db_session, username="tenant_b")
    acct_a = _make_account(db_session, user=user_a, account_number="A-001")
    acct_b = _make_account(db_session, user=user_b, account_number="B-001")

    start = _recent_start(41)
    rng = np.random.default_rng(seed=42)
    noisy = rng.normal(0.0, 0.02, size=40).tolist()
    _seed_portfolio_series(
        db_session, acct_b, start=start,
        values=_values_from_returns(50_000.0, noisy),
    )
    # User A has a perfectly flat 100k portfolio.
    _seed_portfolio_series(db_session, acct_a, start=start, values=[100_000.0] * 40)

    svc = PortfolioAnalyticsService()
    # Only A's account is passed; B's rows must not influence vol.
    result_a = svc._compute_risk_metrics_core(db_session, [acct_a.id])
    # Flat series => zero stdev => vol falls through as ``None`` (guard
    # clause: we only publish a number when daily_vol > 0).
    assert result_a.volatility is None
    assert result_a.sharpe_ratio is None

    # Sanity: the public shim resolves B's accounts for B and ignores A.
    api_b = svc.compute_risk_metrics(db_session, user_b.id)
    assert api_b["volatility"] is not None


def test_no_silent_fallback_on_zero_coverage(db_session):
    """Empty accounts => every forward-looking field ``None``."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    user = _make_user(db_session, username="alice_empty")

    svc = PortfolioAnalyticsService()
    result = svc.compute_risk_metrics(db_session, user.id)

    assert result["beta"] is None
    assert result["beta_portfolio_regression"] is None
    assert result["beta_weighted_snapshot"] is None
    assert result["volatility"] is None
    assert result["sharpe_ratio"] is None
    assert result["max_drawdown"] is None
    assert result["concentration_label"] == "N/A"


def test_user_id_required_positional():
    """D88 contract: no default ``user_id=1`` on any public method."""
    import inspect

    svc = PortfolioAnalyticsService()
    for name in ("compute_risk_metrics", "compute_twr", "compute_sector_attribution"):
        sig = inspect.signature(getattr(svc, name))
        assert "user_id" in sig.parameters, f"{name} missing user_id parameter"
        assert sig.parameters["user_id"].default is inspect.Parameter.empty, (
            f"{name}.user_id must be required (no default) — D88 multi-tenancy"
        )
