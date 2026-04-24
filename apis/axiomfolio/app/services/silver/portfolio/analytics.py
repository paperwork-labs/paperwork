#!/usr/bin/env python3
"""
Portfolio Analytics Service - Snowball Analytics Style
Provides comprehensive portfolio analysis, performance metrics, and insights.

Silver-layer portfolio risk metrics:
- Real beta / volatility / Sharpe / max drawdown from ``PortfolioSnapshot`` and
  ``MarketSnapshotHistory``. No hardcoded 1.0 beta, 15.0 volatility, or
  ``min(unrealized_pnl_pct)`` drawdown.
- Fail-closed: insufficient coverage returns ``None`` for the affected
  field, never a synthetic "1.0". See ``.cursor/rules/no-silent-fallback.mdc``.
- Multi-tenancy: every method requires ``user_id`` positionally (no
  ``user_id=1`` defaults) — D88.

Medallion layer: silver. See docs/ARCHITECTURE.md and D127.

medallion: silver
"""

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

try:
    from app.models.broker_account import BrokerAccount
    from app.models.market_data import MarketSnapshot, MarketSnapshotHistory
    from app.models.portfolio import PortfolioSnapshot
    from app.models.position import Position
    from app.models.tax_lot import TaxLot  # noqa: F401 (legacy import surface)
    from app.models.transaction import Transaction  # noqa: F401
    from app.services.clients.ibkr_client import ibkr_client
    from app.services.clients.ibkr_flexquery_client import flexquery_client
except ImportError:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration constants — fail-closed analytics defaults.
# ---------------------------------------------------------------------------

# Annualized risk-free rate used for Sharpe. Matches value used elsewhere in
# the codebase (e.g. ``compute_risk_metrics`` previously). Sourced from the
# FRED 3-month T-bill; updated manually when rates shift materially.
RISK_FREE_RATE: float = 0.045

# Trading days per year for annualization.
TRADING_DAYS_PER_YEAR: int = 252

# Minimum daily PortfolioSnapshot rows required before we publish volatility.
# Below this, the sample mean/stdev is noise — return ``None`` instead.
MIN_SNAPSHOTS_FOR_VOLATILITY: int = 20

# Minimum aligned daily return pairs required before we publish a regression
# beta. Enforced against intersection of portfolio + benchmark dates.
MIN_RETURNS_FOR_BETA: int = 20

# Minimum portfolio history length (in days) before we publish Sharpe. Sharpe
# below 90 days is notoriously unstable — fail closed.
MIN_DAYS_FOR_SHARPE: int = 90

# Minimum fraction of portfolio market value covered by ``MarketSnapshot.beta``
# before we publish the weighted-snapshot beta. Below this threshold the
# number is unrepresentative of the portfolio and we return ``None``.
MIN_BETA_COVERAGE_WEIGHT: float = 0.5

# Default lookback when computing risk metrics from the daily ledger.
DEFAULT_RISK_LOOKBACK_DAYS: int = 252

# Primary + fallback benchmark symbols for regression beta.
BENCHMARK_SYMBOL_PRIMARY: str = "SPY"
BENCHMARK_SYMBOL_FALLBACK: str = "^GSPC"
# ``market_benchmark_spy_history_backfill`` writes only this ``analysis_type``;
# regression must read the same series (not ``technical_snapshot`` / combined rows).
BENCHMARK_ANALYSIS_TYPE: str = "benchmark_price"

# Stream chunk size for per-row loops that may exceed 1k rows.
_STREAM_CHUNK_SIZE: int = 200


def _naive_midnight_date_key(ts: date | datetime) -> datetime:
    """Normalize a ``snapshot_date`` / ``as_of_date`` to a naive
    ``YYYY-MM-DD 00:00:00`` key.

    ``PortfolioSnapshot.snapshot_date`` is often a wall-clock write time, while
    ``MarketSnapshotHistory.as_of_date`` is midnight-aligned. Regression beta
    keys both sides the same way so aligned days are not empty."""
    return datetime(ts.year, ts.month, ts.day)


