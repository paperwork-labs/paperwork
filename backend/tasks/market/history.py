"""
Snapshot history recording and backfill tasks.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import numpy as np
import pandas as pd
from celery import current_task, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import func

from backend.database import SessionLocal
from backend.models import PriceData
from backend.models.market_data import MarketSnapshot, MarketSnapshotHistory
from backend.services.market.constants import WEINSTEIN_WARMUP_CALENDAR_DAYS
from backend.services.market.dataframe_utils import price_data_rows_to_dataframe
from backend.services.market.indicator_engine import (
    classify_ma_bucket_from_ma,
    compute_core_indicators_series,
    compute_full_indicator_series,
    compute_weinstein_stage_series_from_daily,
)
from backend.services.market.market_data_service import market_data_service
from backend.services.market.snapshot_history_writer import (
    build_snapshot_history_pg_upsert_stmt,
    upsert_snapshot_history_row,
)
from backend.services.market.stage_utils import compute_stage_run_lengths
from backend.tasks.utils.task_utils import _get_tracked_symbols_safe, _set_task_status, task_run

logger = logging.getLogger(__name__)


def _celery_task_id_short() -> str:
    try:
        req = getattr(current_task, "request", None)
        tid = getattr(req, "id", None) if req else None
        return str(tid)[:8] if tid else "?"
    except Exception:
        return "?"


_DEFAULT_SOFT = 3500
_DEFAULT_HARD = 3600


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run("admin_snapshots_history_backfill_date")
def snapshot_for_date(as_of_date: str, batch_size: int = 50) -> dict:
    """Backfill `market_snapshot_history` for a specific as-of date from local `price_data`.

    This is useful when history was not recorded for a day but OHLCV exists, and we want
    snapshot coverage dots to reflect that day.

    Notes:
    - DB-first only (no provider calls)
    - Does NOT update `market_snapshot` (latest cache)
    """
    session = SessionLocal()
    try:
        # Parse date (YYYY-MM-DD) into a naive timestamp to match price_data.date semantics.
        as_of_dt = datetime.fromisoformat(as_of_date).replace(hour=0, minute=0, second=0, microsecond=0)

        ordered = _get_tracked_symbols_safe(session)

        processed_ok = 0
        skipped_no_data = 0
        upserted = 0
        errors = 0
        error_samples: list[dict] = []

        for i in range(0, len(ordered), max(1, batch_size)):
            chunk = ordered[i : i + batch_size]
            for sym in chunk:
                try:
                    snap = market_data_service.snapshots.compute_snapshot_from_db(
                        session, sym, as_of_dt=as_of_dt
                    )
                    if not snap:
                        skipped_no_data += 1
                        continue
                    with session.begin_nested():
                        processed_ok += 1

                        upsert_snapshot_history_row(
                            session,
                            sym,
                            as_of_dt,
                            snap,
                            analysis_type="technical_snapshot",
                        )
                        upserted += 1
                except SoftTimeLimitExceeded:
                    raise
                except Exception as exc:
                    errors += 1
                    if len(error_samples) < 25:
                        error_samples.append({"symbol": sym, "error": str(exc)})
            try:
                session.commit()
            except SoftTimeLimitExceeded:
                raise
            except Exception as exc:
                logger.warning(
                    "snapshot_for_date batch commit failed for chunk starting %s: %s",
                    chunk[0] if chunk else "?",
                    exc,
                )
                session.rollback()

        res = {
            "status": "ok",
            "as_of_date": as_of_date,
            "symbols": len(ordered),
            "processed_ok": processed_ok,
            "skipped_no_data": skipped_no_data,
            "upserted": upserted,
            "errors": errors,
            "error_samples": error_samples,
        }
        if error_samples:
            res["error"] = "Sample errors:\n" + "\n".join(
                f"- {e.get('symbol')}: {e.get('error')}" for e in error_samples
            )
        return res
    finally:
        session.close()


@shared_task(
    soft_time_limit=14400,
    time_limit=16200,
)
@task_run("admin_snapshots_history_backfill", lock_key=lambda **_: "snapshots_history_backfill", lock_ttl_seconds=16500)
def snapshot_last_n_days(
    days: int = 200,
    batch_size: int = 25,
    since_date: Optional[str] = None,
) -> dict:
    """Backfill `market_snapshot_history` for the last N trading days (SPY calendar) from local DB prices.

    This computes and stores indicators per day (ledger) so you can later view/backtest
    historical snapshots. `market_snapshot` remains the fast latest-view.
    """
    session = SessionLocal()
    try:
        ordered = _get_tracked_symbols_safe(session)

        # Trading-day calendar:
        # Prefer SPY dates as canonical, but fall back to any symbol with 1d bars in the DB.
        # This keeps the backfill robust even when SPY isn't present yet or is stale.
        calendar_symbol = "SPY"
        since_dt = None
        if since_date:
            try:
                import pandas as _pd

                since_dt = _pd.to_datetime(since_date, utc=True).tz_convert(None).normalize().to_pydatetime()
            except Exception:
                since_dt = None
        cal_dates = (
            session.query(PriceData.date)
            .filter(PriceData.symbol == calendar_symbol, PriceData.interval == "1d")
            .order_by(PriceData.date.desc())
            .limit(12000 if since_dt is not None else max(1, int(days)))
            .all()
        )
        as_of_dates = [r[0] for r in cal_dates if r and r[0] is not None and (since_dt is None or r[0] >= since_dt)]
        latest_daily_dt = (
            session.query(func.max(PriceData.date))
            .filter(PriceData.interval == "1d")
            .scalar()
        )
        spy_latest_dt = (
            session.query(func.max(PriceData.date))
            .filter(PriceData.symbol == calendar_symbol, PriceData.interval == "1d")
            .scalar()
        )
        if latest_daily_dt and (spy_latest_dt is None or spy_latest_dt.date() < latest_daily_dt.date()):
            alt_query = session.query(PriceData.symbol).filter(
                PriceData.interval == "1d",
                PriceData.date == latest_daily_dt,
            )
            if ordered:
                alt_query = alt_query.filter(PriceData.symbol.in_(ordered))
            alt_symbol = alt_query.limit(1).scalar()
            if alt_symbol and alt_symbol != calendar_symbol:
                calendar_symbol = str(alt_symbol)
                cal_dates = (
                    session.query(PriceData.date)
                    .filter(PriceData.symbol == calendar_symbol, PriceData.interval == "1d")
                    .order_by(PriceData.date.desc())
                    .limit(12000 if since_dt is not None else max(1, int(days)))
                    .all()
                )
                as_of_dates = [r[0] for r in cal_dates if r and r[0] is not None and (since_dt is None or r[0] >= since_dt)]
        if not as_of_dates:
            alt = (
                session.query(PriceData.symbol, func.count(PriceData.date).label("n"))
                .filter(PriceData.interval == "1d")
                .group_by(PriceData.symbol)
                .order_by(func.count(PriceData.date).desc())
                .limit(1)
                .all()
            )
            if alt:
                calendar_symbol = str(alt[0][0] or "")
                cal_dates = (
                    session.query(PriceData.date)
                    .filter(PriceData.symbol == calendar_symbol, PriceData.interval == "1d")
                    .order_by(PriceData.date.desc())
                    .limit(12000 if since_dt is not None else max(1, int(days)))
                    .all()
                )
                as_of_dates = [r[0] for r in cal_dates if r and r[0] is not None and (since_dt is None or r[0] >= since_dt)]

        if not as_of_dates:
            err = "No daily bars found in price_data to establish a trading-day calendar (expected SPY or any 1d bars)."
            _set_task_status("admin_snapshots_history_backfill", "error", {"status": "error", "error": err})
            return {"status": "error", "error": err}

        # Oldest->newest list (raw timestamps) + normalized midnight UTC keys (naive).
        as_of_dates = sorted(as_of_dates)
        start_dt = as_of_dates[0]

        import pandas as pd

        def _norm_midnight_utc(dt: object) -> datetime:
            # Ensure DatetimeIndex-compatible keys while avoiding tz mismatches.
            ts = pd.to_datetime(dt, utc=True, errors="coerce")
            if ts is None or pd.isna(ts):
                raise ValueError(f"Invalid as_of_date value: {dt!r}")
            return ts.tz_convert(None).normalize().to_pydatetime()

        as_of_days = [_norm_midnight_utc(d) for d in as_of_dates if d is not None]

        # Progress/observability: estimate total rows upfront (upper bound).
        estimated_rows = int(len(ordered) * len(as_of_days))
        _set_task_status(
            "admin_snapshots_history_backfill",
            "running",
            {
                "days": int(days),
                "since_date": since_date,
                "symbols": len(ordered),
                "estimated_rows": estimated_rows,
                "processed_symbols": 0,
                "written_rows": 0,
                "errors": 0,
            },
        )

        processed_symbols = 0
        written_rows = 0
        skipped_no_data = 0
        errors = 0
        error_samples: list[dict] = []

        warmup_start = start_dt - timedelta(days=WEINSTEIN_WARMUP_CALENDAR_DAYS)

        # Preload calendar bars covering the window (+ warmup buffer for weekly stage)
        spy_rows = (
            session.query(
                PriceData.date,
                PriceData.open_price,
                PriceData.high_price,
                PriceData.low_price,
                PriceData.close_price,
                PriceData.volume,
            )
            .filter(PriceData.symbol == calendar_symbol, PriceData.interval == "1d", PriceData.date >= warmup_start)
            .order_by(PriceData.date.asc())
            .all()
        )
        import pandas as pd
        import numpy as np
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from backend.services.market.indicator_engine import (
            compute_core_indicators_series,
            compute_weinstein_stage_series_from_daily,
            classify_ma_bucket_from_ma,
        )

        if spy_rows:
            spy_df = price_data_rows_to_dataframe(spy_rows, ascending=True)
            # Normalize to midnight UTC (naive) so membership checks align with as_of_days.
            spy_df.index = pd.to_datetime(spy_df.index, utc=True, errors="coerce").tz_convert(None).normalize()
        else:
            spy_df = pd.DataFrame()

        last_progress_emit = 0
        try:
            for i in range(0, len(ordered), max(1, batch_size)):
                chunk = ordered[i : i + batch_size]
                for sym in chunk:
                    try:
                        rows = (
                            session.query(
                                PriceData.date,
                                PriceData.open_price,
                                PriceData.high_price,
                                PriceData.low_price,
                                PriceData.close_price,
                                PriceData.volume,
                            )
                            .filter(PriceData.symbol == sym, PriceData.interval == "1d", PriceData.date >= warmup_start)
                            .order_by(PriceData.date.asc())
                            .all()
                        )
                        if not rows:
                            skipped_no_data += 1
                            continue

                        df = price_data_rows_to_dataframe(rows, ascending=True)
                        # Normalize to midnight UTC (naive) so membership checks align with as_of_days.
                        df.index = pd.to_datetime(df.index, utc=True, errors="coerce").tz_convert(None).normalize()
                        if df.empty:
                            skipped_no_data += 1
                            continue

                        core = compute_core_indicators_series(df)
                        # Derived daily fields
                        close = df["Close"]
                        price = close
                        atr14 = core.get("atr_14")
                        atr30 = core.get("atr_30")
                        sma21 = core.get("sma_21")
                        sma50 = core.get("sma_50")
                        sma100 = core.get("sma_100")
                        sma150 = core.get("sma_150")
                        sma200 = core.get("sma_200")

                        def range_pos(window: int) -> pd.Series:
                            hi = df["High"].rolling(window).max()
                            lo = df["Low"].rolling(window).min()
                            denom = (hi - lo).replace(0, np.nan)
                            return ((price - lo) / denom) * 100.0

                        range20 = range_pos(20)
                        range50 = range_pos(50)
                        range252 = range_pos(252)

                        atrp14 = (atr14 / price) * 100.0
                        atrp30 = (atr30 / price) * 100.0
                        atr_distance = (price - sma50) / atr14

                        atrx_sma21 = (price - sma21) / atr14
                        atrx_sma50 = (price - sma50) / atr14
                        atrx_sma100 = (price - sma100) / atr14
                        atrx_sma150 = (price - sma150) / atr14

                        # Stage / RS (best-effort; may be NaN early if insufficient weekly history)
                        stage_daily = pd.DataFrame(index=df.index)
                        stage_run_by_date: dict = {}
                        if not spy_df.empty:
                            stage_daily = compute_weinstein_stage_series_from_daily(
                                df.iloc[::-1].copy(),
                                spy_df.iloc[::-1].copy(),
                            )
                            try:
                                if not stage_daily.empty and "stage_label" in stage_daily.columns:
                                    labels = [
                                        stage_daily.loc[d, "stage_label"] if d in stage_daily.index else None
                                        for d in stage_daily.index
                                    ]
                                    run_info = compute_stage_run_lengths(labels)
                                    stage_run_by_date = dict(zip(stage_daily.index, run_info))
                            except SoftTimeLimitExceeded:
                                raise
                            except Exception:
                                stage_run_by_date = {}

                        # Build per-date payload rows for last N trading days
                        wanted = [d for d in as_of_days if d in df.index]
                        if not wanted:
                            skipped_no_data += 1
                            continue

                        payload_rows = []
                        for d in wanted:
                            # MA bucket (daily)
                            ma_bucket = None
                            try:
                                ma_bucket = classify_ma_bucket_from_ma(
                                    {
                                        "price": float(price.loc[d]),
                                        "sma_5": float(core.loc[d, "sma_5"]) if not pd.isna(core.loc[d, "sma_5"]) else None,
                                        "sma_8": float(core.loc[d, "sma_8"]) if not pd.isna(core.loc[d, "sma_8"]) else None,
                                        "sma_21": float(core.loc[d, "sma_21"]) if not pd.isna(core.loc[d, "sma_21"]) else None,
                                        "sma_50": float(core.loc[d, "sma_50"]) if not pd.isna(core.loc[d, "sma_50"]) else None,
                                        "sma_100": float(core.loc[d, "sma_100"]) if not pd.isna(core.loc[d, "sma_100"]) else None,
                                        "sma_200": float(core.loc[d, "sma_200"]) if not pd.isna(core.loc[d, "sma_200"]) else None,
                                    }
                                ).get("bucket")
                            except SoftTimeLimitExceeded:
                                raise
                            except Exception:
                                ma_bucket = None

                            stage_label = None
                            stage_slope_pct = None
                            stage_dist_pct = None
                            rs_mansfield_pct = None
                            try:
                                if not stage_daily.empty and d in stage_daily.index:
                                    stage_label = stage_daily.loc[d, "stage_label"]
                                    stage_slope_pct = (
                                        float(stage_daily.loc[d, "stage_slope_pct"])
                                        if "stage_slope_pct" in stage_daily.columns and not pd.isna(stage_daily.loc[d, "stage_slope_pct"])
                                        else None
                                    )
                                    stage_dist_pct = (
                                        float(stage_daily.loc[d, "stage_dist_pct"])
                                        if "stage_dist_pct" in stage_daily.columns and not pd.isna(stage_daily.loc[d, "stage_dist_pct"])
                                        else None
                                    )
                                    rs_mansfield_pct = (
                                        float(stage_daily.loc[d, "rs_mansfield_pct"])
                                        if "rs_mansfield_pct" in stage_daily.columns and not pd.isna(stage_daily.loc[d, "rs_mansfield_pct"])
                                        else None
                                    )
                            except SoftTimeLimitExceeded:
                                raise
                            except Exception as e:
                                logger.warning("stage_indicator_extract failed for %s on %s: %s", sym, d, e)

                            run_info = stage_run_by_date.get(d) if stage_run_by_date else None
                            payload = {
                                "symbol": sym,
                                "analysis_type": "technical_snapshot",
                                "as_of_timestamp": d.isoformat() if hasattr(d, "isoformat") else str(d),
                                "current_price": float(price.loc[d]) if not pd.isna(price.loc[d]) else None,
                                "rsi": float(core.loc[d, "rsi"]) if "rsi" in core.columns and not pd.isna(core.loc[d, "rsi"]) else None,
                                "sma_5": float(core.loc[d, "sma_5"]) if not pd.isna(core.loc[d, "sma_5"]) else None,
                                "sma_14": float(core.loc[d, "sma_14"]) if not pd.isna(core.loc[d, "sma_14"]) else None,
                                "sma_21": float(core.loc[d, "sma_21"]) if not pd.isna(core.loc[d, "sma_21"]) else None,
                                "sma_50": float(core.loc[d, "sma_50"]) if not pd.isna(core.loc[d, "sma_50"]) else None,
                                "sma_100": float(core.loc[d, "sma_100"]) if not pd.isna(core.loc[d, "sma_100"]) else None,
                                "sma_150": float(core.loc[d, "sma_150"]) if not pd.isna(core.loc[d, "sma_150"]) else None,
                                "sma_200": float(core.loc[d, "sma_200"]) if not pd.isna(core.loc[d, "sma_200"]) else None,
                                "atr_14": float(atr14.loc[d]) if atr14 is not None and not pd.isna(atr14.loc[d]) else None,
                                "atr_30": float(atr30.loc[d]) if atr30 is not None and not pd.isna(atr30.loc[d]) else None,
                                "atrp_14": float(atrp14.loc[d]) if not pd.isna(atrp14.loc[d]) else None,
                                "atrp_30": float(atrp30.loc[d]) if not pd.isna(atrp30.loc[d]) else None,
                                "atr_distance": float(atr_distance.loc[d]) if not pd.isna(atr_distance.loc[d]) else None,
                                "range_pos_20d": float(range20.loc[d]) if not pd.isna(range20.loc[d]) else None,
                                "range_pos_50d": float(range50.loc[d]) if not pd.isna(range50.loc[d]) else None,
                                "range_pos_52w": float(range252.loc[d]) if not pd.isna(range252.loc[d]) else None,
                                "atrx_sma_21": float(atrx_sma21.loc[d]) if not pd.isna(atrx_sma21.loc[d]) else None,
                                "atrx_sma_50": float(atrx_sma50.loc[d]) if not pd.isna(atrx_sma50.loc[d]) else None,
                                "atrx_sma_100": float(atrx_sma100.loc[d]) if not pd.isna(atrx_sma100.loc[d]) else None,
                                "atrx_sma_150": float(atrx_sma150.loc[d]) if not pd.isna(atrx_sma150.loc[d]) else None,
                                "macd": float(core.loc[d, "macd"]) if "macd" in core.columns and not pd.isna(core.loc[d, "macd"]) else None,
                                "macd_signal": float(core.loc[d, "macd_signal"]) if "macd_signal" in core.columns and not pd.isna(core.loc[d, "macd_signal"]) else None,
                                "ma_bucket": ma_bucket,
                                "stage_label": stage_label if isinstance(stage_label, str) else None,
                                "stage_label_5d_ago": None,  # computed below
                                "current_stage_days": run_info.get("current_stage_days") if run_info else None,
                                "previous_stage_label": run_info.get("previous_stage_label") if run_info else None,
                                "previous_stage_days": run_info.get("previous_stage_days") if run_info else None,
                                "stage_slope_pct": stage_slope_pct,
                                "stage_dist_pct": stage_dist_pct,
                                "rs_mansfield_pct": rs_mansfield_pct,
                            }
                            row = {
                                "symbol": sym,
                                "analysis_type": "technical_snapshot",
                                "as_of_date": d,
                                "current_price": payload.get("current_price"),
                                "rsi": payload.get("rsi"),
                                "atr_value": payload.get("atr_14"),
                                "sma_50": payload.get("sma_50"),
                                "macd": payload.get("macd"),
                                "macd_signal": payload.get("macd_signal"),
                            }
                            # Add any wide columns that exist on the model.
                            for k, v in payload.items():
                                if hasattr(MarketSnapshotHistory, k):
                                    row[k] = v
                            payload_rows.append(row)

                        # Stage 5d ago: compute from daily mapped labels and attach to payloads
                        try:
                            if not stage_daily.empty and "stage_label" in stage_daily.columns:
                                stage_5d = stage_daily["stage_label"].shift(5)
                                for r in payload_rows:
                                    d = r["as_of_date"]
                                    if d in stage_5d.index:
                                        lbl = stage_5d.loc[d]
                                        if isinstance(lbl, str):
                                            r["stage_label_5d_ago"] = lbl
                        except SoftTimeLimitExceeded:
                            raise
                        except Exception as e:
                            logger.warning("stage_label_5d_ago failed for %s: %s", sym, e)

                        # Update latest snapshot stage duration fields from history backfill.
                        # Only write if the latest backfill row has a recognized (non-UNKNOWN)
                        # stage; otherwise we'd overwrite the live snapshot's correct values.
                        try:
                            if payload_rows and stage_run_by_date:
                                latest_row = max(payload_rows, key=lambda r: r.get("as_of_date"))
                                latest_date = latest_row.get("as_of_date")
                                latest_stage = latest_row.get("stage_label")
                                latest_info = stage_run_by_date.get(latest_date)
                                is_known_stage = (
                                    isinstance(latest_stage, str)
                                    and latest_stage.strip()
                                    and latest_stage.strip().upper() != "UNKNOWN"
                                )
                                if latest_info and is_known_stage:
                                    session.query(MarketSnapshot).filter(
                                        MarketSnapshot.symbol == sym,
                                        MarketSnapshot.analysis_type == "technical_snapshot",
                                    ).update(
                                        {
                                            "current_stage_days": latest_info.get("current_stage_days"),
                                            "previous_stage_label": latest_info.get("previous_stage_label"),
                                            "previous_stage_days": latest_info.get("previous_stage_days"),
                                        },
                                        synchronize_session=False,
                                    )
                                elif latest_info and not is_known_stage:
                                    logger.debug(
                                        "Skipping snapshot stage update for %s: "
                                        "latest backfill stage is '%s' (UNKNOWN/empty)",
                                        sym,
                                        latest_stage,
                                    )
                        except SoftTimeLimitExceeded:
                            raise
                        except Exception:
                            logger.warning(
                                "Failed to update snapshot stage fields for %s",
                                sym,
                                exc_info=True,
                            )

                        stmt = build_snapshot_history_pg_upsert_stmt(
                            payload_rows, conflict_update="wide"
                        )
                        session.execute(stmt)
                        session.commit()
                        written_rows += len(payload_rows)
                        processed_symbols += 1

                        # Emit progress every ~10 symbols to keep UI responsive without spamming Redis.
                        if processed_symbols - last_progress_emit >= 10:
                            last_progress_emit = processed_symbols
                            _set_task_status(
                                "admin_snapshots_history_backfill",
                                "running",
                                {
                                    "days": int(days),
                                    "symbols": len(ordered),
                                    "estimated_rows": estimated_rows,
                                    "processed_symbols": processed_symbols,
                                    "written_rows": written_rows,
                                    "skipped_no_data": skipped_no_data,
                                    "errors": errors,
                                },
                            )
                    except SoftTimeLimitExceeded:
                        raise
                    except Exception as exc:
                        session.rollback()
                        errors += 1
                        if len(error_samples) < 25:
                            error_samples.append({"symbol": sym, "error": str(exc)})
        except SoftTimeLimitExceeded:
            logger.warning(
                "snapshot_last_n_days hit soft time limit after processing %d symbols",
                processed_symbols,
            )
            try:
                session.commit()
            except SoftTimeLimitExceeded:
                raise
            except Exception as ce:
                logger.warning(
                    "snapshot_last_n_days partial commit after soft limit failed: %s",
                    ce,
                    exc_info=True,
                )
                session.rollback()
            partial_res = {
                "status": "partial",
                "days": int(days),
                "since_date": since_date,
                "symbols": len(ordered),
                "calendar_symbol": calendar_symbol,
                "processed_symbols": processed_symbols,
                "written_rows": written_rows,
                "skipped_no_data": skipped_no_data,
                "errors": errors,
                "error_samples": error_samples,
            }
            _set_task_status(
                "admin_snapshots_history_backfill",
                "ok",
                partial_res,
            )
            return partial_res

        res = {
            "status": "ok" if errors == 0 else "error",
            "days": int(days),
            "symbols": len(ordered),
            "calendar_symbol": calendar_symbol,
            "processed_symbols": processed_symbols,
            "written_rows": written_rows,
            "skipped_no_data": skipped_no_data,
            "errors": errors,
            "error_samples": error_samples,
        }
        if error_samples:
            res["error"] = "Sample errors:\n" + "\n".join(
                f"- {e.get('symbol')}: {e.get('error')}" for e in error_samples
            )
        _set_task_status(
            "admin_snapshots_history_backfill",
            "ok" if errors == 0 else "error",
            res,
        )
        return res
    finally:
        session.close()


# ============================= Single-Symbol Snapshot History Backfill =============================


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run("admin_snapshots_history_backfill_symbol")
def snapshot_for_symbol(
    symbol: str,
    start_date: str,
    end_date: Optional[str] = None,
) -> dict:
    """Backfill MarketSnapshotHistory for a single symbol over a date range.

    Reads OHLCV from PriceData, calls compute_full_indicator_series(),
    upserts rows for the requested date range.
    """
    session = SessionLocal()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            end_cmp = pd.Timestamp(datetime.strptime(end_date, "%Y-%m-%d")).normalize()
        else:
            end_cmp = (
                pd.Timestamp(datetime.now(timezone.utc))
                .tz_convert("UTC")
                .tz_localize(None)
                .normalize()
            )

        rows = (
            session.query(
                PriceData.date, PriceData.open_price, PriceData.high_price,
                PriceData.low_price, PriceData.close_price, PriceData.volume,
            )
            .filter(PriceData.symbol == symbol, PriceData.interval == "1d")
            .order_by(PriceData.date.asc())
            .all()
        )
        if not rows:
            return {"status": "skipped", "reason": "no_price_data", "symbol": symbol}

        df = price_data_rows_to_dataframe(rows, ascending=True)
        df.index = pd.to_datetime(df.index, utc=True, errors="coerce").tz_convert(None).normalize()
        if df.empty:
            return {"status": "skipped", "reason": "empty_dataframe", "symbol": symbol}

        spy_df = pd.DataFrame()
        try:
            spy_rows = (
                session.query(
                    PriceData.date, PriceData.open_price, PriceData.high_price,
                    PriceData.low_price, PriceData.close_price, PriceData.volume,
                )
                .filter(PriceData.symbol == "SPY", PriceData.interval == "1d")
                .order_by(PriceData.date.asc())
                .all()
            )
            if spy_rows:
                spy_df = price_data_rows_to_dataframe(spy_rows, ascending=True)
                spy_df.index = pd.to_datetime(spy_df.index, utc=True, errors="coerce").tz_convert(None).normalize()
        except SoftTimeLimitExceeded:
            raise
        except Exception as e:
            logger.warning("spy_benchmark_fetch failed for %s: %s", symbol, e)

        indicators_df = compute_full_indicator_series(df, spy_df=spy_df if not spy_df.empty else None)

        mask = (indicators_df.index >= pd.Timestamp(start_dt)) & (indicators_df.index <= end_cmp)
        target_df = indicators_df.loc[mask]

        if target_df.empty:
            return {"status": "skipped", "reason": "no_dates_in_range", "symbol": symbol}

        written = 0
        errors = 0
        for batch_start in range(0, len(target_df), 100):
            batch = target_df.iloc[batch_start:batch_start + 100]
            batch_rows = []
            for d, row in batch.iterrows():
                r = {
                    "symbol": symbol,
                    "analysis_type": "technical_snapshot",
                    "as_of_date": d,
                }
                for k, v in row.items():
                    if hasattr(MarketSnapshotHistory, k):
                        if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                            r[k] = None
                        else:
                            r[k] = v
                batch_rows.append(r)

            try:
                stmt = build_snapshot_history_pg_upsert_stmt(
                    batch_rows, conflict_update="partial"
                )
                session.execute(stmt)
                session.commit()
                written += len(batch_rows)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                session.rollback()
                errors += len(batch_rows)
                logger.warning(
                    "snapshot_for_symbol batch upsert failed for %s: %s",
                    symbol,
                    e,
                )

        return {
            "status": "ok",
            "symbol": symbol,
            "start_date": start_date,
            "written_rows": written,
            "errors": errors,
        }
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:
        return {"status": "error", "symbol": symbol, "error": str(exc)}
    finally:
        session.close()


@shared_task(
    soft_time_limit=300,
    time_limit=600,
)
@task_run("admin_snapshots_history_record")
def record_daily(symbols: Optional[List[str]] = None) -> dict:
    """Persist immutable daily snapshots to MarketSnapshotHistory from latest MarketSnapshot."""
    _set_task_status("admin_snapshots_history_record", "running")
    task_id = _celery_task_id_short()
    t0 = time.monotonic()
    logger.info("[%s] record_daily started", task_id)
    session = SessionLocal()
    try:
        if not symbols:
            symbols = _get_tracked_symbols_safe(session)
        sym_list = sorted(set(s.upper() for s in symbols))
        total = len(sym_list)
        written = 0
        skipped_no_snapshot = 0
        errors = 0
        error_samples: List[dict] = []
        for n, sym in enumerate(sym_list, 1):
            try:
                row = (
                    session.query(MarketSnapshot)
                    .filter(
                        MarketSnapshot.symbol == sym,
                        MarketSnapshot.analysis_type == "technical_snapshot",
                    )
                    .order_by(MarketSnapshot.analysis_timestamp.desc())
                    .first()
                )
                if row and isinstance(row.raw_analysis, dict):
                    snapshot = dict(row.raw_analysis)
                else:
                    snapshot = market_data_service.snapshots.compute_snapshot_from_db(session, sym)
                    if not snapshot:
                        skipped_no_snapshot += 1
                        continue
                as_of_dt = None
                try:
                    as_of_dt = getattr(row, "as_of_timestamp", None) if row is not None else None
                except SoftTimeLimitExceeded:
                    raise
                except Exception:
                    as_of_dt = None
                if as_of_dt is None:
                    as_of_dt = (
                        session.query(PriceData.date)
                        .filter(PriceData.symbol == sym, PriceData.interval == "1d")
                        .order_by(PriceData.date.desc())
                        .limit(1)
                        .scalar()
                    )
                as_of_date = as_of_dt or datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                upsert_snapshot_history_row(
                    session,
                    sym,
                    as_of_date,
                    snapshot,
                    analysis_type="technical_snapshot",
                )
                session.commit()
                written += 1
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                session.rollback()
                errors += 1
                if len(error_samples) < 25:
                    error_samples.append({"symbol": sym, "error": str(e)})
                logger.warning(
                    "[%s] record_daily failed for %s (%d/%d): %s",
                    task_id,
                    sym,
                    n,
                    total,
                    e,
                )
        res = {
            "status": "ok",
            "symbols": len(symbols),
            "written": written,
            "skipped_no_snapshot": skipped_no_snapshot,
            "errors": errors,
            "error_samples": error_samples,
        }
        elapsed = time.monotonic() - t0
        logger.info(
            "[%s] record_daily completed in %.1fs (symbols=%d written=%d skipped=%d errors=%d)",
            task_id,
            elapsed,
            total,
            written,
            skipped_no_snapshot,
            errors,
        )
        _set_task_status("admin_snapshots_history_record", "ok", res)
        return res
    finally:
        session.close()


@shared_task(
    soft_time_limit=3600,
    time_limit=4200,
)
@task_run("admin_repair_stage_history_async", lock_key=lambda **_: "repair_stage_history", lock_ttl_seconds=4500)
def repair_stage_history_async(days: int = 3650, symbol: Optional[str] = None) -> dict:
    """Async Celery wrapper around StageQualityService.repair_stage_history_window."""
    session = SessionLocal()
    try:
        from backend.services.market.stage_quality_service import StageQualityService
        svc = StageQualityService()
        result = svc.repair_stage_history_window(session, days=days, symbol=symbol)
        session.commit()
        return result
    except Exception as exc:
        logger.exception("repair_stage_history_async failed: %s", exc)
        session.rollback()
        return {"status": "error", "error": str(exc)}
    finally:
        session.close()
