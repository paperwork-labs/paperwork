"""Pydantic response models for high-traffic market data endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# --- Prices ---


class CurrentPriceResponse(BaseModel):
    """GET /prices/{symbol}"""

    symbol: str
    current_price: float | None = None
    price: float | None = None
    timestamp: str
    source: str | None = None
    as_of: str | None = None
    age_seconds: int | None = None


class PriceHistoryBar(BaseModel):
    """Single OHLCV bar from GET /prices/{symbol}/history."""

    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceHistoryResponse(BaseModel):
    """GET /prices/{symbol}/history"""

    symbol: str
    period: str
    interval: str
    data_source: str
    bars: list[PriceHistoryBar]


# --- Snapshots (row payloads mirror ORM columns; keep dict for JSON/OpenAPI flexibility) ---


class SnapshotSingleResponse(BaseModel):
    """GET /snapshots/{symbol}"""

    symbol: str
    snapshot: dict[str, Any] | None = None


class SnapshotsListResponse(BaseModel):
    """GET /snapshots — empty universe omits tracked_count."""

    count: int
    tracked_count: int | None = None
    rows: list[dict[str, Any]]


# --- Dashboard ---


class DashboardCoverageBlock(BaseModel):
    status: Any | None = None
    daily_pct: Any | None = None
    m5_pct: Any | None = None
    daily_stale: Any | None = None
    m5_stale: Any | None = None


class DashboardRegime(BaseModel):
    """Empty-object regime is valid when the tracked universe is empty."""

    up_1d_count: int = 0
    down_1d_count: int = 0
    flat_1d_count: int = 0
    above_sma50_count: int = 0
    above_sma200_count: int = 0
    stage_counts: dict[str, int] = Field(default_factory=dict)
    stage_counts_normalized: dict[str, int] = Field(default_factory=dict)


class DashboardSummaryItem(BaseModel):
    symbol: str
    stage_label: str
    previous_stage_label: str | None = None
    current_price: float | None = None
    perf_1d: float | None = None
    perf_5d: float | None = None
    perf_20d: float | None = None
    rs_mansfield_pct: float | None = None
    sector: str | None = None
    industry: str | None = None
    current_stage_days: int | None = None
    momentum_score: float | None = None


class DashboardSetups(BaseModel):
    breakout_candidates: list[DashboardSummaryItem]
    pullback_candidates: list[DashboardSummaryItem]
    rs_leaders: list[DashboardSummaryItem]


class DashboardSectorMomentumRow(BaseModel):
    sector: str
    count: int
    avg_perf_20d: float | None = None
    avg_rs_mansfield_pct: float | None = None


class DashboardStageTransition(BaseModel):
    symbol: str
    previous_stage_label: str | None = None
    stage_label: str
    current_stage_days: int | None = None
    perf_1d: float | None = None


class DashboardProximityRow(BaseModel):
    symbol: str
    current_price: float | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    distance_pct: float | None = None
    distance_atr: float | None = None
    sector: str | None = None
    stage_label: str | None = None
    current_stage_days: int | None = None


class DashboardSectorEtfRow(BaseModel):
    symbol: str
    sector_name: str
    change_1d: float | None = None
    change_5d: float | None = None
    change_20d: float | None = None
    rs_mansfield_pct: float | None = None
    atrx_sma_50: float | None = None
    stage_label: str | None = None
    days_in_stage: int | None = None


class DashboardMetricRankEntry(BaseModel):
    symbol: str
    value: float
    metric: str


class DashboardRangeBin(BaseModel):
    bin: str
    count: int


class DashboardBreadthPoint(BaseModel):
    date: str
    above_sma50_pct: float
    above_sma200_pct: float
    total: int


class DashboardRrgSector(BaseModel):
    symbol: str
    name: str
    rs_ratio: float
    rs_momentum: float


class DashboardUpcomingEarnings(BaseModel):
    symbol: str
    next_earnings: str
    stage_label: str
    rs_mansfield_pct: float | None = None
    sector: str | None = None


class DashboardFundamentalLeader(BaseModel):
    symbol: str
    eps_growth_yoy: float
    rs_mansfield_pct: float
    pe_ttm: float | None = None
    stage_label: str
    sector: str | None = None
    composite_score: float


class DashboardRsiDivergenceItem(BaseModel):
    symbol: str
    perf_20d: float
    rsi: float
    stage_label: str
    sector: str | None = None


class DashboardRsiDivergences(BaseModel):
    bearish: list[DashboardRsiDivergenceItem]
    bullish: list[DashboardRsiDivergenceItem]


class DashboardTdSignal(BaseModel):
    symbol: str
    signals: list[str]
    stage_label: str
    perf_1d: float | None = None
    sector: str | None = None


class DashboardGapLeader(BaseModel):
    symbol: str
    gaps_up: int
    gaps_down: int
    total_gaps: int
    stage_label: str
    sector: str | None = None


class MarketDashboardResponse(BaseModel):
    """GET /dashboard — matches MarketDashboardService.build_dashboard payload."""

    generated_at: str
    latest_snapshot_at: str | None = None
    tracked_count: int
    snapshot_count: int
    coverage: DashboardCoverageBlock | None = None
    regime: DashboardRegime
    leaders: list[DashboardSummaryItem]
    setups: DashboardSetups
    sector_momentum: list[DashboardSectorMomentumRow]
    action_queue: list[DashboardSummaryItem]
    entry_proximity_top: list[DashboardProximityRow]
    exit_proximity_top: list[DashboardProximityRow]
    sector_etf_table: list[DashboardSectorEtfRow]
    entering_stage_2a: list[DashboardStageTransition]
    entering_stage_3: list[DashboardStageTransition]
    entering_stage_4: list[DashboardStageTransition]
    top10_matrix: dict[str, list[DashboardMetricRankEntry]]
    bottom10_matrix: dict[str, list[DashboardMetricRankEntry]]
    range_histogram: list[DashboardRangeBin]
    breadth_series: list[DashboardBreadthPoint]
    rrg_sectors: list[DashboardRrgSector]
    upcoming_earnings: list[DashboardUpcomingEarnings]
    fundamental_leaders: list[DashboardFundamentalLeader]
    rsi_divergences: DashboardRsiDivergences
    td_signals: list[DashboardTdSignal]
    gap_leaders: list[DashboardGapLeader]
    constituent_symbols: list[str]
