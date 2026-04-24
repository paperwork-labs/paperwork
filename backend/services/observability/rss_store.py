"""Redis-backed peak RSS (resident set) observability for API requests.

Storage (UTC hour bucket ``YYYYMMDDHH``; TTL 72h on all keys):
  - ``apiv1:obs:rss:{bucket}`` — sorted set, member ``METHOD:/path``,
    score = peak process RSS **delta** (bytes) for that template; ZADD with ``GT`` when
    the server supports it, else a plain ZADD (best effort).
  - ``apiv1:obs:rss:log:{bucket}`` — capped list of JSON lines for p50/p95/p99.
  - ``apiv1:obs:rss:count:{bucket}`` — request counter (INCR).

No PII: only method + path template.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, DefaultDict, Dict, List, Optional, Tuple

from backend.api.middleware import rate_limit as rate_limit_mod

logger = logging.getLogger(__name__)

_RSS_TTL_S = 72 * 3600
_RSS_LOG_MAX = 50_000

_RSS_DEGRADE: Dict[str, Any] = {
    "count": 0,
    "last_error": None,
    "last_at": None,
}

KEY_PREFIX = "apiv1:obs:rss"


def maxrss_to_bytes(ru_maxrss: int) -> int:
    """Normalize ``resource.getrusage`` maxrss to bytes (Linux: KiB, macOS: bytes)."""
    n = int(ru_maxrss)
    if sys.platform == "darwin":
        return n
    return n * 1024


def _hour_bucket_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H")


def _zkey(bucket: str) -> str:
    return f"{KEY_PREFIX}:{bucket}"


def _logkey(bucket: str) -> str:
    return f"{KEY_PREFIX}:log:{bucket}"


def _countkey(bucket: str) -> str:
    return f"{KEY_PREFIX}:count:{bucket}"


def _record_degradation(exc: Exception) -> None:
    _RSS_DEGRADE["count"] = int(_RSS_DEGRADE.get("count", 0)) + 1
    _RSS_DEGRADE["last_error"] = f"{type(exc).__name__}: {exc}"
    _RSS_DEGRADE["last_at"] = datetime.now(timezone.utc).isoformat()
    logger.warning("rss observability: redis write failed (fail open): %s", exc, exc_info=True)


def rss_redis_degradation_snapshot() -> Dict[str, Any]:
    return dict(_RSS_DEGRADE)


def _percentile_from_sorted(sorted_bytes: List[int], p: float) -> float:
    if not sorted_bytes:
        return 0.0
    n = len(sorted_bytes)
    if n == 1:
        return float(sorted_bytes[0])
    k = (n - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, n - 1)
    d0, d1 = float(sorted_bytes[f]), float(sorted_bytes[c])
    if f == c:
        return d0
    return d0 + (k - f) * (d1 - d0)


def _percentile(values: List[int], p: float) -> float:
    if not values:
        return 0.0
    return _percentile_from_sorted(sorted(values), p)


def record_request_rss_peak(redis, method: str, path_template: str, start_bytes: int, end_bytes: int) -> None:
    """Persist maxrss growth for this request (``end - start`` bytes, floored at 0)."""
    if redis is None:
        return
    method_u = (method or "GET").upper()
    try:
        delta = max(0, int(end_bytes) - int(start_bytes))
    except Exception as e:
        logger.warning("rss observability: invalid maxrss start=%s end=%s: %s", start_bytes, end_bytes, e)
        return

    pnorm = rate_limit_mod._normalise_endpoint(path_template)
    member = f"{method_u}:{pnorm}"
    row = json.dumps({"m": method_u, "p": pnorm, "d": delta}, separators=(",", ":"), sort_keys=True)
    bucket = _hour_bucket_utc()
    zkey, lkey, ckey = _zkey(bucket), _logkey(bucket), _countkey(bucket)

    try:
        pipe = redis.pipeline()
        try:
            pipe.zadd(zkey, {member: float(delta)}, gt=True)
        except TypeError:
            pipe.zadd(zkey, {member: float(delta)})
        pipe.rpush(lkey, row)
        pipe.ltrim(lkey, -_RSS_LOG_MAX, -1)
        pipe.incr(ckey)
        for k in (zkey, lkey, ckey):
            pipe.expire(k, _RSS_TTL_S)
        pipe.execute()
    except Exception as e:
        _record_degradation(e)


def _read_log_for_bucket(redis, bucket: str) -> List[Dict[str, Any]]:
    lkey = _logkey(bucket)
    try:
        raw = redis.lrange(lkey, 0, -1)
    except Exception as e:
        logger.warning("rss observability: log read failed for %s: %s", lkey, e)
        return []
    out: List[Dict[str, Any]] = []
    for line in raw:
        s = line.decode() if isinstance(line, (bytes, bytearray)) else str(line)
        try:
            d = json.loads(s)
            if "m" in d and "p" in d and "d" in d:
                out.append(d)
        except json.JSONDecodeError:
            continue
    return out


def _read_count(redis, bucket: str) -> int:
    try:
        ckey = _countkey(bucket)
        v = redis.get(ckey)
        if v is None:
            return 0
        return int(v.decode() if isinstance(v, (bytes, bytearray)) else v)
    except Exception as e:
        logger.warning("rss observability: count read failed: %s", e)
        return 0


def _build_top_list(rows: List[Dict[str, Any]], redis, bucket: str) -> Dict[str, Any]:
    by_key: Dict[str, List[int]] = {}
    for r in rows:
        key = f'{r["m"]}:{r["p"]}'
        by_key.setdefault(key, []).append(int(r["d"]))

    items: List[Dict[str, Any]] = []
    for key, dvals in by_key.items():
        first = key.find(":")
        if first <= 0:
            method, path = "GET", key
        else:
            method, path = key[:first], key[first + 1 :]
        dlist = dvals
        p50b = _percentile(dlist, 50) / 1024.0
        p95b = _percentile(dlist, 95) / 1024.0
        p99b = _percentile(dlist, 99) / 1024.0
        items.append(
            {
                "path": path,
                "method": method,
                "count": len(dlist),
                "p50_rss_kb": round(p50b, 2),
                "p95_rss_kb": round(p95b, 2),
                "p99_rss_kb": round(p99b, 2),
            }
        )
    items.sort(key=lambda x: x["p99_rss_kb"], reverse=True)
    top_10 = items[:10]
    wcount = _read_count(redis, bucket)
    snap = rss_redis_degradation_snapshot()
    return {
        "top_rss_endpoints": top_10,
        "worker_request_count_last_hour": wcount,
        "rss_observability": {
            "available": True,
            "redis_degraded": snap["count"] > 0,
            "redis_degrade_total": snap["count"],
        },
    }


def get_rss_health_payload(redis) -> Dict[str, Any]:
    """Additive fields for ``/api/v1/market-data/admin/health``."""
    if redis is None:
        return {
            "top_rss_endpoints": [],
            "worker_request_count_last_hour": 0,
            "rss_observability": {
                "available": False,
                "reason": "redis_unconfigured",
            },
        }
    bucket = _hour_bucket_utc()
    rows = _read_log_for_bucket(redis, bucket)
    return _build_top_list(rows, redis, bucket)


def get_rss_cli_table(redis, hours: int, top_n: int) -> str:
    """Text table: endpoints ranked by p99 delta RSS (KiB) across recent UTC hours."""
    if hours < 1 or top_n < 1:
        return "hours and top_n must be positive.\n"
    if redis is None:
        return "Redis is not configured (REDIS_URL missing).\n"

    from collections import defaultdict

    agg: DefaultDict[Tuple[str, str], List[int]] = defaultdict(list)
    now = datetime.now(timezone.utc)
    for h in range(hours):
        dt = now - timedelta(hours=h)
        b = dt.strftime("%Y%m%d%H")
        for r in _read_log_for_bucket(redis, b):
            k = (str(r["m"]), str(r["p"]))
            agg[k].append(int(r["d"]))

    if not agg:
        return f"No RSS samples in the last {hours} hour(s).\n"

    lines_out: List[Tuple[Tuple[str, str], int, int, int, int, int, int, float]] = []
    for (method, path), dvals in agg.items():
        n = len(dvals)
        s = sorted(dvals)
        p50k = int(_percentile_from_sorted(s, 50.0) / 1024.0)
        p95k = int(_percentile_from_sorted(s, 95.0) / 1024.0)
        p99k = int(_percentile_from_sorted(s, 99.0) / 1024.0)
        maxk = s[-1] // 1024
        sumk = sum(s) // 1024
        lines_out.append(((method, path), n, p50k, p95k, p99k, maxk, sumk, float(p99k)))
    lines_out.sort(key=lambda t: t[7], reverse=True)

    buf: List[str] = [
        f"Top {top_n} by p99 peak RSS delta (KiB) — last {hours} UTC hour(s)\n",
        f"{'endpoint':<50}  {'n':>5}  {'p50':>5}  {'p95':>5}  {'p99':>5}  {'max':>5}  {'sum':>6}\n",
        "-" * 90 + "\n",
    ]
    for row in lines_out[:top_n]:
        (method, path), n, p50k, p95k, p99k, maxk, sumk, _p99f = row
        ep = f"{method}:{path}"[:48]
        buf.append(
            f"{ep:<50}  {n:5d}  {p50k:5d}  {p95k:5d}  {p99k:5d}  {maxk:5d}  {sumk:6d}\n"
        )
    return "".join(buf)
