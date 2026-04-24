"""Pydantic response models for high-traffic market data endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- Prices ---


class CurrentPriceResponse(BaseModel):
    """GET /prices/{symbol}"""

    symbol: str
    current_price: Optional[float] = None
    price: Optional[float] = None
    timestamp: str
    source: Optional[str] = None
    as_of: Optional[str] = None
    age_seconds: Optional[int] = None


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
    bars: List[PriceHistoryBar]


# --- Snapshots (row payloads mirror ORM columns; keep dict for JSON/OpenAPI flexibility) ---


class SnapshotSingleResponse(BaseModel):
    """GET /snapshots/{symbol}"""

    symbol: str
    snapshot: Optional[Dict[str, Any]] = None


class SnapshotsListResponse(BaseModel):
    """GET /snapshots — empty universe omits tracked_count."""

    count: int
    tracked_count: Optional[int] = None
    rows: List[Dict[str, Any]]


# --- Dashboard ---


class DashboardCoverageBlock(BaseModel):
    status: Optional[Any] = None
    daily_pct: Optional[Any] = None
    m5_pct: Optional[Any] = None
    daily_stale: Optional[Any] = None
    m5_stale: Optional[Any] = None


class DashboardRegime(BaseModel):
    """Empty-object regime is valid when the tracked universe is empty."""

    up_1d_count: int = 0
    down_1d_count: int = 0
    flat_1d_count: int = 0
    above_sma50_count: int = 0
    above_sma200_count: int = 0
    stage_counts: Dict[str, int] = Field(default_factory=dict)
    stage_counts_normalized: Dict[str, int] = Field(default_factory=dict)


class DashboardSummaryItem(BaseModel):
    symbol: str
    stage_label: str
    previous_stage_label: Optional[str] = None
    current_price: Optional[float] = None
    perf_1d: Optional[float] = None
    perf_5d: Optional[float] = None
    perf_20d: Optional[float] = None
    rs_mansfield_pct: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    current_stage_days: Optional[int] = None
    momentum_score: Optional[float] = None


class DashboardSetups(BaseModel):
    breakout_candidates: List[DashboardSummaryItem]
    pullback_candidates: List[DashboardSummaryItem]
    rs_leaders: List[DashboardSummaryItem]


class DashboardSectorMomentumRow(BaseModel):
    sector: str
    count: int
    avg_perf_20d: Optional[float] = None
    avg_rs_mansfield_pct: Optional[float] = None


class DashboardStageTransition(BaseModel):
    symbol: str
    previous_stage_label: Optional[str] = None
    stage_label: str
    current_stage_days: Optional[int] = None
    perf_1d: Optional[float] = None


class DashboardProximityRow(BaseModel):
    symbol: str
    current_price: Optional[float] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    distance_pct: Optional[float] = None
    distance_atr: Optional[float] = None
    sector: Optional[str] = None
    stage_label: Optional[str] = None
    current_stage_days: Optional[int] = None


class DashboardSectorEtfRow(BaseModel):
    symbol: str
    sector_name: str
    change_1d: Optional[float] = None
    change_5d: Optional[float] = None
    change_20d: Optional[float] = None
    rs_mansfield_pct: Optional[float] = None
    atrx_sma_50: Optional[float] = None
    stage_label: Optional[str] = None
    days_in_stage: Optional[int] = None


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
    rs_mansfield_pct: Optional[float] = None
    sector: Optional[str] = None


class DashboardFundamentalLeader(BaseModel):
    symbol: str
    eps_growth_yoy: float
    rs_mansfield_pct: float
    pe_ttm: Optional[float] = None
    stage_label: str
    sector: Optional[str] = None
    composite_score: float


class DashboardRsiDivergenceItem(BaseModel):
    symbol: str
    perf_20d: float
    rsi: float
    stage_label: str
    sector: Optional[str] = None


class DashboardRsiDivergences(BaseModel):
    bearish: List[DashboardRsiDivergenceItem]
    bullish: List[DashboardRsiDivergenceItem]


class DashboardTdSignal(BaseModel):
    symbol: str
    signals: List[str]
    stage_label: str
    perf_1d: Optional[float] = None
    sector: Optional[str] = None


class DashboardGapLeader(BaseModel):
    symbol: str
    gaps_up: int
    gaps_down: int
    total_gaps: int
    stage_label: str
    sector: Optional[str] = None


class MarketDashboardResponse(BaseModel):
    """GET /dashboard — matches MarketDashboardService.build_dashboard payload."""

    generated_at: str
    latest_snapshot_at: Optional[str] = None
    tracked_count: int
    snapshot_count: int
    coverage: Optional[DashboardCoverageBlock] = None
    regime: DashboardRegime
    leaders: List[DashboardSummaryItem]
    setups: DashboardSetups
    sector_momentum: List[DashboardSectorMomentumRow]
    action_queue: List[DashboardSummaryItem]
    entry_proximity_top: List[DashboardProximityRow]
    exit_proximity_top: List[DashboardProximityRow]
    sector_etf_table: List[DashboardSectorEtfRow]
    entering_stage_2a: List[DashboardStageTransition]
    entering_stage_3: List[DashboardStageTransition]
    entering_stage_4: List[DashboardStageTransition]
    top10_matrix: Dict[str, List[DashboardMetricRankEntry]]
    bottom10_matrix: Dict[str, List[DashboardMetricRankEntry]]
    range_histogram: List[DashboardRangeBin]
    breadth_series: List[DashboardBreadthPoint]
    rrg_sectors: List[DashboardRrgSector]
    upcoming_earnings: List[DashboardUpcomingEarnings]
    fundamental_leaders: List[DashboardFundamentalLeader]
    rsi_divergences: DashboardRsiDivergences
    td_signals: List[DashboardTdSignal]
    gap_leaders: List[DashboardGapLeader]
    constituent_symbols: List[str]