@dataclass
class PortfolioMetrics:
    """Portfolio performance and risk metrics.

    Risk fields are ``Optional[float]`` because we fail closed on
    insufficient coverage rather than return synthetic values that
    hide degradation (see ``.cursor/rules/no-silent-fallback.mdc``).
    """

    total_value: float
    total_cost_basis: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float

    # Performance Metrics
    ytd_return: float
    total_return: float
    annualized_return: float

    # Risk Metrics — ``None`` when coverage is insufficient
    volatility: Optional[float]
    sharpe_ratio: Optional[float]
    max_drawdown: Optional[float]
    beta: Optional[float]

    # Asset Allocation
    equity_allocation: float
    options_allocation: float
    cash_allocation: float

    # Tax Information
    long_term_positions: int
    short_term_positions: int
    unrealized_lt_gains: float
    unrealized_st_gains: float
    tax_loss_harvest_opportunities: float


@dataclass
class RiskMetricsResult:
    """Structured output of :func:`PortfolioAnalyticsService._compute_risk_metrics_core`.

    Any field may be ``None`` when its supporting data set is empty or below
    the coverage threshold — consumers must surface "insufficient coverage"
    rather than pretending the metric exists.
    """

    # Regression beta: ``Cov(R_p, R_b) / Var(R_b)`` over the intersection of
    # portfolio daily returns and benchmark (``SPY`` / ``^GSPC``) daily
    # returns. ``None`` when < ``MIN_RETURNS_FOR_BETA`` aligned rows.
    beta_portfolio_regression: Optional[float]

    # Weighted-snapshot beta: Σ(w_i · MarketSnapshot.beta_i) / Σ(w_i with
    # non-null beta). ``None`` when coverage < ``MIN_BETA_COVERAGE_WEIGHT``.
    beta_weighted_snapshot: Optional[float]

    # Annualized volatility of ``PortfolioSnapshot.total_value`` daily returns,
    # expressed as a percent (e.g. 18.5 == 18.5%). ``None`` when
    # < ``MIN_SNAPSHOTS_FOR_VOLATILITY`` usable rows.
    volatility: Optional[float]

    # Annualized Sharpe = ``(μ·252 − r_f) / (σ·√252)``. ``None`` when
    # history < ``MIN_DAYS_FOR_SHARPE`` days or volatility is ``None``.
    sharpe_ratio: Optional[float]

    # Peak-to-trough drawdown as a percent (always ≤ 0). ``None`` when
    # < ``MIN_SNAPSHOTS_FOR_VOLATILITY`` rows available.
    max_drawdown: Optional[float]

    # Concentration diagnostics (always defined when at least one position
    # exists; zero otherwise). HHI is scaled to ``[0, 10000]``.
    hhi: float
    top5_weight: float
    concentration_label: str

    # Benchmark symbol actually used for regression beta, or ``None`` when
    # benchmark coverage was insufficient.
    benchmark_symbol: Optional[str]

    # Number of aligned daily return pairs used for regression beta.
    benchmark_overlap_days: int

    # Number of PortfolioSnapshot rows consumed.
    portfolio_days: int

    def preferred_beta(self) -> Optional[float]:
        """Prefer the regression beta (portfolio-vs-SPY); fall back to the
        weighted-snapshot method when regression coverage is insufficient."""
        if self.beta_portfolio_regression is not None:
            return self.beta_portfolio_regression
        return self.beta_weighted_snapshot

    def to_api_dict(self) -> Dict[str, Any]:
        """Serialize for the ``/risk-metrics`` API response."""
        return {
            "beta": self.preferred_beta(),
            "beta_portfolio_regression": self.beta_portfolio_regression,
            "beta_weighted_snapshot": self.beta_weighted_snapshot,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "hhi": round(self.hhi, 0) if self.hhi else 0,
            "top5_weight": self.top5_weight,
            "concentration_label": self.concentration_label,
            "benchmark_symbol": self.benchmark_symbol,
            "benchmark_overlap_days": self.benchmark_overlap_days,
            "portfolio_days": self.portfolio_days,
        }


@dataclass
class TaxOptimizationOpportunity:
    """Tax optimization opportunity."""

    symbol: str
    opportunity_type: str  # "tax_loss_harvest", "ltcg_realization", "wash_sale_warning"
    market_value: float
    unrealized_pnl: float
    days_held: int
    estimated_tax_impact: float
    recommendation: str
    confidence: float


