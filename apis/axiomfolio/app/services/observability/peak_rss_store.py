"""Redis aggregation for ``PeakRssMiddleware`` sampled per-request memory metrics.

Key layout (TTL 24h on each per-endpoint zset)::

  apiv1:obs:peak_rss:{METHOD:/normalizedPath}

Each zset has score = monotonic time (``time.time()``, float) and
``member = "{peak_rss_kib:012d}:\\x00{unique}"`` so we keep the 100
most **recent** samples (trim lowest scores / oldest) and percentiles
reflect recent traffic, not the historical max.

medallion: ops
"""

from __future__ import annotations

import logging
import platform
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.api.middleware import rate_limit as rate_limit_mod

logger = logging.getLogger(__name__)

PEAK_RSS_REDIS_KEY_PREFIX: str = "apiv1:obs:peak_rss:"
_TTL_S: int = 24 * 3600
_MAX_SAMPLES: int = 100
_MEMBER_SEP: str = "\x00"
_re_invalid_k = re.compile(r"[^\w\-/.:]")

# WARN threshold: 500 MiB delta in one request (1/4 of 2 GiB box)
PEAK_RSS_WARN_DELTA_KIB: int = 500 * 1024


def ru_maxrss_raw_to_kib(ru_maxrss: int) -> int:
    """Convert ``rusage`` ``ru_maxrss`` to kibibytes (Linux: KiB, macOS: bytes)."""
    raw = int(ru_maxrss)
    if platform.system() == "Darwin":
        return max(0, raw // 1024)
    return max(0, raw)


def _endpoint_key_from_template(method: str, path_template: str) -> str:
    pnorm = rate_limit_mod._normalise_endpoint(path_template)  # noqa: SLF001
    pnorm = _re_invalid_k.sub("_", pnorm)
    m = (method or "GET").upper()
    return f"{PEAK_RSS_REDIS_KEY_PREFIX}{m}:{pnorm}"


def record_peak_rss_sample(redis, method: str, path_template: str, peak_rss_kib: int) -> None:
    """Push one sample; zset is capped to the 100 most recent (by time score)."""
    if redis is None:
        return
    key = _endpoint_key_from_template(method, path_template)
    tscore = float(time.time())  # sortable; no precision issues vs time_ns
    member = f"{int(max(0, peak_rss_kib)):012d}{_MEMBER_SEP}{uuid.uuid4().hex}"
    try:
        redis.zadd(key, {member: tscore})  # type: ignore[union-attr]
        n = int(redis.zcard(key) or 0)  # type: ignore[union-attr]
        if n > _MAX_SAMPLES:
            # Lowest rank = lowest score = oldest time
            redis.zremrangebyrank(key, 0, n - _MAX_SAMPLES - 1)  # type: ignore[union-attr]
        redis.expire(key, _TTL_S)  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        logger.warning("peak_rss: redis write/trim failed for %s: %s", key, e, exc_info=True)


def _parse_members_for_kib(redis, key: str) -> List[int]:
    out: List[int] = []
    try:
        items = redis.zrange(key, 0, -1)  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        logger.warning("peak_rss: zrange failed for %s: %s", key, e, exc_info=True)
        return out
    if not items:
        return out
    for m in items:
        try:
            s = m.decode() if isinstance(m, (bytes, bytearray)) else str(m)
            kpart = s.split(_MEMBER_SEP, 1)[0]
            out.append(int(kpart, 10))
        except (ValueError, TypeError) as e:
            logger.warning("peak_rss: bad member in %s: %s (%s)", key, m, e)
    return out


def _pctl(sorted_vals: List[int], p: float) -> int:
    if not sorted_vals:
        return 0
    n = len(sorted_vals)
    if n == 1:
        return int(sorted_vals[0])
    k = (n - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, n - 1)
    d0, d1 = float(sorted_vals[f]), float(sorted_vals[c])
    if f == c:
        return int(d0)
    return int(d0 + (k - f) * (d1 - d0))


def _scan_peak_rss_key_names(redis) -> List[str]:
    out: List[str] = []
    try:
        for bkey in redis.scan_iter(match=f"{PEAK_RSS_REDIS_KEY_PREFIX}*", count=500):  # type: ignore[union-attr]
            out.append(
                bkey.decode() if isinstance(bkey, (bytes, bytearray)) else str(bkey)
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("peak_rss: redis scan failed: %s", e, exc_info=True)
        raise
    return out


def get_hottest_endpoints_aggregated(redis) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Return ``(hottest_list, error_code)`` — error is non-None on fatal Redis.

    The list is the top-10 routes by max ``peak_rss`` (Kib) in the sample window, descending.
    For each route: ``p50`` / ``p95`` in MiB, ``max`` in MiB, ``samples`` = count of points.
    """
    if redis is None:
        return None, "redis_unreachable"
    try:
        keys = _scan_peak_rss_key_names(redis)
    except Exception:
        return None, "redis_unreachable"

    rows: List[Dict[str, Any]] = []
    for k in keys:
        vals = _parse_members_for_kib(redis, k)
        if not vals:
            continue
        sv = sorted(int(x) for x in vals)
        route = k[len(PEAK_RSS_REDIS_KEY_PREFIX) :]
        p50 = _pctl(sv, 50.0)
        p95 = _pctl(sv, 95.0)
        mx = int(sv[-1])
        rows.append(
            {
                "route": route,
                "samples": len(sv),
                "p50_peak_mb": int(round(p50 / 1024.0)) if p50 else 0,
                "p95_peak_mb": int(round(p95 / 1024.0)) if p95 else 0,
                "max_peak_mb": int(round(mx / 1024.0)) if mx else 0,
            }
        )
    rows.sort(key=lambda r: int(r.get("max_peak_mb", 0)), reverse=True)
    return rows[:10], None
