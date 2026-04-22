"""
Options chain gold surface: IV context, liquidity, spread.

Medallion layer: gold. See docs/ARCHITECTURE.md and D127.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, List, Optional, Sequence

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.models.market.options_chain_snapshot import OptionsChainSnapshot
from backend.services.market.yfinance_options_chain import fetch_yfinance_options_chain

logger = logging.getLogger(__name__)

IV_HISTORY_MIN = 30


class ChainSourceUnavailableError(Exception):
    """No registered provider could return an options chain for the symbol."""


@dataclass
class ChainResult:
    """Result of options chain surface computation."""

    symbol: str
    user_id: int
    source: str
    snapshot_taken_at: datetime
    contracts_processed: int
    contracts_persisted: int
    contracts_skipped_no_iv: int
    contracts_errored: int
    contracts_skipped_malformed: int
    iv_history_queries: int
    rows: list[dict[str, Any]] = field(default_factory=list)
    error_reasons: list[str] = field(default_factory=list)


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def compute_liquidity_score(
    open_interest: int, volume: int, spread_rel: Optional[Decimal]
) -> Optional[Decimal]:
    """Composite liquidity score 0-1: OI, volume, tight spread (see spec)."""
    oi = max(0, int(open_interest))
    v = max(0, int(volume))
    if spread_rel is None:
        srf = 0.0
    else:
        srf = float(max(Decimal(0), spread_rel))
    t1 = _clamp01(math.log10(oi + 1) / 3.0) * 0.5
    t2 = _clamp01(math.log10(v + 1) / 3.0) * 0.3
    t3 = (1.0 - _clamp01(srf / 0.1)) * 0.2
    return Decimal(str(round(t1 + t2 + t3, 4)))


def _mid_spread(
    bid: Optional[Decimal], ask: Optional[Decimal]
) -> tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    if bid is not None and ask is not None:
        if ask < bid:
            logger.debug("options spread crossed market bid=%s ask=%s", bid, ask)
            return None, None, None
        mid = (bid + ask) / Decimal(2)
        s_abs = ask - bid
        if mid is not None and mid > 0 and s_abs >= 0:
            s_rel = s_abs / mid
        else:
            s_rel = None
        return mid, s_abs, s_rel
    if bid is not None and ask is None:
        return bid, None, None
    if ask is not None and bid is None:
        return ask, None, None
    return None, None, None


def _decile_index(strike: Decimal, s_min: Decimal, s_max: Decimal) -> int:
    if s_max <= s_min:
        return 0
    width = s_max - s_min
    pos = (strike - s_min) / width
    idx = int(float(pos) * 10.0)
    if idx < 0:
        return 0
    if idx > 9:
        return 9
    return idx


def _decile_strike_bounds(
    s_min: Decimal, s_max: Decimal, decile: int
) -> tuple[Decimal, Decimal]:
    if s_max <= s_min:
        return s_min, s_max
    w = s_max - s_min
    lo = s_min + (Decimal(str(decile)) / Decimal(10)) * w
    hi = s_min + (Decimal(str(decile + 1)) / Decimal(10)) * w
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi


def _iv_percentile_rank(
    current: Decimal, values: list[Decimal]
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    if not values:
        return None, None
    sorted_v = sorted(values)
    n = len(sorted_v)
    le = sum(1 for v in sorted_v if v <= current)
    pct = Decimal(str(le)) / Decimal(str(n))
    lo = min(sorted_v)
    hi = max(sorted_v)
    if hi > lo:
        rnk = (current - lo) / (hi - lo)
    else:
        rnk = Decimal(0.5)
    if rnk < 0:
        rnk = Decimal(0)
    if rnk > 1:
        rnk = Decimal(1)
    return pct, rnk


def _snapshot_cutoff_1y(now: datetime) -> datetime:
    n = now
    if n.tzinfo is None:
        n = n.replace(tzinfo=timezone.utc)
    return n - timedelta(days=365)


def _query_ivs_strike_bucket(
    session: Session,
    symbol: str,
    expiry: date,
    option_type: str,
    strike_lo: Decimal,
    strike_hi: Decimal,
    cutoff: datetime,
) -> list[Decimal]:
    q = (
        session.query(OptionsChainSnapshot.implied_vol)
        .filter(
            OptionsChainSnapshot.symbol == symbol,
            OptionsChainSnapshot.expiry == expiry,
            OptionsChainSnapshot.option_type == option_type,
            OptionsChainSnapshot.strike >= strike_lo,
            OptionsChainSnapshot.strike <= strike_hi,
            OptionsChainSnapshot.snapshot_taken_at >= cutoff,
            OptionsChainSnapshot.implied_vol.isnot(None),
        )
    )
    return [Decimal(str(v)) for (v,) in q.all() if v is not None]


def _query_ivs_expiry_otype(
    session: Session,
    symbol: str,
    expiry: date,
    option_type: str,
    cutoff: datetime,
) -> list[Decimal]:
    q = (
        session.query(OptionsChainSnapshot.implied_vol)
        .filter(
            OptionsChainSnapshot.symbol == symbol,
            OptionsChainSnapshot.expiry == expiry,
            OptionsChainSnapshot.option_type == option_type,
            OptionsChainSnapshot.snapshot_taken_at >= cutoff,
            OptionsChainSnapshot.implied_vol.isnot(None),
        )
    )
    return [Decimal(str(v)) for (v,) in q.all() if v is not None]


def _batch_preload_iv_histories(
    session: Session,
    sym: str,
    strikes_by_exp: dict[date, tuple[Decimal, Decimal]],
    row_list: Sequence[dict[str, Any]],
    taken: datetime,
    skip_row_indices: Optional[set[int]] = None,
) -> tuple[
    dict[tuple[date, str, int], list[Decimal]],
    dict[tuple[date, str], list[Decimal]],
    int,
]:
    """Load IV history in O(buckets) + O(fallback pairs) round-trips."""
    cutoff = _snapshot_cutoff_1y(taken)
    decile_keys: set[tuple[date, str, int]] = set()
    for i, r in enumerate(row_list):
        if skip_row_indices is not None and i in skip_row_indices:
            continue
        ex = r.get("expiry")
        strike = r.get("strike")
        ot = r.get("option_type")
        if ex is None or strike is None or ot is None:
            continue
        if r.get("implied_vol") is None:
            continue
        s_lo, s_hi = strikes_by_exp.get(ex, (strike, strike))
        try:
            dec = _decile_index(strike, s_lo, s_hi)
        except (TypeError, ValueError) as e:
            logger.warning(
                "options chain IV decile: symbol=%s row_index=%d: %s",
                sym,
                i,
                e,
            )
            continue
        decile_keys.add((ex, str(ot), dec))

    bucket_hists: dict[tuple[date, str, int], list[Decimal]] = {}
    qcount = 0
    for (ex, oty, dec) in decile_keys:
        s_lo, s_hi = strikes_by_exp[ex]
        lo, hi = _decile_strike_bounds(s_lo, s_hi, dec)
        bucket_hists[(ex, oty, dec)] = _query_ivs_strike_bucket(
            session, sym, ex, oty, lo, hi, cutoff
        )
        qcount += 1

    need_fb: set[tuple[date, str]] = set()
    for key, hist in bucket_hists.items():
        ex, oty, _d = key
        if len(hist) < IV_HISTORY_MIN:
            need_fb.add((ex, oty))

    fallback: dict[tuple[date, str], list[Decimal]] = {}
    for (ex, oty) in need_fb:
        fallback[(ex, oty)] = _query_ivs_expiry_otype(
            session, sym, ex, oty, cutoff
        )
        qcount += 1

    return bucket_hists, fallback, qcount


def _iv_hist_for_contract(
    ex: date,
    oty: str,
    strike: Decimal,
    s_lo: Decimal,
    s_hi: Decimal,
    bucket_hists: dict[tuple[date, str, int], list[Decimal]],
    fallback: dict[tuple[date, str], list[Decimal]],
) -> tuple[list[Decimal], Optional[str]]:
    dec = _decile_index(strike, s_lo, s_hi)
    bhist = bucket_hists.get((ex, oty, dec), [])
    if len(bhist) >= IV_HISTORY_MIN:
        return bhist, None
    fb = fallback.get((ex, oty), [])
    if len(fb) >= IV_HISTORY_MIN:
        return fb, None
    combined = fb or bhist
    if not combined:
        return [], "insufficient history"
    return combined, "insufficient history"


class OptionsChainSurface:
    """Build and persist per-contract options surface rows."""

    def resolve_rows(
        self, symbol: str, user_id: int, expiries: Optional[List[date]] = None
    ) -> tuple[str, list[dict[str, Any]]]:
        """Resolve chain data (yfinance). user_id reserved for data-source prefs."""
        _ = user_id
        if not (symbol or "").strip():
            raise ChainSourceUnavailableError("empty symbol")
        rows = fetch_yfinance_options_chain(
            symbol, max_dte_days=120, expiries=expiries
        )
        if not rows:
            raise ChainSourceUnavailableError(f"no options chain for {symbol!r}")
        return "yfinance", rows

    def compute(
        self,
        symbol: str,
        user_id: int,
        *,
        session: Session,
        expiries: Optional[List[date]] = None,
        rows: Optional[Sequence[dict[str, Any]]] = None,
        snapshot_taken_at: Optional[datetime] = None,
    ) -> ChainResult:
        """Fetch chain, compute metrics, upsert, return structured counters.

        Callers own the SQLAlchemy ``session`` (commit/rollback scope); Celery
        and route handlers open ``SessionLocal()`` at their boundary.
        """
        return self._compute_impl(
            session,
            symbol,
            user_id,
            expiries=expiries,
            rows=rows,
            snapshot_taken_at=snapshot_taken_at,
        )

    def _compute_impl(
        self,
        session: Session,
        symbol: str,
        user_id: int,
        *,
        expiries: Optional[List[date]] = None,
        rows: Optional[Sequence[dict[str, Any]]] = None,
        snapshot_taken_at: Optional[datetime] = None,
    ) -> ChainResult:
        taken = snapshot_taken_at or datetime.now(timezone.utc)
        if taken.tzinfo is None:
            taken = taken.replace(tzinfo=timezone.utc)
        if rows is None:
            source, row_list = self.resolve_rows(symbol, user_id, expiries=expiries)
        else:
            source = "fixture"
            row_list = list(rows)

        sym = (symbol or "").upper().strip()
        strikes_by_exp: dict[date, tuple[Decimal, Decimal]] = {}
        prepass_unusable: set[int] = set()
        for i, r in enumerate(row_list):
            try:
                ex = r.get("expiry")
                st = r.get("strike")
                ot = r.get("option_type")
                if ex is None or st is None or ot is None:
                    continue
                if ex not in strikes_by_exp:
                    strikes_by_exp[ex] = (st, st)
                else:
                    lo, hi = strikes_by_exp[ex]
                    if st < lo:
                        lo = st
                    if st > hi:
                        hi = st
                    strikes_by_exp[ex] = (lo, hi)
            except Exception as e:
                logger.warning(
                    "options chain strike-range prepass: symbol=%s row_index=%d: %s",
                    sym,
                    i,
                    e,
                )
                prepass_unusable.add(i)

        bucket_hists, iv_fallback, iv_history_queries = _batch_preload_iv_histories(
            session,
            sym,
            strikes_by_exp,
            row_list,
            taken,
            skip_row_indices=prepass_unusable,
        )

        processed = len(row_list)
        persisted = 0
        skipped_no_iv = 0
        skipped_malformed = 0
        errored = 0
        out_result_rows: list[dict[str, Any]] = []
        db_rows: list[dict[str, Any]] = []
        reasons: list[str] = []

        for i, r in enumerate(row_list):
            if i in prepass_unusable:
                skipped_malformed += 1
                continue
            ex = r.get("expiry")
            strike = r.get("strike")
            otype = r.get("option_type")
            if ex is None or strike is None or otype is None:
                skipped_malformed += 1
                continue
            try:
                bid = r.get("bid")
                ask = r.get("ask")
                oi = int(r.get("open_interest") or 0)
                vol = int(r.get("volume") or 0)
                s_lo, s_hi = strikes_by_exp.get(ex, (strike, strike))
                mid, s_abs, s_rel = _mid_spread(bid, ask)
                liq = compute_liquidity_score(oi, vol, s_rel)
                iv: Optional[Decimal] = r.get("implied_vol")
                ivp: Optional[Decimal] = None
                ivr: Optional[Decimal] = None
                if iv is not None:
                    hist, reason = _iv_hist_for_contract(
                        ex,
                        str(otype),
                        strike,
                        s_lo,
                        s_hi,
                        bucket_hists,
                        iv_fallback,
                    )
                    if reason:
                        reasons.append(
                            f"{sym} {ex} {strike} {otype}: {reason}"
                        )
                    if len(hist) >= IV_HISTORY_MIN:
                        ivp, ivr = _iv_percentile_rank(iv, hist)
                else:
                    skipped_no_iv += 1

                row_dict: dict[str, Any] = {
                    "symbol": sym,
                    "expiry": ex,
                    "strike": strike,
                    "option_type": otype,
                    "bid": bid,
                    "ask": ask,
                    "mid": mid,
                    "spread_abs": s_abs,
                    "spread_rel": s_rel,
                    "open_interest": oi,
                    "volume": vol,
                    "implied_vol": iv,
                    "iv_pctile_1y": ivp,
                    "iv_rank_1y": ivr,
                    "liquidity_score": liq,
                    "delta": r.get("delta"),
                    "gamma": r.get("gamma"),
                    "theta": r.get("theta"),
                    "vega": r.get("vega"),
                    "snapshot_taken_at": taken,
                    "source": source,
                }
                db_rows.append(row_dict)
                out_result_rows.append(
                    {k: v for k, v in row_dict.items() if k != "source"}
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("options chain row error %s: %s", sym, e)
                errored += 1

        if db_rows:
            ins = pg_insert(OptionsChainSnapshot).values(db_rows)
            excl = ins.excluded
            set_ = {
                c.name: getattr(excl, c.name)
                for c in OptionsChainSnapshot.__table__.columns
                if c.name and c.name != "id"
            }
            ins = ins.on_conflict_do_update(
                constraint="uq_ocs_sym_exp_strike_type_ts",
                set_=set_,
            )
            session.execute(ins)
            persisted = len(db_rows)
            session.commit()
        else:
            session.rollback()

        assert (
            persisted + errored + skipped_malformed == processed
        ), "counter drift"
        assert skipped_no_iv <= persisted, "invalid skipped count"

        logger.info(
            "options_chain_surface %s: processed=%d persisted=%d "
            "skipped_no_iv=%d errored=%d skipped_malformed=%d "
            "iv_history_queries=%d",
            sym,
            processed,
            persisted,
            skipped_no_iv,
            errored,
            skipped_malformed,
            iv_history_queries,
        )
        return ChainResult(
            symbol=sym,
            user_id=user_id,
            source=source,
            snapshot_taken_at=taken,
            contracts_processed=processed,
            contracts_persisted=persisted,
            contracts_skipped_no_iv=skipped_no_iv,
            contracts_errored=errored,
            contracts_skipped_malformed=skipped_malformed,
            iv_history_queries=iv_history_queries,
            rows=out_result_rows,
            error_reasons=reasons,
        )