class PortfolioAnalyticsService:
    """
    Portfolio Analytics Service - Professional grade portfolio analysis.

    Provides Snowball Analytics-style functionality:
    - Portfolio performance & risk metrics
    - Tax optimization opportunities
    - Asset allocation analysis
    - Performance attribution
    - Risk monitoring
    """

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session

    async def get_portfolio_analytics(
        self,
        account_id: str,
        user_id: int,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive portfolio analytics for account.

        Args:
            account_id: Broker account number (external identifier).
            user_id: Owning user id — required, multi-tenancy scope. No
                default per D88.
            db: Optional DB session. When provided, risk metrics are computed
                from the daily ledger. When omitted, risk fields surface as
                ``None`` (caller can render "insufficient coverage").
        """
        try:
            logger.info("generating portfolio analytics for %s (user=%d)", account_id, user_id)

            positions = await ibkr_client.get_positions(account_id)
            tax_lots = await flexquery_client.get_official_tax_lots(account_id)

            account_ids: List[int] = []
            if db is not None:
                account_ids = [
                    row.id
                    for row in db.query(BrokerAccount.id).filter(
                        BrokerAccount.user_id == user_id,
                        BrokerAccount.account_number == account_id,
                    ).all()
                ]

            metrics = await self._calculate_portfolio_metrics(
                positions, tax_lots, db=db, account_ids=account_ids
            )

            tax_opportunities = await self._find_tax_opportunities(tax_lots)
            allocation = self._calculate_asset_allocation(positions)
            performance = await self._calculate_performance_attribution(
                positions, tax_lots
            )

            return {
                "account_id": account_id,
                "as_of_date": datetime.now().isoformat(),
                "portfolio_metrics": metrics.__dict__,
                "tax_opportunities": [opp.__dict__ for opp in tax_opportunities],
                "asset_allocation": allocation,
                "performance_attribution": performance,
                "positions_count": len(positions),
                "tax_lots_count": len(tax_lots),
            }

        except Exception as e:
            # Surface the error rather than swallow it — preserves caller's
            # ability to distinguish "no data" from "upstream failure".
            logger.exception("portfolio analytics failed for %s (user=%d)", account_id, user_id)
            return {"error": str(e)}

    async def _calculate_portfolio_metrics(
        self,
        positions: List[Dict],
        tax_lots: List[Dict],
        *,
        db: Optional[Session] = None,
        account_ids: Optional[Sequence[int]] = None,
    ) -> PortfolioMetrics:
        """Calculate comprehensive portfolio metrics."""

        # Basic totals
        total_value = sum(pos.get("market_value", 0) for pos in positions)
        total_cost_basis = sum(lot.get("cost_basis", 0) for lot in tax_lots)
        total_unrealized_pnl = total_value - total_cost_basis
        total_unrealized_pnl_pct = (
            (total_unrealized_pnl / total_cost_basis * 100)
            if total_cost_basis > 0
            else 0
        )

        # Asset allocation
        equity_value = sum(
            pos.get("market_value", 0)
            for pos in positions
            if pos.get("contract_type") == "STK"
        )
        options_value = sum(
            pos.get("market_value", 0)
            for pos in positions
            if pos.get("contract_type") == "OPT"
        )

        equity_allocation = (equity_value / total_value * 100) if total_value > 0 else 0
        options_allocation = (
            (options_value / total_value * 100) if total_value > 0 else 0
        )
        cash_allocation = max(0, 100 - equity_allocation - options_allocation)

        # Tax lot analysis
        long_term_positions = len(
            [lot for lot in tax_lots if lot.get("is_long_term", False)]
        )
        short_term_positions = len(tax_lots) - long_term_positions

        unrealized_lt_gains = sum(
            lot.get("unrealized_pnl", 0)
            for lot in tax_lots
            if lot.get("is_long_term", False) and lot.get("unrealized_pnl", 0) > 0
        )
        unrealized_st_gains = sum(
            lot.get("unrealized_pnl", 0)
            for lot in tax_lots
            if not lot.get("is_long_term", False) and lot.get("unrealized_pnl", 0) > 0
        )

        # Calculate tax loss harvest opportunities
        tax_loss_harvest_opportunities = sum(
            abs(lot.get("unrealized_pnl", 0))
            for lot in tax_lots
            if lot.get("unrealized_pnl", 0) < -1000
        )  # $1000+ losses

        # Performance metrics (simplified — would need historical data for
        # precise calculation; kept as-is until dedicated TWR work lands).
        ytd_return = total_unrealized_pnl_pct
        total_return = total_unrealized_pnl_pct
        annualized_return = total_return / max(1, len(tax_lots) / 252)

        # Risk metrics — compute from the daily ledger if a DB session was
        # supplied and the account resolves; otherwise fail closed.
        volatility: Optional[float] = None
        sharpe_ratio: Optional[float] = None
        max_drawdown: Optional[float] = None
        beta: Optional[float] = None
        if db is not None and account_ids:
            risk = self._compute_risk_metrics_core(db, list(account_ids))
            volatility = risk.volatility
            sharpe_ratio = risk.sharpe_ratio
            max_drawdown = risk.max_drawdown
            beta = risk.preferred_beta()

        return PortfolioMetrics(
            total_value=total_value,
            total_cost_basis=total_cost_basis,
            total_unrealized_pnl=total_unrealized_pnl,
            total_unrealized_pnl_pct=total_unrealized_pnl_pct,
            ytd_return=ytd_return,
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            beta=beta,
            equity_allocation=equity_allocation,
            options_allocation=options_allocation,
            cash_allocation=cash_allocation,
            long_term_positions=long_term_positions,
            short_term_positions=short_term_positions,
            unrealized_lt_gains=unrealized_lt_gains,
            unrealized_st_gains=unrealized_st_gains,
            tax_loss_harvest_opportunities=tax_loss_harvest_opportunities,
        )

    async def _find_tax_opportunities(
        self, tax_lots: List[Dict]
    ) -> List[TaxOptimizationOpportunity]:
        """Find tax optimization opportunities."""
        opportunities = []

        for lot in tax_lots:
            symbol = lot.get("symbol", "")
            unrealized_pnl = lot.get("unrealized_pnl", 0)
            days_held = lot.get("days_held", 0)
            current_value = lot.get("market_value", 0)

            # Tax loss harvesting opportunity
            if unrealized_pnl < -1000:  # $1000+ loss
                estimated_tax_savings = (
                    abs(unrealized_pnl) * 0.24
                )  # Assume 24% tax rate

                opportunities.append(
                    TaxOptimizationOpportunity(
                        symbol=symbol,
                        opportunity_type="tax_loss_harvest",
                        market_value=current_value,
                        unrealized_pnl=unrealized_pnl,
                        days_held=days_held,
                        estimated_tax_impact=estimated_tax_savings,
                        recommendation=f"Consider harvesting ${abs(unrealized_pnl):,.0f} loss for tax savings",
                        confidence=0.8,
                    )
                )

            # Long-term capital gains opportunity (approaching 1 year)
            elif 300 <= days_held <= 365 and unrealized_pnl > 0:
                opportunities.append(
                    TaxOptimizationOpportunity(
                        symbol=symbol,
                        opportunity_type="ltcg_opportunity",
                        market_value=current_value,
                        unrealized_pnl=unrealized_pnl,
                        days_held=days_held,
                        estimated_tax_impact=0,
                        recommendation=f"Wait {365 - days_held} days for long-term capital gains treatment",
                        confidence=0.9,
                    )
                )

            # Wash sale warning (if we had transaction history)
            # This would require checking for recent sales of the same security

        return opportunities

    def _calculate_asset_allocation(self, positions: List[Dict]) -> Dict[str, Any]:
        """Calculate detailed asset allocation."""
        total_value = sum(pos.get("market_value", 0) for pos in positions)

        if total_value == 0:
            return {"error": "No positions found"}

        # By asset class
        by_asset_class = {}
        for pos in positions:
            asset_class = pos.get("contract_type", "UNKNOWN")
            value = pos.get("market_value", 0)

            if asset_class not in by_asset_class:
                by_asset_class[asset_class] = {"value": 0, "percentage": 0}

            by_asset_class[asset_class]["value"] += value

        # Calculate percentages
        for asset_class in by_asset_class:
            by_asset_class[asset_class]["percentage"] = (
                by_asset_class[asset_class]["value"] / total_value * 100
            )

        # Top holdings
        top_holdings = sorted(
            [
                {
                    "symbol": pos.get("symbol"),
                    "value": pos.get("market_value", 0),
                    "percentage": pos.get("market_value", 0) / total_value * 100,
                }
                for pos in positions
            ],
            key=lambda x: x["value"],
            reverse=True,
        )[:10]

        return {
            "total_value": total_value,
            "by_asset_class": by_asset_class,
            "top_holdings": top_holdings,
            "concentration_risk": max(
                [h["percentage"] for h in top_holdings], default=0
            ),
        }

    async def _calculate_performance_attribution(
        self, positions: List[Dict], tax_lots: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate performance attribution by various factors."""

        # By security
        by_security = {}
        for lot in tax_lots:
            symbol = lot.get("symbol", "")
            unrealized_pnl = lot.get("unrealized_pnl", 0)

            if symbol not in by_security:
                by_security[symbol] = 0
            by_security[symbol] += unrealized_pnl

        # Top contributors and detractors
        sorted_performance = sorted(
            by_security.items(), key=lambda x: x[1], reverse=True
        )
        top_contributors = sorted_performance[:5]
        top_detractors = sorted_performance[-5:]

        return {
            "by_security": by_security,
            "top_contributors": [{"symbol": s, "pnl": p} for s, p in top_contributors],
            "top_detractors": [{"symbol": s, "pnl": p} for s, p in top_detractors],
            "total_securities": len(by_security),
        }


    # ------------------------------------------------------------------
    # Silver-layer risk math
    #
    # The private helper ``_compute_risk_metrics_core`` is the single
    # source of truth for beta / volatility / Sharpe / drawdown. Both
    # the public ``compute_risk_metrics`` route helper and the async
    # ``_calculate_portfolio_metrics`` dispatch through it so the two
    # surfaces can never drift apart again.
    # ------------------------------------------------------------------

    def _load_portfolio_snapshots(
        self,
        db: Session,
        account_ids: Sequence[int],
        *,
        lookback_days: int = DEFAULT_RISK_LOOKBACK_DAYS,
    ) -> List[PortfolioSnapshot]:
        """Return the last ``lookback_days`` daily portfolio snapshots in
        chronological order. Uses ``yield_per`` for large result sets so
        we do not spike memory on long histories."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        query = (
            db.query(PortfolioSnapshot)
            .filter(
                PortfolioSnapshot.account_id.in_(account_ids),
                PortfolioSnapshot.snapshot_date >= cutoff.date(),
            )
            .order_by(PortfolioSnapshot.snapshot_date.asc())
            .yield_per(_STREAM_CHUNK_SIZE)
        )
        return list(query)

    def _aggregate_portfolio_daily_totals(
        self,
        snapshots: Sequence[PortfolioSnapshot],
    ) -> List[Tuple[datetime, float]]:
        """Collapse per-account snapshots into a single portfolio-level time
        series. Multiple accounts on the same date are summed."""
        by_date: Dict[datetime, float] = {}
        for snap in snapshots:
            value = float(snap.total_value or 0)
            if value <= 0:
                continue
            key = _naive_midnight_date_key(snap.snapshot_date)
            by_date[key] = by_date.get(key, 0.0) + value
        return sorted(by_date.items(), key=lambda kv: kv[0])

    @staticmethod
    def _daily_returns(values: Sequence[float]) -> List[float]:
        """Simple arithmetic daily returns. Skips transitions where the
        prior value is non-positive (which would blow up division)."""
        out: List[float] = []
        for i in range(1, len(values)):
            prev = values[i - 1]
            if prev > 0:
                out.append((values[i] - prev) / prev)
        return out

    @staticmethod
    def _max_drawdown_pct(values: Sequence[float]) -> Optional[float]:
        """Peak-to-trough drawdown as a percent (always ≤ 0). Returns
        ``None`` when the series is too short to be meaningful."""
        if len(values) < MIN_SNAPSHOTS_FOR_VOLATILITY:
            return None
        peak = values[0]
        worst = 0.0
        for v in values:
            if v > peak:
                peak = v
            if peak > 0:
                dd = (v - peak) / peak
                if dd < worst:
                    worst = dd
        return round(worst * 100, 2)

    def _load_benchmark_daily_closes(
        self,
        db: Session,
        symbol: str,
        start_date: datetime,
    ) -> Dict[datetime, float]:
        """Load daily ``current_price`` closes from ``MarketSnapshotHistory``
        for ``symbol`` since ``start_date``, restricted to benchmark rows only.

        Keyed by :func:`_naive_midnight_date_key` for alignment with aggregated
        portfolio series."""
        rows = (
            db.query(MarketSnapshotHistory)
            .filter(
                MarketSnapshotHistory.symbol == symbol,
                MarketSnapshotHistory.analysis_type == BENCHMARK_ANALYSIS_TYPE,
                MarketSnapshotHistory.as_of_date >= start_date,
                MarketSnapshotHistory.current_price.isnot(None),
            )
            .order_by(
                MarketSnapshotHistory.as_of_date.asc(),
                MarketSnapshotHistory.analysis_timestamp.desc(),
                MarketSnapshotHistory.id.desc(),
            )
            .yield_per(_STREAM_CHUNK_SIZE)
        )
        # Last assignment wins per ``key``; ``as_of_date`` ascending plus later
        # same-calendar stamps overwrite earlier rows for that day.
        closes: Dict[datetime, float] = {}
        for row in rows:
            as_of = row.as_of_date
            if hasattr(as_of, "date"):
                key = _naive_midnight_date_key(as_of)
            else:
                key = as_of  # pragma: no cover (defensive)
            price = float(row.current_price)
            if price > 0:
                closes[key] = price
        return closes

    def _resolve_benchmark(
        self,
        db: Session,
        start_date: datetime,
    ) -> Tuple[Optional[str], Dict[datetime, float]]:
        """Return the first benchmark symbol with enough history, or
        ``(None, {})`` when neither SPY nor ^GSPC has coverage."""
        for symbol in (BENCHMARK_SYMBOL_PRIMARY, BENCHMARK_SYMBOL_FALLBACK):
            closes = self._load_benchmark_daily_closes(db, symbol, start_date)
            if len(closes) >= MIN_RETURNS_FOR_BETA + 1:
                return symbol, closes
        return None, {}

    def _compute_regression_beta(
        self,
        portfolio_daily: Sequence[Tuple[datetime, float]],
        benchmark_closes: Dict[datetime, float],
    ) -> Tuple[Optional[float], int]:
        """Return ``(beta, n_aligned_returns)``. Beta is the sample
        covariance of portfolio and benchmark daily returns divided by
        the sample variance of benchmark returns (``ddof=1`` for both).
        """
        if not portfolio_daily or not benchmark_closes:
            return None, 0
        aligned_p: List[float] = []
        aligned_b: List[float] = []
        for i in range(1, len(portfolio_daily)):
            prev_d, prev_v = portfolio_daily[i - 1]
            curr_d, curr_v = portfolio_daily[i]
            if prev_v <= 0:
                continue
            prev_b = benchmark_closes.get(prev_d)
            curr_b = benchmark_closes.get(curr_d)
            if prev_b is None or curr_b is None or prev_b <= 0:
                continue
            aligned_p.append((curr_v - prev_v) / prev_v)
            aligned_b.append((curr_b - prev_b) / prev_b)
        n = len(aligned_p)
        if n < MIN_RETURNS_FOR_BETA:
            return None, n
        mean_p = sum(aligned_p) / n
        mean_b = sum(aligned_b) / n
        cov = sum((p - mean_p) * (b - mean_b) for p, b in zip(aligned_p, aligned_b)) / (n - 1)
        var_b = sum((b - mean_b) ** 2 for b in aligned_b) / (n - 1)
        if var_b <= 0:
            return None, n
        return round(cov / var_b, 4), n

    def _compute_weighted_snapshot_beta(
        self,
        db: Session,
        account_ids: Sequence[int],
    ) -> Optional[float]:
        """Weighted average of per-symbol ``MarketSnapshot.beta`` using
        market-value weights. Returns ``None`` when the covered weight is
        below ``MIN_BETA_COVERAGE_WEIGHT`` — i.e. we lack beta for the
        majority of the portfolio."""
        if not account_ids:
            return None
        positions = (
            db.query(Position)
            .filter(Position.account_id.in_(account_ids), Position.quantity != 0)
            .all()
        )
        total_mv = sum(float(p.market_value or 0) for p in positions)
        if total_mv <= 0:
            return None
        symbols = [p.symbol for p in positions if p.symbol]
        if not symbols:
            return None
        snaps = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol.in_(symbols),
                MarketSnapshot.is_valid.is_(True),
            )
            .all()
        )
        snap_map = {s.symbol: s for s in snaps}
        weighted = 0.0
        covered = 0.0
        for p in positions:
            w = float(p.market_value or 0) / total_mv
            snap = snap_map.get(p.symbol)
            if snap is not None and snap.beta is not None:
                weighted += w * float(snap.beta)
                covered += w
        if covered < MIN_BETA_COVERAGE_WEIGHT:
            return None
        return round(weighted / covered, 4)

    def _compute_concentration(
        self,
        db: Session,
        account_ids: Sequence[int],
    ) -> Tuple[float, float, str]:
        """Return ``(hhi, top5_weight_pct, label)``. Always defined, even
        when there are zero positions (returns ``0, 0, "N/A"``)."""
        if not account_ids:
            return 0.0, 0.0, "N/A"
        positions = (
            db.query(Position)
            .filter(Position.account_id.in_(account_ids), Position.quantity != 0)
            .all()
        )
        total_mv = sum(float(p.market_value or 0) for p in positions)
        if total_mv <= 0:
            return 0.0, 0.0, "N/A"
        weights = [float(p.market_value or 0) / total_mv for p in positions]
        hhi = sum(w * w for w in weights) * 10000
        top5 = round(sum(sorted(weights, reverse=True)[:5]) * 100, 1)
        label = (
            "Concentrated" if hhi > 2500 else "Moderate" if hhi > 1500 else "Diversified"
        )
        return hhi, top5, label

    def _compute_risk_metrics_core(
        self,
        db: Session,
        account_ids: Sequence[int],
        *,
        lookback_days: int = DEFAULT_RISK_LOOKBACK_DAYS,
    ) -> RiskMetricsResult:
        """Single source of truth for silver-layer risk metrics.

        Fail-closed semantics:
        - No portfolio snapshots → all forward-looking fields ``None``.
        - < ``MIN_SNAPSHOTS_FOR_VOLATILITY`` → volatility / drawdown ``None``.
        - < ``MIN_DAYS_FOR_SHARPE`` → sharpe ``None``.
        - < ``MIN_BETA_COVERAGE_WEIGHT`` weight covered by ``MarketSnapshot.beta``
          → ``beta_weighted_snapshot`` ``None``.
        - Benchmark (``SPY`` / ``^GSPC``) has < ``MIN_RETURNS_FOR_BETA``
          aligned returns → ``beta_portfolio_regression`` ``None``.
        """
        hhi, top5_weight, concentration_label = self._compute_concentration(db, account_ids)

        if not account_ids:
            return RiskMetricsResult(
                beta_portfolio_regression=None,
                beta_weighted_snapshot=None,
                volatility=None,
                sharpe_ratio=None,
                max_drawdown=None,
                hhi=hhi,
                top5_weight=top5_weight,
                concentration_label=concentration_label,
                benchmark_symbol=None,
                benchmark_overlap_days=0,
                portfolio_days=0,
            )

        snapshots = self._load_portfolio_snapshots(
            db, account_ids, lookback_days=lookback_days
        )
        daily = self._aggregate_portfolio_daily_totals(snapshots)
        values = [v for _, v in daily]

        volatility: Optional[float] = None
        sharpe_ratio: Optional[float] = None
        annualized_return: Optional[float] = None
        if len(values) >= MIN_SNAPSHOTS_FOR_VOLATILITY:
            returns = self._daily_returns(values)
            if returns:
                mean_r = sum(returns) / len(returns)
                if len(returns) > 1:
                    var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
                    daily_vol = math.sqrt(var_r) if var_r > 0 else 0.0
                    if daily_vol > 0:
                        volatility = round(
                            daily_vol * math.sqrt(TRADING_DAYS_PER_YEAR) * 100, 2
                        )
                        annualized_return = mean_r * TRADING_DAYS_PER_YEAR
                        if len(values) >= MIN_DAYS_FOR_SHARPE:
                            sharpe_ratio = round(
                                (annualized_return - RISK_FREE_RATE)
                                / (daily_vol * math.sqrt(TRADING_DAYS_PER_YEAR)),
                                3,
                            )

        max_drawdown = self._max_drawdown_pct(values)

        benchmark_symbol: Optional[str] = None
        benchmark_overlap = 0
        beta_regression: Optional[float] = None
        if daily:
            start = daily[0][0]
            if hasattr(start, "year"):
                start_dt = datetime(start.year, start.month, start.day)
            else:
                start_dt = datetime.now(timezone.utc) - timedelta(days=lookback_days)
            benchmark_symbol, benchmark_closes = self._resolve_benchmark(db, start_dt)
            if benchmark_symbol is not None:
                beta_regression, benchmark_overlap = self._compute_regression_beta(
                    daily, benchmark_closes
                )
                if beta_regression is None:
                    # Insufficient overlap — we still know which benchmark we
                    # tried; surface it for diagnostics but null the beta.
                    pass

        beta_weighted_snapshot = self._compute_weighted_snapshot_beta(db, account_ids)

        return RiskMetricsResult(
            beta_portfolio_regression=beta_regression,
            beta_weighted_snapshot=beta_weighted_snapshot,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            hhi=hhi,
            top5_weight=top5_weight,
            concentration_label=concentration_label,
            benchmark_symbol=benchmark_symbol if beta_regression is not None else None,
            benchmark_overlap_days=benchmark_overlap,
            portfolio_days=len(values),
        )

    def compute_risk_metrics(self, db: Session, user_id: int) -> Dict[str, Any]:
        """Public risk-metrics endpoint shim.

        ``user_id`` is required (D88 — no ``user_id=1`` defaults). Returns
        a dict with ``None`` for any metric whose coverage is insufficient;
        callers must render a "insufficient coverage" state rather than
        treat ``None`` as zero (no-silent-fallback.mdc)."""
        acct_ids = [
            row.id
            for row in db.query(BrokerAccount.id)
            .filter(BrokerAccount.user_id == user_id)
            .all()
        ]
        result = self._compute_risk_metrics_core(db, acct_ids)
        return result.to_api_dict()

    def compute_twr(
        self, db: Session, user_id: int, period_days: int = 365
    ) -> Dict[str, Any]:
        """Compute Time-Weighted Return from PortfolioSnapshot history.

        ``user_id`` is required (D88)."""
        acct_ids = [
            row.id
            for row in db.query(BrokerAccount.id)
            .filter(BrokerAccount.user_id == user_id)
            .all()
        ]
        if not acct_ids:
            return {"twr": None, "period_days": period_days, "data_points": 0}
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
        snapshots = (
            db.query(PortfolioSnapshot)
            .filter(
                PortfolioSnapshot.account_id.in_(acct_ids),
                PortfolioSnapshot.snapshot_date >= cutoff.date(),
            )
            .order_by(PortfolioSnapshot.snapshot_date)
            .yield_per(_STREAM_CHUNK_SIZE)
        )
        values = [float(s.total_value or 0) for s in snapshots if s.total_value]

        if len(values) < 2:
            return {"twr": None, "period_days": period_days, "data_points": len(values)}

        twr = 1.0
        for i in range(1, len(values)):
            if values[i - 1] > 0:
                twr *= 1 + (values[i] - values[i - 1]) / values[i - 1]

        return {
            "twr": round((twr - 1) * 100, 2),
            "period_days": period_days,
            "data_points": len(values),
        }

    def compute_sector_attribution(
        self, db: Session, user_id: int
    ) -> List[Dict[str, Any]]:
        """Performance attribution by sector/industry.

        ``user_id`` is required (D88)."""
        acct_ids = [
            row.id
            for row in db.query(BrokerAccount.id)
            .filter(BrokerAccount.user_id == user_id)
            .all()
        ]
        if not acct_ids:
            return []

        positions = (
            db.query(Position)
            .filter(Position.account_id.in_(acct_ids), Position.quantity != 0)
            .all()
        )

        total_mv = sum(float(p.market_value or 0) for p in positions)
        if total_mv <= 0:
            return []

        symbols = [p.symbol for p in positions if p.symbol]
        snap_map: Dict[str, Any] = {}
        if symbols:
            snaps = (
                db.query(MarketSnapshot)
                .filter(
                    MarketSnapshot.symbol.in_(symbols),
                    MarketSnapshot.is_valid.is_(True),
                )
                .all()
            )
            snap_map = {s.symbol: s for s in snaps}

        by_sector: Dict[str, Dict[str, float]] = {}
        for p in positions:
            pos_sector = getattr(p, "sector", None)
            snap = snap_map.get(p.symbol)
            sector = (
                pos_sector
                or (snap.sector if snap and snap.sector else None)
                or "Other"
            )
            s = by_sector.setdefault(sector, {"value": 0, "pnl": 0, "weight": 0})
            mv = float(p.market_value or 0)
            s["value"] += mv
            s["pnl"] += float(p.unrealized_pnl or 0)
            s["weight"] += mv / total_mv

        return [
            {
                "sector": sector,
                "weight_pct": round(data["weight"] * 100, 1),
                "market_value": round(data["value"], 2),
                "contribution_pnl": round(data["pnl"], 2),
            }
            for sector, data in sorted(by_sector.items(), key=lambda x: -x[1]["value"])
        ]


# Global service instance
portfolio_analytics_service = PortfolioAnalyticsService()
