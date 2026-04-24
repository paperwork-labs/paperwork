"""medallion: silver"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from backend.models import MarketSnapshot
from backend.models.market_data import MarketSnapshotHistory

logger = logging.getLogger(__name__)

VALID_STAGE_LABELS = {
    "1", "1A", "1B",
    "2A", "2B", "2B(RS-)", "2C",
    "3", "3A", "3B",
    "4", "4A", "4B", "4C",
    "UNKNOWN",
}


def normalize_stage_label(stage_label: Any) -> Optional[str]:
    """Normalize a raw stage label string to its canonical form.

    Shared across stage quality, stage run derivation, and repair operations.
    Returns None for unrecognized/empty labels.
    """
    raw = str(stage_label or "").strip().upper()
    if not raw:
        return None
    if raw in ("1A", "1B"):
        return raw
    if "2A" in raw:
        return "2A"
    if "2B(RS-)" in raw:
        return "2B(RS-)"
    if "2B" in raw:
        return "2B"
    if "2C" in raw:
        return "2C"
    if raw in {"2", "STAGE 2"}:
        return "2A"
    if raw in ("3A", "3B"):
        return raw
    if raw in ("4A", "4B", "4C"):
        return raw
    if raw in {"1", "STAGE 1"} or raw.endswith(" 1"):
        return "1"
    if raw in {"3", "STAGE 3"} or raw.endswith(" 3"):
        return "3"
    if raw in {"4", "STAGE 4"} or raw.endswith(" 4"):
        return "4"
    if raw == "UNKNOWN":
        return "UNKNOWN"
    return None


class StageQualityService:
    """Stage quality auditing and history repair.

    Pure service — does not depend on ``MarketDataService`` at runtime.
    """

    def stage_quality_summary(
        self,
        db: Session,
        *,
        lookback_days: int = 120,
    ) -> Dict[str, Any]:
        lookback_days = max(7, min(int(lookback_days), 3650))
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        MS = MarketSnapshot
        snap_type = MS.analysis_type == "technical_snapshot"
        lab = func.upper(func.trim(func.coalesce(MS.stage_label, "")))
        prev_trim = func.trim(func.coalesce(MS.previous_stage_label, ""))

        total = int(db.query(func.count()).filter(snap_type).scalar() or 0)

        stage_counter: Counter[str] = Counter()
        invalid_stage_count = 0
        unknown_count = 0
        empty_label_count = 0
        for label_val, cnt in (
            db.query(lab, func.count()).filter(snap_type).group_by(lab).all()
        ):
            stage_raw = str(label_val or "").strip().upper()
            n = int(cnt)
            if stage_raw == "":
                # Null / empty label means "not yet computed" — an unknown state,
                # not an invalid one. Per ``no-silent-fallback.mdc`` we still
                # surface the count via ``empty_label_count`` so ops can see
                # the warmup / gap explicitly; we do NOT count it as invalid
                # (which would pin the dim to critical forever while warmups
                # populate) nor as silently green.
                empty_label_count += n
                unknown_count += n
            elif stage_raw in VALID_STAGE_LABELS:
                stage_counter[stage_raw] += n
                if stage_raw == "UNKNOWN":
                    unknown_count += n
            else:
                invalid_stage_count += n

        invalid_current_days_count = int(
            db.query(func.count())
            .filter(
                snap_type,
                lab != "",
                lab != "UNKNOWN",
                or_(MS.current_stage_days.is_(None), MS.current_stage_days < 1),
            )
            .scalar()
            or 0
        )

        invalid_previous_link_count = int(
            db.query(func.count())
            .filter(
                snap_type,
                or_(
                    and_(prev_trim != "", MS.previous_stage_days.is_(None)),
                    and_(prev_trim == "", MS.previous_stage_days.isnot(None)),
                ),
            )
            .scalar()
            or 0
        )

        stale_stage_count = int(
            db.query(func.count())
            .filter(
                snap_type,
                or_(MS.as_of_timestamp.is_(None), MS.as_of_timestamp < cutoff),
            )
            .scalar()
            or 0
        )

        recent_rows = (
            db.query(
                MarketSnapshotHistory.symbol,
                MarketSnapshotHistory.as_of_date,
                MarketSnapshotHistory.stage_label,
                MarketSnapshotHistory.current_stage_days,
            )
            .filter(
                MarketSnapshotHistory.analysis_type == "technical_snapshot",
                MarketSnapshotHistory.as_of_date >= cutoff,
            )
            .order_by(
                MarketSnapshotHistory.symbol.asc(),
                MarketSnapshotHistory.as_of_date.asc(),
            )
            .all()
        )

        monotonicity_issues = 0
        history_rows_checked = 0
        unknown_stage_days_count = 0
        by_symbol: Dict[str, List[tuple[datetime, Any, Any]]] = {}
        for symbol, as_of_date, stage_label, current_days in recent_rows:
            by_symbol.setdefault(str(symbol or "").upper(), []).append(
                (as_of_date, stage_label, current_days)
            )

        for series in by_symbol.values():
            prev_norm: Optional[str] = None
            prev_days_val: Optional[int] = None
            prev_dt: Optional[datetime] = None
            for dt, stage_label, current_days in series:
                norm = normalize_stage_label(stage_label)
                if norm is None:
                    continue
                history_rows_checked += 1
                # Distinguish three input states for ``current_stage_days``:
                #   None           -> "not yet populated" (warmup / write gap) — NOT drift
                #   int < 1        -> actual corruption (0, negative) — drift
                #   int >= 1       -> valid counter, used for continuity check
                # Per ``no-silent-fallback.mdc``: nulls surface as
                # ``unknown_stage_days_count`` so ops can see the gap, but they
                # don't falsely trigger a "critical" drift verdict — a missing
                # counter is an unknown state, not a broken one.
                if current_days is None:
                    unknown_stage_days_count += 1
                    prev_norm = norm
                    prev_days_val = None
                    prev_dt = dt
                    continue
                try:
                    cur_days = int(current_days)
                except Exception:
                    cur_days = 0
                if cur_days < 1:
                    monotonicity_issues += 1
                elif prev_norm is not None and prev_days_val is not None and prev_dt is not None:
                    cal_gap = (dt - prev_dt).days if dt and prev_dt else 0
                    if cal_gap == 1:
                        if norm == prev_norm and cur_days != prev_days_val + 1:
                            monotonicity_issues += 1
                        if norm != prev_norm and cur_days != 1:
                            monotonicity_issues += 1
                    else:
                        if norm == prev_norm and cur_days <= prev_days_val:
                            monotonicity_issues += 1
                        if norm != prev_norm and cur_days < 1:
                            monotonicity_issues += 1
                prev_norm = norm
                prev_days_val = cur_days if cur_days >= 1 else None
                prev_dt = dt

        known_count = total - unknown_count - invalid_stage_count
        unknown_rate = (unknown_count / total) if total else 0.0
        known_rate = (known_count / total) if total else 0.0

        warning = (
            invalid_stage_count > 0
            or invalid_current_days_count > 0
            or invalid_previous_link_count > 0
            or monotonicity_issues > 0
            or unknown_rate > 0.35
        )
        status = "warning" if warning else "ok"

        return {
            "status": status,
            "window_days": lookback_days,
            "total_symbols": total,
            "known_count": known_count,
            "unknown_count": unknown_count,
            "empty_label_count": empty_label_count,
            "known_rate": round(known_rate, 4),
            "unknown_rate": round(unknown_rate, 4),
            "invalid_stage_count": invalid_stage_count,
            "invalid_current_days_count": invalid_current_days_count,
            "invalid_previous_link_count": invalid_previous_link_count,
            "monotonicity_issues": monotonicity_issues,
            "unknown_stage_days_count": unknown_stage_days_count,
            "stage_history_rows_checked": history_rows_checked,
            "stale_stage_count": stale_stage_count,
            "stage_counts": {
                k: int(stage_counter.get(k, 0))
                for k in sorted(VALID_STAGE_LABELS)
            },
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def repair_stage_history_window(
        self,
        db: Session,
        *,
        days: int = 120,
        symbol: str | None = None,
    ) -> Dict[str, Any]:
        days = max(7, min(int(days), 3650))
        target_symbol = (symbol or "").strip().upper() or None
        # None: full-universe DISTINCT path; set: repair only that symbol as a one-element list.

        # When repairing a single symbol we don't need the universe scan —
        # short-circuit to avoid a multi-second DISTINCT on a 600k-row
        # table every time someone repairs one ticker.
        if target_symbol:
            symbols = [target_symbol]
        else:
            # Index-only scan on (analysis_type, symbol) introduced in
            # migration 0022; previously this was the query that R39
            # killed with a 30s statement_timeout.
            query = (
                db.query(MarketSnapshotHistory.symbol)
                .filter(MarketSnapshotHistory.analysis_type == "technical_snapshot")
                .distinct()
                .order_by(MarketSnapshotHistory.symbol.asc())
            )
            symbols = [s for (s,) in query.all()]

        touched_rows = 0
        touched_symbols = 0
        for idx, sym in enumerate(symbols, 1):
            rows = (
                db.query(MarketSnapshotHistory)
                .filter(
                    MarketSnapshotHistory.analysis_type == "technical_snapshot",
                    MarketSnapshotHistory.symbol == sym,
                )
                .order_by(MarketSnapshotHistory.as_of_date.desc())
                .limit(days)
                .all()
            )
            if not rows:
                continue
            rows = list(reversed(rows))

            cur_stage: Optional[str] = None
            cur_days = 0
            prev_stage: Optional[str] = None
            prev_days_val: Optional[int] = None
            updated_for_symbol = False

            for row in rows:
                norm = normalize_stage_label(getattr(row, "stage_label", None))
                if norm is None:
                    continue
                if norm == "UNKNOWN":
                    cur_stage = None
                    cur_days = 0
                    prev_stage = None
                    prev_days_val = None
                    row.current_stage_days = None
                    row.previous_stage_label = None
                    row.previous_stage_days = None
                    touched_rows += 1
                    updated_for_symbol = True
                    continue
                if cur_stage == norm:
                    cur_days += 1
                else:
                    prev_stage = cur_stage
                    prev_days_val = cur_days if cur_stage is not None else None
                    cur_stage = norm
                    cur_days = 1
                row.current_stage_days = cur_days
                row.previous_stage_label = prev_stage
                row.previous_stage_days = prev_days_val
                touched_rows += 1
                updated_for_symbol = True

            if updated_for_symbol:
                touched_symbols += 1
                snap = (
                    db.query(MarketSnapshot)
                    .filter(
                        MarketSnapshot.analysis_type == "technical_snapshot",
                        MarketSnapshot.symbol == sym,
                    )
                    .first()
                )
                if snap is not None:
                    target_norm = normalize_stage_label(
                        getattr(snap, "stage_label", None)
                    )
                    candidate = None
                    if target_norm is not None:
                        for row in reversed(rows):
                            row_norm = normalize_stage_label(
                                getattr(row, "stage_label", None)
                            )
                            if row_norm == target_norm:
                                candidate = row
                                break
                    if candidate is None:
                        for row in reversed(rows):
                            row_norm = normalize_stage_label(
                                getattr(row, "stage_label", None)
                            )
                            if row_norm is not None and row_norm != "UNKNOWN":
                                candidate = row
                                break
                    if candidate is not None:
                        snap.current_stage_days = getattr(candidate, "current_stage_days", None)
                        snap.previous_stage_label = getattr(candidate, "previous_stage_label", None)
                        snap.previous_stage_days = getattr(candidate, "previous_stage_days", None)

            if idx % 50 == 0:
                db.commit()

        db.commit()
        return {
            "window_days": days,
            "target_symbol": target_symbol,
            "total_symbols": len(symbols),
            "touched_symbols": touched_symbols,
            "touched_rows": touched_rows,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
