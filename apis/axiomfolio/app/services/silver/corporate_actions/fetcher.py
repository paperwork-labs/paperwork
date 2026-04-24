"""Pull corporate actions from FMP and upsert into ``corporate_actions``.

Endpoints used (FMP API v3):

* ``/historical-price-full/stock_split/{symbol}`` -- forward + reverse splits
* ``/historical-price-full/stock_dividend/{symbol}`` -- cash + stock dividends

Mergers / spinoffs / name changes are NOT pulled here. v1 admits them
through the ``MANUAL`` source via the admin API; pulling them
generically requires the ``$50/mo`` FMP plan or a Polygon corporate
actions endpoint and is out of scope for this PR. The
:class:`CorporateActionApplier` already routes by action_type so the
manual rows apply through the same path.

Idempotency
-----------
The ``corporate_actions`` table has ``UNIQUE(symbol, action_type, ex_date)``.
:meth:`_upsert` checks for an existing row by that triple and returns
``False`` (no insert) when one exists. Re-running the fetcher for the
same symbols / window therefore never creates duplicates.

Error model
-----------
Per-symbol HTTP failures are caught, logged, and counted under
``symbols_errored``. The fetcher never raises out of
:meth:`fetch_for_symbols` -- one bad symbol must not abort the whole
universe sweep. Caller (the Celery task) reads the counters and
records them on ``JobRun.counters`` so admin / health surfaces can see
the failure mode without having to grep logs.

medallion: silver
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Optional, Sequence

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.corporate_action import (
    CorporateAction,
    CorporateActionSource,
    CorporateActionStatus,
    CorporateActionType,
)

logger = logging.getLogger(__name__)


_FMP_BASE = "https://financialmodelingprep.com/api/v3"
_FMP_TIMEOUT_SECONDS = 30


@dataclass
class FetchReport:
    """Counters returned to the Celery task for ``JobRun.counters``."""

    symbols_total: int = 0
    symbols_fetched: int = 0
    symbols_errored: int = 0
    actions_inserted: int = 0
    actions_skipped_duplicate: int = 0
    errored_symbols: List[str] = field(default_factory=list)


class CorporateActionFetcher:
    """Fetch + upsert corporate actions for a list of symbols.

    Construct with the active SQLAlchemy session; the fetcher does not
    commit. The caller (Celery task or test) controls the transaction
    boundary so the fetch can be rolled back atomically with downstream
    work.
    """

    def __init__(
        self,
        session: Session,
        *,
        api_key: Optional[str] = None,
        http_get: Optional[Callable[..., requests.Response]] = None,
    ) -> None:
        self.session = session
        # Allow tests to inject a stub; default to the real key from settings.
        self.api_key = api_key if api_key is not None else getattr(settings, "FMP_API_KEY", None)
        self._http_get = http_get or requests.get

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_for_symbols(
        self,
        symbols: Sequence[str],
        since_date: date,
    ) -> FetchReport:
        """Pull splits + dividends for every symbol with ex_date >= since_date.

        Errors per-symbol are isolated (logged + counted) so one bad
        provider response can't poison the whole sweep.
        """
        report = FetchReport(symbols_total=len(symbols))
        if not symbols:
            return report
        if not self.api_key:
            # Fail-loud per no-silent-fallback.mdc: an unconfigured key is
            # an operator misconfiguration, not a "skip silently" condition.
            logger.error(
                "CorporateActionFetcher: FMP_API_KEY not set; refusing to "
                "silently produce zero actions for %d symbols",
                len(symbols),
            )
            report.symbols_errored = len(symbols)
            report.errored_symbols = list(symbols)
            return report

        for symbol in symbols:
            try:
                self._fetch_one(symbol, since_date, report)
                report.symbols_fetched += 1
            except Exception as exc:  # noqa: BLE001 -- per-symbol isolation
                report.symbols_errored += 1
                report.errored_symbols.append(symbol)
                logger.warning(
                    "CorporateActionFetcher: failed for %s: %s",
                    symbol,
                    exc,
                )
        return report

    # ------------------------------------------------------------------
    # Per-symbol pipeline
    # ------------------------------------------------------------------

    def _fetch_one(
        self,
        symbol: str,
        since_date: date,
        report: FetchReport,
    ) -> None:
        for payload in self._fetch_fmp_splits(symbol):
            action = _split_payload_to_action(symbol, payload, since_date)
            if action is None:
                continue
            if self._upsert(action):
                report.actions_inserted += 1
            else:
                report.actions_skipped_duplicate += 1

        for payload in self._fetch_fmp_dividends(symbol):
            action = _dividend_payload_to_action(symbol, payload, since_date)
            if action is None:
                continue
            if self._upsert(action):
                report.actions_inserted += 1
            else:
                report.actions_skipped_duplicate += 1

    def _upsert(self, action: CorporateAction) -> bool:
        """Insert ``action`` unless a matching row already exists.

        Match key: (symbol, action_type, ex_date) -- mirrors the
        ``UniqueConstraint`` on the table. Returns True if a new row
        was inserted, False if an equivalent row was already present.

        Note: we don't update existing rows. Provider corrections are
        rare; the operator can delete + re-fetch via the admin API if
        a real correction is needed. Silently overwriting historical
        ``status`` / ``error_message`` columns would erase the audit
        trail.
        """
        existing = self.session.execute(
            select(CorporateAction.id).where(
                CorporateAction.symbol == action.symbol,
                CorporateAction.action_type == action.action_type,
                CorporateAction.ex_date == action.ex_date,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return False
        self.session.add(action)
        self.session.flush()
        return True

    # ------------------------------------------------------------------
    # FMP transport
    # ------------------------------------------------------------------

    def _fetch_fmp_splits(self, symbol: str) -> List[Dict[str, Any]]:
        url = f"{_FMP_BASE}/historical-price-full/stock_split/{symbol}"
        return self._fetch_fmp(url, symbol, "historical")

    def _fetch_fmp_dividends(self, symbol: str) -> List[Dict[str, Any]]:
        url = f"{_FMP_BASE}/historical-price-full/stock_dividend/{symbol}"
        return self._fetch_fmp(url, symbol, "historical")

    def _fetch_fmp(self, url: str, symbol: str, payload_key: str) -> List[Dict[str, Any]]:
        response = self._http_get(
            url,
            params={"apikey": self.api_key},
            timeout=_FMP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json() or {}
        if isinstance(body, list):
            # Some FMP endpoints return a bare list when there are no events.
            return body
        items = body.get(payload_key) or []
        if not isinstance(items, list):
            logger.debug(
                "FMP %s returned non-list under %r for %s; got %r",
                url,
                payload_key,
                symbol,
                type(items).__name__,
            )
            return []
        return items


# ---------------------------------------------------------------------------
# Payload -> CorporateAction translation
# ---------------------------------------------------------------------------


def _parse_iso_date(raw: Any) -> Optional[date]:
    if not raw:
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def _decimal_or_none(raw: Any) -> Optional[Decimal]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, Decimal):
        return raw
    try:
        if isinstance(raw, float):
            return Decimal(str(raw))
        return Decimal(raw)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _split_payload_to_action(
    symbol: str,
    payload: Dict[str, Any],
    since_date: date,
) -> Optional[CorporateAction]:
    """Translate an FMP split row into a ``CorporateAction``.

    FMP split payload shape::

        {
            "date": "2022-08-25",
            "label": "August 25, 22",
            "numerator": 20.0,
            "denominator": 1.0
        }

    A ``numerator < denominator`` indicates a reverse split.
    """
    ex_date = _parse_iso_date(payload.get("date"))
    if ex_date is None or ex_date < since_date:
        return None

    num = _decimal_or_none(payload.get("numerator"))
    den = _decimal_or_none(payload.get("denominator"))
    if num is None or den is None or den == 0:
        logger.debug(
            "Skipping malformed FMP split for %s on %s: %r",
            symbol,
            ex_date,
            payload,
        )
        return None

    action_type = (
        CorporateActionType.REVERSE_SPLIT if num < den else CorporateActionType.SPLIT
    )

    return CorporateAction(
        symbol=symbol.upper(),
        action_type=action_type.value,
        ex_date=ex_date,
        ratio_numerator=num,
        ratio_denominator=den,
        source=CorporateActionSource.FMP.value,
        source_ref=str(payload.get("label") or ""),
        status=CorporateActionStatus.PENDING.value,
        ohlcv_adjusted=False,
    )


def _dividend_payload_to_action(
    symbol: str,
    payload: Dict[str, Any],
    since_date: date,
) -> Optional[CorporateAction]:
    """Translate an FMP dividend row into a ``CorporateAction``.

    FMP dividend payload shape::

        {
            "date": "2024-02-15",
            "label": "February 15, 24",
            "adjDividend": 0.24,
            "dividend": 0.24,
            "recordDate": "2024-02-12",
            "paymentDate": "2024-03-14",
            "declarationDate": "2024-02-01"
        }

    All FMP "dividend" rows are cash dividends. Stock dividends arrive
    on the splits endpoint (with non-integer ratios).
    """
    ex_date = _parse_iso_date(payload.get("date"))
    if ex_date is None or ex_date < since_date:
        return None

    cash = _decimal_or_none(payload.get("dividend")) or _decimal_or_none(
        payload.get("adjDividend")
    )
    if cash is None or cash <= 0:
        logger.debug(
            "Skipping zero / malformed FMP dividend for %s on %s: %r",
            symbol,
            ex_date,
            payload,
        )
        return None

    return CorporateAction(
        symbol=symbol.upper(),
        action_type=CorporateActionType.CASH_DIVIDEND.value,
        ex_date=ex_date,
        record_date=_parse_iso_date(payload.get("recordDate")),
        payment_date=_parse_iso_date(payload.get("paymentDate")),
        declaration_date=_parse_iso_date(payload.get("declarationDate")),
        cash_amount=cash,
        cash_currency="USD",  # FMP returns USD; multi-currency out of scope.
        source=CorporateActionSource.FMP.value,
        source_ref=str(payload.get("label") or ""),
        status=CorporateActionStatus.PENDING.value,
        ohlcv_adjusted=False,
    )
