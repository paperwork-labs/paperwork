"""SymbolMasterService — point-in-time resolution + writes for the
symbol master layer.

Read API
--------

* :py:meth:`SymbolMasterService.resolve` — resolves a ticker (and
  optional ``as_of_date``) to a ``SymbolMaster`` row, walking
  ``SymbolAlias`` rows for historical lookups. Returns ``None`` when
  unknown (callers handle missing-data states explicitly per
  ``no-silent-fallback.mdc``).
* :py:meth:`SymbolMasterService.resolve_strict` — same as
  :py:meth:`resolve` but raises :class:`UnknownTickerError` on
  unknown tickers, for callers that want a hard fail.
* :py:meth:`SymbolMasterService.bulk_resolve` — convenience
  many-ticker helper for hot paths (e.g. dashboard hydration).

Write API
---------

* :py:meth:`SymbolMasterService.get_or_create_master` — idempotent
  upsert keyed on ``primary_ticker``.
* :py:meth:`SymbolMasterService.register_alias` — adds a
  ``SymbolAlias`` row (idempotent on
  ``(master, alias_ticker, valid_from)``).
* :py:meth:`SymbolMasterService.record_ticker_change` — atomic
  ticker-rename: rotates the master's ``primary_ticker``, plants a
  sticky alias for the legacy ticker, and appends a
  ``SymbolHistory`` row. Idempotent.

Multi-tenancy
-------------

The master is a global table. The service is intentionally
user-agnostic so any caller can resolve a ticker. Callers that
project user-scoped data through the master (e.g. user portfolios)
**must** keep the user filter on their own tables — the master
contributes no tenant filter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.models.symbol_master import (
    AliasSource,
    AssetClass,
    SymbolAlias,
    SymbolChangeType,
    SymbolHistory,
    SymbolMaster,
    SymbolStatus,
)


logger = logging.getLogger(__name__)


# Sentinel "beginning of time" for sticky aliases. We avoid
# ``date.min`` (year 1) because some Postgres tooling and JSON
# serializers misbehave on such extreme values. 1900-01-01 predates
# every modern security in our universe by a wide margin and round-
# trips cleanly through psycopg, JSON, and the alembic test harness.
HISTORICAL_FLOOR_DATE = date(1900, 1, 1)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SymbolMasterError(Exception):
    """Base class for symbol-master errors."""


class UnknownTickerError(SymbolMasterError):
    """Raised by :py:meth:`SymbolMasterService.resolve_strict` when no
    master row matches the given ticker / as_of date."""

    def __init__(self, ticker: str, as_of_date: Optional[date] = None) -> None:
        msg = f"Unknown ticker: {ticker!r}"
        if as_of_date is not None:
            msg += f" (as_of={as_of_date.isoformat()})"
        super().__init__(msg)
        self.ticker = ticker
        self.as_of_date = as_of_date


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TickerChangeResult:
    """Return shape for :py:meth:`SymbolMasterService.record_ticker_change`."""

    master: SymbolMaster
    alias: SymbolAlias
    history: SymbolHistory
    created_master: bool
    created_alias: bool
    created_history: bool


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SymbolMasterService:
    """Stateless service over a SQLAlchemy session.

    The session is supplied by the caller and the service never opens
    or closes it (per the iron law in ``engineering.mdc``). Commits
    are likewise the caller's responsibility — keeps transactional
    boundaries explicit at the route / task layer.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(ticker: str) -> str:
        """Tickers are stored upper-case with no surrounding whitespace.
        Doing this in one place avoids "MSFT vs msft vs ' MSFT '" bugs
        leaking into every call site."""
        return (ticker or "").strip().upper()

    def resolve(
        self, ticker: str, as_of_date: Optional[date] = None
    ) -> Optional[SymbolMaster]:
        """Resolve a ticker (optionally point-in-time) to a master row.

        Resolution order:

        1. Match against ``SymbolAlias`` (if ``as_of_date`` given,
           constrained to the half-open ``[valid_from, valid_to)``
           window; the most-recently-effective alias wins).
        2. Match against ``SymbolMaster.primary_ticker``.

        Returns ``None`` if no row matches. We deliberately do *not*
        fall back to a "best guess" here — silent fallbacks are
        forbidden (see ``no-silent-fallback.mdc``). Use
        :py:meth:`resolve_strict` if you want an exception instead.
        """
        normalized = self._normalize(ticker)
        if not normalized:
            return None

        alias_q = self.db.query(SymbolAlias).filter(
            SymbolAlias.alias_ticker == normalized
        )
        if as_of_date is not None:
            alias_q = alias_q.filter(SymbolAlias.valid_from <= as_of_date).filter(
                or_(
                    SymbolAlias.valid_to.is_(None),
                    SymbolAlias.valid_to > as_of_date,
                )
            )
        alias = alias_q.order_by(SymbolAlias.valid_from.desc()).first()
        if alias is not None:
            return self.db.get(SymbolMaster, alias.symbol_master_id)

        master = (
            self.db.query(SymbolMaster)
            .filter(SymbolMaster.primary_ticker == normalized)
            .first()
        )
        return master

    def resolve_strict(
        self, ticker: str, as_of_date: Optional[date] = None
    ) -> SymbolMaster:
        """Like :py:meth:`resolve` but raises :class:`UnknownTickerError`
        on no match."""
        master = self.resolve(ticker, as_of_date=as_of_date)
        if master is None:
            raise UnknownTickerError(self._normalize(ticker), as_of_date=as_of_date)
        return master

    def bulk_resolve(
        self, tickers: Iterable[str], as_of_date: Optional[date] = None
    ) -> dict[str, Optional[SymbolMaster]]:
        """Resolve many tickers, preserving caller's normalized keys.

        Empty / whitespace-only inputs are dropped so callers don't
        accidentally key on ``""``. The returned dict's keys are the
        *normalized* ticker strings.
        """
        out: dict[str, Optional[SymbolMaster]] = {}
        for raw in tickers:
            normalized = self._normalize(raw)
            if not normalized:
                continue
            if normalized in out:
                continue
            out[normalized] = self.resolve(normalized, as_of_date=as_of_date)
        return out

    def history_for(self, master_id: int) -> list[SymbolHistory]:
        """Return the audit ledger for a master, oldest first."""
        return (
            self.db.query(SymbolHistory)
            .filter(SymbolHistory.symbol_master_id == master_id)
            .order_by(SymbolHistory.effective_date.asc(), SymbolHistory.id.asc())
            .all()
        )

    def aliases_for(self, master_id: int) -> list[SymbolAlias]:
        """Return all aliases for a master, oldest first."""
        return (
            self.db.query(SymbolAlias)
            .filter(SymbolAlias.symbol_master_id == master_id)
            .order_by(SymbolAlias.valid_from.asc(), SymbolAlias.id.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def get_or_create_master(
        self,
        primary_ticker: str,
        *,
        asset_class: AssetClass = AssetClass.EQUITY,
        name: Optional[str] = None,
        exchange: Optional[str] = None,
        country: Optional[str] = None,
        currency: Optional[str] = None,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        gics_code: Optional[str] = None,
        cik: Optional[str] = None,
        isin: Optional[str] = None,
        figi: Optional[str] = None,
        status: SymbolStatus = SymbolStatus.ACTIVE,
    ) -> tuple[SymbolMaster, bool]:
        """Idempotent upsert keyed on ``primary_ticker``.

        Returns ``(master, created)``. When ``created`` is ``True``,
        the row was just inserted; when ``False``, an existing row
        was returned untouched (descriptive fields are *not*
        backfilled here — keeps the function side-effect-light and
        leaves enrichment to dedicated upsert calls in initial-load).
        """
        normalized = self._normalize(primary_ticker)
        if not normalized:
            raise SymbolMasterError("primary_ticker must be a non-empty string")

        existing = (
            self.db.query(SymbolMaster)
            .filter(SymbolMaster.primary_ticker == normalized)
            .first()
        )
        if existing is not None:
            return existing, False

        master = SymbolMaster(
            primary_ticker=normalized,
            asset_class=asset_class.value,
            status=status.value,
            name=name,
            exchange=exchange,
            country=country,
            currency=currency,
            sector=sector,
            industry=industry,
            gics_code=gics_code,
            cik=cik,
            isin=isin,
            figi=figi,
        )
        self.db.add(master)
        self.db.flush()
        return master, True

    def register_alias(
        self,
        master_id: int,
        alias_ticker: str,
        *,
        valid_from: date,
        source: AliasSource,
        valid_to: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> SymbolAlias:
        """Add (or fetch existing) alias on
        ``(master_id, alias_ticker, valid_from)``.

        Idempotent: calling twice with the same args returns the same
        row. Window must be valid (``valid_to is None`` OR
        ``valid_to > valid_from``).
        """
        normalized = self._normalize(alias_ticker)
        if not normalized:
            raise SymbolMasterError("alias_ticker must be a non-empty string")
        if valid_to is not None and valid_to <= valid_from:
            raise SymbolMasterError(
                "valid_to must be strictly greater than valid_from "
                f"(got valid_from={valid_from} valid_to={valid_to})"
            )

        existing = (
            self.db.query(SymbolAlias)
            .filter(
                SymbolAlias.symbol_master_id == master_id,
                SymbolAlias.alias_ticker == normalized,
                SymbolAlias.valid_from == valid_from,
            )
            .first()
        )
        if existing is not None:
            return existing

        alias = SymbolAlias(
            symbol_master_id=master_id,
            alias_ticker=normalized,
            valid_from=valid_from,
            valid_to=valid_to,
            source=source.value,
            notes=notes,
        )
        self.db.add(alias)
        self.db.flush()
        return alias

    def record_ticker_change(
        self,
        old_ticker: str,
        new_ticker: str,
        *,
        effective_date: date,
        source: AliasSource = AliasSource.TICKER_CHANGE,
        notes: Optional[str] = None,
        new_name: Optional[str] = None,
    ) -> TickerChangeResult:
        """Record a corporate ticker rename atomically.

        Steps:

        1. Resolve / create the master keyed on the *new* ticker.
        2. If the master's ``primary_ticker`` is still the old one,
           rotate it to the new one.
        3. Plant a sticky alias for the old ticker (valid from the
           historical floor, no end). This means
           ``resolve("OLD")`` keeps working forever, no matter what
           date you ask about.
        4. Append a ``SymbolHistory`` row capturing the change.

        Idempotent: rerunning with the same args reuses existing
        rows. The ``created_*`` flags on the result tell the caller
        what actually happened, which the initial-load script uses
        for accurate counters per ``no-silent-fallback.mdc``.
        """
        old_norm = self._normalize(old_ticker)
        new_norm = self._normalize(new_ticker)
        if not old_norm or not new_norm:
            raise SymbolMasterError(
                "old_ticker and new_ticker must be non-empty strings"
            )
        if old_norm == new_norm:
            raise SymbolMasterError(
                f"old_ticker and new_ticker must differ (got {old_norm!r})"
            )

        # Step 1+2: anchor on the new ticker. If a row already exists
        # under the old ticker (e.g. seeded from MarketSnapshot before
        # this rename was known), rotate it.
        master, created_master = self._anchor_master_for_rename(
            old_norm, new_norm, new_name=new_name
        )

        # Step 3: sticky alias for the old ticker. Pre-check so we can
        # report ``created_alias`` accurately (caller relies on this
        # for idempotency counters).
        pre_existing_alias = (
            self.db.query(SymbolAlias)
            .filter(
                SymbolAlias.symbol_master_id == master.id,
                SymbolAlias.alias_ticker == old_norm,
                SymbolAlias.valid_from == HISTORICAL_FLOOR_DATE,
            )
            .first()
        )
        alias = self.register_alias(
            master.id,
            old_norm,
            valid_from=HISTORICAL_FLOOR_DATE,
            valid_to=None,
            source=source,
            notes=notes,
        )
        created_alias = pre_existing_alias is None

        # Step 4: append history row, idempotent on the
        # (master, change_type, effective_date, old_value, new_value)
        # tuple so reruns don't pollute the audit ledger.
        new_value = {"primary_ticker": new_norm}
        old_value = {"primary_ticker": old_norm}

        existing_history = (
            self.db.query(SymbolHistory)
            .filter(
                SymbolHistory.symbol_master_id == master.id,
                SymbolHistory.change_type == SymbolChangeType.TICKER_CHANGE.value,
                SymbolHistory.effective_date == effective_date,
                SymbolHistory.old_value == old_value,
                SymbolHistory.new_value == new_value,
            )
            .first()
        )
        if existing_history is not None:
            history = existing_history
            created_history = False
        else:
            history = SymbolHistory(
                symbol_master_id=master.id,
                change_type=SymbolChangeType.TICKER_CHANGE.value,
                old_value=old_value,
                new_value=new_value,
                effective_date=effective_date,
                source=source.value,
            )
            self.db.add(history)
            self.db.flush()
            created_history = True

        return TickerChangeResult(
            master=master,
            alias=alias,
            history=history,
            created_master=created_master,
            created_alias=created_alias,
            created_history=created_history,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _anchor_master_for_rename(
        self,
        old_norm: str,
        new_norm: str,
        *,
        new_name: Optional[str],
    ) -> tuple[SymbolMaster, bool]:
        """Pick the right master row to anchor a ticker change on.

        Cases:

        * Master already exists under ``new_norm`` -> reuse it.
        * Master exists under ``old_norm`` -> rotate its
          ``primary_ticker`` to ``new_norm`` (UNIQUE constraint
          ensures no collision; if ``new_norm`` was also a separate
          master row, we keep the one that's already labelled
          ``new_norm`` and leave the legacy row alone — callers can
          merge them via a follow-up).
        * Neither exists -> create a fresh master keyed on
          ``new_norm``.
        """
        # Case 1: row already keyed on the new ticker.
        new_existing = (
            self.db.query(SymbolMaster)
            .filter(SymbolMaster.primary_ticker == new_norm)
            .first()
        )
        if new_existing is not None:
            if new_name and not new_existing.name:
                new_existing.name = new_name
            return new_existing, False

        # Case 2: legacy row keyed on the old ticker — rotate it.
        old_existing = (
            self.db.query(SymbolMaster)
            .filter(SymbolMaster.primary_ticker == old_norm)
            .first()
        )
        if old_existing is not None:
            old_existing.primary_ticker = new_norm
            if new_name:
                old_existing.name = new_name
            self.db.flush()
            return old_existing, False

        # Case 3: nothing exists yet — create on the new ticker.
        master = SymbolMaster(
            primary_ticker=new_norm,
            asset_class=AssetClass.EQUITY.value,
            status=SymbolStatus.ACTIVE.value,
            name=new_name,
        )
        self.db.add(master)
        self.db.flush()
        return master, True
