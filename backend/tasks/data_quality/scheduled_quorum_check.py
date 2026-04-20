"""
Scheduled Cross-Provider Quorum Sweep
=====================================

Hourly Celery task (during US market hours) that samples ~5% of recent
``MarketSnapshot`` writes and cross-validates the latest price across
the configured market data providers via ``QuorumService``.

Why sampling? Writing one quorum-log row per market-data fetch would
dominate insert volume on a ~2,500 symbol universe refreshed every few
minutes. A 5% sample over the last hour is enough to detect provider
drift quickly while keeping the table size sane.

Idempotency: the unique index
``uq_provider_quorum_symbol_field_check_at`` (symbol, field_name,
check_at) means a duplicate same-second insert is silently dropped by
``QuorumService.persist`` rather than corrupting analytics. The task
floors ``check_at`` to the current second and uses the same value for
every row in the run, so a retry within the same second is a NOOP.

This module is provider-shape-aware but indicator-engine-blind: it
only READS provider quotes, never writes to ``MarketSnapshot`` /
``MarketSnapshotHistory`` / ``PriceData``. The DANGER ZONE engines
remain untouched.
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from celery import shared_task

from backend.database import SessionLocal
from backend.models.market_data import MarketSnapshot
from backend.services.data_quality import QuorumService
from backend.services.data_quality.tolerances import DEFAULT_QUORUM_THRESHOLD
from backend.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


# Defaults match the JobTemplate kwargs in ``backend/tasks/job_catalog.py``.
DEFAULT_SAMPLE_PCT = 0.05
MAX_SAMPLE_SIZE = 50
DEFAULT_LOOKBACK_MINUTES = 60


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def _select_sample(
    db,
    lookback_minutes: int,
    sample_pct: float,
    max_sample: int,
    *,
    rng: Optional[random.Random] = None,
) -> List[str]:
    """Pull recent symbols from ``market_snapshot`` and downsample.

    We use ``analysis_timestamp`` (when the snapshot was written) rather
    than ``as_of_timestamp`` (market-data as-of) because the question
    "what did we just write?" maps to the former.
    """
    rng = rng or random
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)

    rows = (
        db.query(MarketSnapshot.symbol)
        .filter(MarketSnapshot.analysis_timestamp >= cutoff)
        .group_by(MarketSnapshot.symbol)
        .all()
    )
    universe = sorted({row[0] for row in rows if row[0]})
    if not universe:
        return []

    target = max(1, int(math.ceil(len(universe) * sample_pct)))
    target = min(target, max_sample, len(universe))
    return rng.sample(universe, target)


# ---------------------------------------------------------------------------
# Provider fan-out
# ---------------------------------------------------------------------------


async def _gather_provider_quotes(
    symbols: List[str],
) -> Dict[str, Dict[str, Optional[Decimal]]]:
    """Fan out ``get_quotes`` across configured providers.

    Returns ``{symbol: {provider_name: Decimal_or_None}}``. A provider
    that raises is recorded as ``None`` for every symbol it was asked
    about -- "no value" is itself a data point for the quorum check.

    Imports happen inside the function so that test runs that monkey-
    patch this function don't pay the import cost of yfinance / fmpsdk.
    """
    from backend.services.market.providers import (
        FMPProvider,
        YFinanceProvider,
    )

    providers = []
    for cls in (YFinanceProvider, FMPProvider):
        try:
            instance = cls()
        except Exception as e:
            logger.warning("provider %s failed to construct: %s", cls.__name__, e)
            continue
        if not instance.is_available():
            logger.info("provider %s skipped (not configured)", instance.name)
            continue
        providers.append(instance)

    if not providers:
        logger.warning("scheduled_quorum_check found 0 configured providers")
        return {symbol: {} for symbol in symbols}

    async def _one(provider) -> Tuple[str, Dict[str, Optional[float]]]:
        try:
            quotes = await provider.get_quotes(symbols)
            return provider.name, quotes or {}
        except Exception as e:
            logger.warning(
                "provider %s get_quotes failed for %d symbols: %s",
                provider.name,
                len(symbols),
                e,
            )
            return provider.name, {symbol: None for symbol in symbols}

    results = await asyncio.gather(
        *(_one(provider) for provider in providers), return_exceptions=False
    )

    by_symbol: Dict[str, Dict[str, Optional[Decimal]]] = {
        symbol: {} for symbol in symbols
    }
    for provider_name, quotes in results:
        for symbol in symbols:
            raw = quotes.get(symbol)
            if raw is None:
                by_symbol[symbol][provider_name] = None
                continue
            # Provider protocol returns ``float``. We convert via
            # ``str()`` so Decimal preserves the exact provider digit
            # string rather than the binary float repr (e.g.,
            # ``Decimal(0.1)`` -> ``0.1000000000000000055511151231...``).
            try:
                by_symbol[symbol][provider_name] = Decimal(str(raw))
            except Exception as e:
                logger.warning(
                    "provider %s returned unparseable quote %r for %s: %s",
                    provider_name,
                    raw,
                    symbol,
                    e,
                )
                by_symbol[symbol][provider_name] = None
    return by_symbol


# ---------------------------------------------------------------------------
# Synchronous core (testable without Celery)
# ---------------------------------------------------------------------------


def run_quorum_check(
    *,
    sample_pct: float = DEFAULT_SAMPLE_PCT,
    max_sample: int = MAX_SAMPLE_SIZE,
    lookback_minutes: int = DEFAULT_LOOKBACK_MINUTES,
    field_name: str = "LAST_PRICE",
    threshold: Decimal = DEFAULT_QUORUM_THRESHOLD,
    rng: Optional[random.Random] = None,
) -> Dict:
    """Run one quorum-sweep pass.

    Returns a structured counters dict (per the no-silent-fallback rule):
    every symbol must end up in exactly one of the buckets and the sum
    is asserted equal to the sample size.
    """
    db = SessionLocal()
    try:
        sample = _select_sample(
            db,
            lookback_minutes=lookback_minutes,
            sample_pct=sample_pct,
            max_sample=max_sample,
            rng=rng,
        )
        if not sample:
            logger.info(
                "scheduled_quorum_check: no recent snapshots in last %d min",
                lookback_minutes,
            )
            return {
                "sampled": 0,
                "quorum_reached": 0,
                "disagreement": 0,
                "insufficient_providers": 0,
                "single_source": 0,
                "errors": 0,
                "lookback_minutes": lookback_minutes,
                "field_name": field_name,
            }

        provider_by_symbol = asyncio.run(_gather_provider_quotes(sample))

        service = QuorumService(default_threshold=threshold)
        # One ``check_at`` for the whole run -- simplifies the
        # idempotency story (the unique index keys off this).
        check_at = datetime.now(timezone.utc).replace(microsecond=0)

        counters = {
            "sampled": len(sample),
            "quorum_reached": 0,
            "disagreement": 0,
            "insufficient_providers": 0,
            "single_source": 0,
            "errors": 0,
            "lookback_minutes": lookback_minutes,
            "field_name": field_name,
            "check_at": check_at.isoformat(),
        }

        for symbol in sample:
            provider_values = provider_by_symbol.get(symbol, {})
            try:
                result = service.validate(
                    symbol=symbol,
                    field_name=field_name,
                    provider_values=provider_values
                    if provider_values
                    else {"_no_provider": None},
                    threshold=threshold,
                )
                service.persist(db, result, check_at=check_at)
                key = result.status.value.lower()
                if key in counters:
                    counters[key] += 1
            except Exception as e:
                counters["errors"] += 1
                logger.warning(
                    "quorum check failed for %s: %s", symbol, e
                )

        # No-silent-fallback: assert every sample lands in exactly one
        # bucket. If this trips in prod, the counter map is out of sync
        # with the QuorumStatus enum and we want to know loudly.
        bucket_total = (
            counters["quorum_reached"]
            + counters["disagreement"]
            + counters["insufficient_providers"]
            + counters["single_source"]
            + counters["errors"]
        )
        assert bucket_total == counters["sampled"], (
            f"counter drift: bucketed {bucket_total} != sampled "
            f"{counters['sampled']}"
        )

        db.commit()
        logger.info(
            "scheduled_quorum_check: sampled=%d quorum=%d disagreement=%d "
            "insufficient=%d single_source=%d errors=%d",
            counters["sampled"],
            counters["quorum_reached"],
            counters["disagreement"],
            counters["insufficient_providers"],
            counters["single_source"],
            counters["errors"],
        )
        return counters
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Celery entry point
# ---------------------------------------------------------------------------


@shared_task(
    name="backend.tasks.data_quality.scheduled_quorum_check.run",
    soft_time_limit=540,
    time_limit=600,
)
@task_run("data_quality_quorum_sweep")
def run(
    sample_pct: float = DEFAULT_SAMPLE_PCT,
    max_sample: int = MAX_SAMPLE_SIZE,
    lookback_minutes: int = DEFAULT_LOOKBACK_MINUTES,
) -> Dict:
    """Celery hourly entry point.

    Hard/soft time limits match the ``JobTemplate.timeout_s`` value in
    ``job_catalog.py`` (600s) so the lock TTL math stays consistent.
    """
    return run_quorum_check(
        sample_pct=sample_pct,
        max_sample=max_sample,
        lookback_minutes=lookback_minutes,
    )
