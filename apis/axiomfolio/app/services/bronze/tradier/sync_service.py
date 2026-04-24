"""Tradier bronze-layer sync service.

Mirrors :class:`app.services.bronze.etrade.sync_service.ETradeSyncService`
exactly on contract:

* ``sync_account_comprehensive(account_number, session, *, user_id=None)``
  is the single entry point; the caller owns the :class:`Session` and the
  transaction boundary.
* Per-section loops emit ``written / skipped / errors`` counters and
  assert ``written + skipped + errors == total`` so silent drops are
  loud (see ``.cursor/rules/no-silent-fallback.mdc``).
* Every query scopes by ``account.user_id`` AND ``account.id`` — no
  global lookups. Cross-tenant isolation is pinned by
  ``backend/tests/services/bronze/tradier/test_sync_service_isolation.py``.
* After all sections are written, we reconcile closing lots inside
  ``session.begin_nested()`` so an attribution failure rolls back just
  the savepoint, not the whole sync (matches ``schwab_sync_service.py``).

Unlike E*TRADE, Tradier exposes positions (stocks + options) at a single
``/positions`` endpoint where the option-vs-stock distinction is the
**symbol shape** — OCC/OSI-style option symbols are ``[A-Z]{1,6}`` root
plus 15 fixed tail characters (``YYMMDD`` + ``C|P`` + 8-digit strike), so
length is **16–21** (e.g. ``MSFT240119C00400000`` with a 4-letter root).
We split on that shape in
``_sync_options`` / ``_sync_positions``. The same distinction drives
``broker_account.options_enabled = True`` when any option row is written
(matches #391 pattern).

Tradier history combines trades + dividends + ACH + fees into one
``/history`` feed keyed by ``type``. ``_sync_transactions`` fans out the
canonical ``Transaction`` rows; ``_sync_trades`` mirrors BUY/SELL events
into ``Trade`` rows so the closing-lot matcher (silver layer) can
attribute sells to open lots; ``_sync_dividends`` mirrors ``dividend``
events into ``Dividend`` rows. All three scan the same raw list — we
fetch it once.

Medallion layer: bronze. See docs/ARCHITECTURE.md and D127.

medallion: bronze
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.account_balance import AccountBalance
from app.models.broker_account import BrokerAccount, BrokerType
from app.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from app.models.options import Option
from app.models.position import Position, PositionStatus, PositionType
from app.models.trade import Trade
from app.models.transaction import Dividend, Transaction, TransactionType
from app.services.bronze.tradier.client import (
    TradierAPIError,
    TradierBronzeClient,
)
from app.services.oauth.encryption import (
    EncryptionDecryptError,
    EncryptionUnavailableError,
    decrypt,
)
# medallion: allow cross-layer import (bronze -> silver); resolves when app.services.silver.portfolio.closing_lot_matcher moves during Phase 0.C
from app.services.silver.portfolio.closing_lot_matcher import reconcile_closing_lots

logger = logging.getLogger(__name__)


# Connection rows this service is willing to consume. Both live and sandbox
# are supported — the client chooses the base URL based on the broker id.
_TRADIER_LIVE_BROKER_IDS: Tuple[str, ...] = ("tradier",)
_TRADIER_SANDBOX_BROKER_IDS: Tuple[str, ...] = ("tradier_sandbox",)
_TRADIER_ALL_BROKER_IDS: Tuple[str, ...] = (
    _TRADIER_LIVE_BROKER_IDS + _TRADIER_SANDBOX_BROKER_IDS
)

# ``BrokerAccount.broker`` must pair with the matching OAuth row slug
# (``tradier`` vs ``tradier_sandbox``) — see ``_oauth_broker_slug_for_account``.
_TRADIER_ACCOUNT_BROKER_TYPES: Tuple[BrokerType, ...] = (
    BrokerType.TRADIER,
    BrokerType.TRADIER_SANDBOX,
)

# ``Trade.execution_id`` is ``String(50)``; hashes must stay within this.
_EXECUTION_ID_MAX_LEN = 50


# Map Tradier's ``type`` (top-level) + ``trade.transaction_type`` (nested)
# into our canonical ``TransactionType`` enum. Observed values come from
# Tradier's v1 docs (``/accounts/{id}/history``).
_TRADIER_HISTORY_TYPE_MAP: Dict[str, TransactionType] = {
    "trade": TransactionType.OTHER,       # overridden below via transaction_type
    "option": TransactionType.OTHER,      # overridden below via transaction_type
    "dividend": TransactionType.DIVIDEND,
    "interest": TransactionType.BROKER_INTEREST_RECEIVED,
    "fee": TransactionType.OTHER_FEE,
    "tax": TransactionType.OTHER_FEE,
    "ach": TransactionType.TRANSFER,
    "wire": TransactionType.TRANSFER,
    "check": TransactionType.WITHDRAWAL,
    "journal": TransactionType.OTHER,
    "transfer": TransactionType.TRANSFER,
    "adjustment": TransactionType.OTHER,
}

# ``trade.transaction_type`` -> canonical + trade-side.
# Tradier uses: ``buy``, ``buy_to_cover``, ``buy_to_open``, ``buy_to_close``,
# ``sell``, ``sell_short``, ``sell_to_open``, ``sell_to_close``.
_TRADIER_TRADE_ACTION_MAP: Dict[str, TransactionType] = {
    "buy": TransactionType.BUY,
    "buy_to_cover": TransactionType.BUY,
    "buy_to_open": TransactionType.BUY,
    "buy_to_close": TransactionType.BUY,
    "sell": TransactionType.SELL,
    "sell_short": TransactionType.SELL,
    "sell_to_open": TransactionType.SELL,
    "sell_to_close": TransactionType.SELL,
}

# OCC/OSI option symbols: 1–6 letter root + 6 date digits + C/P + 8 strike
# digits → total length 16–21. Shorter tickers (``AAPL``) must not match.
_OSI_SYMBOL_MIN_LEN = 16
_OSI_SYMBOL_MAX_LEN = 21
_OSI_SYMBOL_RE = re.compile(r"^[A-Z]{1,6}\d{6}[CP]\d{8}$")


def _to_decimal(value: Any) -> Optional[Decimal]:
    """Coerce Tradier's JSON numbers into :class:`Decimal`.

    Tradier returns ``0`` as an int and prices as floats; we normalize
    via ``str()`` to avoid binary-float rounding. Empty / non-numeric
    inputs return ``None`` rather than ``Decimal(0)`` so callers can
    distinguish "not reported" from "truly zero".
    """

    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_tradier_datetime(value: Any) -> datetime:
    """Parse Tradier's ISO-8601 dates / datetimes into tz-aware UTC.

    Tradier uses ``YYYY-MM-DDTHH:MM:SS.sssZ`` for ``date_acquired`` and
    ``YYYY-MM-DD`` for history events; we accept both, plus native
    ``date`` / ``datetime`` objects so tests can inject fixtures
    directly.
    """

    if value is None or value == "":
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    try:
        raw = str(value).strip()
        # ``Z`` suffix isn't ISO 8601 per ``fromisoformat`` pre-3.11 spec.
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            return datetime.now(timezone.utc)


def _is_option_symbol(symbol: str) -> bool:
    """Return True if ``symbol`` is an OSI-style option contract code."""

    if not symbol:
        return False
    sym = symbol.upper()
    if len(sym) < _OSI_SYMBOL_MIN_LEN or len(sym) > _OSI_SYMBOL_MAX_LEN:
        return False
    return bool(_OSI_SYMBOL_RE.match(sym))


def _parse_osi_symbol(osi: str) -> Optional[Dict[str, Any]]:
    """Split an OSI-style ``AAPL230616C00165000`` into its fields.

    Returns ``None`` on shape mismatch so callers can skip the row
    instead of half-writing a malformed option.
    """

    if not _is_option_symbol(osi):
        return None
    # Walk backwards from the end because the root is variable length
    # (1-6 chars). The last 15 chars are always ``YYMMDD[CP]########``.
    tail = osi[-15:]
    root = osi[:-15]
    try:
        year = 2000 + int(tail[0:2])
        month = int(tail[2:4])
        day = int(tail[4:6])
        put_call = tail[6]
        strike_raw = int(tail[7:])
    except ValueError:
        return None
    if put_call not in ("C", "P"):
        return None
    try:
        expiry = date(year, month, day)
    except ValueError:
        return None
    return {
        "underlying": root,
        "expiry": expiry,
        "put_call": "CALL" if put_call == "C" else "PUT",
        "strike": strike_raw / 1000.0,  # OSI strike = integer * 0.001
    }


class TradierSyncService:
    """Bronze ingestion from Tradier's v1 data API.

    The caller (``BrokerSyncService``) passes in a fresh SQLAlchemy
    ``Session``; we never create sessions inside the service and we never
    commit — the caller controls the transaction boundary.
    """

    def __init__(self, client: Optional[TradierBronzeClient] = None) -> None:
        # ``client`` is optional so the broker dispatcher can instantiate
        # the service cheaply and tests can inject a fake. The real
        # client needs the decrypted access token so we defer
        # construction until ``_connect``.
        self._client: Optional[TradierBronzeClient] = client
        self._connection_broker_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Credentials + account discovery
    # ------------------------------------------------------------------
    @staticmethod
    def _oauth_broker_slug_for_account(account: BrokerAccount) -> str:
        """Map ``BrokerAccount.broker`` to the OAuth row slug (``tradier`` / ``tradier_sandbox``)."""

        if account.broker == BrokerType.TRADIER:
            return "tradier"
        if account.broker == BrokerType.TRADIER_SANDBOX:
            return "tradier_sandbox"
        raise ConnectionError(
            "This account is not a Tradier broker; cannot load Tradier OAuth."
        )

    def _load_connection(
        self, account: BrokerAccount, session: Session
    ) -> BrokerOAuthConnection:
        """Load the ACTIVE OAuth connection for this user + Tradier.

        Picks the connection whose ``broker`` string matches the account's
        Tradier environment (``tradier`` for live, ``tradier_sandbox`` for
        sandbox) so a user with both links does not get a last-updated coin
        flip.
        """

        expected_slug = self._oauth_broker_slug_for_account(account)
        conn: Optional[BrokerOAuthConnection] = (
            session.query(BrokerOAuthConnection)
            .filter(
                BrokerOAuthConnection.user_id == account.user_id,
                BrokerOAuthConnection.broker == expected_slug,
            )
            .order_by(BrokerOAuthConnection.updated_at.desc())
            .first()
        )
        if conn is None:
            raise ConnectionError(
                "No Tradier OAuth connection found. Link your Tradier account "
                "via the Connections page before syncing."
            )
        if conn.status != OAuthConnectionStatus.ACTIVE.value:
            raise ConnectionError(
                f"Tradier OAuth connection is {conn.status}; please re-link on "
                "the Connections page."
            )
        if not conn.access_token_encrypted:
            raise ConnectionError(
                "Tradier OAuth connection is missing an access token; please "
                "re-link on the Connections page."
            )
        return conn

    def _connect(self, account: BrokerAccount, session: Session) -> None:
        """Instantiate the bronze client with the decrypted access token."""

        if self._client is not None:
            return  # pre-injected (tests)

        conn = self._load_connection(account, session)
        try:
            access_token = decrypt(conn.access_token_encrypted)
        except (EncryptionUnavailableError, EncryptionDecryptError) as exc:
            raise ConnectionError(
                f"Failed to decrypt Tradier credentials: {exc}. Re-link your "
                "Tradier account on the Connections page."
            ) from exc

        self._connection_broker_id = conn.broker
        self._client = TradierBronzeClient(
            access_token=access_token,
            sandbox=(conn.broker in _TRADIER_SANDBOX_BROKER_IDS),
        )

    # Sentinel reason codes returned alongside ``None`` from
    # :meth:`_resolve_or_discover`. Kept as string constants so the
    # resolver and its caller share one vocabulary.
    _RESOLVE_REASON_NO_ACCOUNTS = "no_accounts"
    _RESOLVE_REASON_PLACEHOLDER_COLLISION = "placeholder_collision"

    def _resolve_or_discover(
        self, account: BrokerAccount, session: Session
    ) -> Tuple[Optional[str], Optional[str]]:
        """Map the local ``account_number`` to Tradier's ``account_number``.

        Tradier keys every data endpoint off the account number directly
        (there's no opaque "account id key" like E*TRADE). We still call
        ``/user/profile`` to (a) verify the token can enumerate an
        account and (b) handle placeholder accounts the same way E*TRADE
        does — if the local row is still on ``TRADIER_OAUTH``, we
        repoint to the first live account.
        """

        assert self._client is not None

        accounts = self._client.get_accounts()
        if not accounts:
            logger.warning(
                "tradier sync: account %s (user %s) — /user/profile returned 0 accounts",
                account.id, account.user_id,
            )
            return None, self._RESOLVE_REASON_NO_ACCOUNTS

        target = (account.account_number or "").strip()
        placeholder = (
            not target
            or target == "TRADIER_OAUTH"
            or target.startswith("TRADIER_")
        )

        match: Optional[Dict[str, Any]] = None
        if not placeholder:
            match = next(
                (a for a in accounts if str(a.get("account_number", "")) == target),
                None,
            )

        if match is None:
            # Placeholder or drift: take the first non-CLOSED account.
            match = next(
                (
                    a
                    for a in accounts
                    if (a.get("status") or "").upper() != "CLOSED"
                ),
                accounts[0],
            )
            real_id = str(match.get("account_number") or "").strip()
            if real_id and real_id != target:
                existing = (
                    session.query(BrokerAccount)
                    .filter(
                        BrokerAccount.user_id == account.user_id,
                        BrokerAccount.broker == account.broker,
                        BrokerAccount.account_number == real_id,
                    )
                    .first()
                )
                if existing and existing.id != account.id:
                    logger.warning(
                        "tradier sync: placeholder account %d collides with "
                        "real account %d for user %d (account_number=%s); "
                        "disabling placeholder and skipping this run.",
                        account.id, existing.id, account.user_id, real_id,
                    )
                    try:
                        account.is_enabled = False
                        session.flush()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "tradier sync: failed to disable placeholder %d: %s",
                            account.id, exc,
                        )
                    return None, self._RESOLVE_REASON_PLACEHOLDER_COLLISION
                logger.info(
                    "tradier sync: auto-correcting account %d for user %d: "
                    "'%s' -> '%s'",
                    account.id, account.user_id, target, real_id,
                )
                account.account_number = real_id
                session.flush()

        acct_no = str(match.get("account_number") or "").strip()
        if not acct_no:
            return None, self._RESOLVE_REASON_NO_ACCOUNTS
        return acct_no, None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def sync_account_comprehensive(
        self,
        account_number: str,
        session: Session,
        *,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Sync a single Tradier account end-to-end.

        ``account_number`` is not unique across tenants; ``user_id`` is
        the multi-tenancy disambiguator. Fail-closed when ``user_id`` is
        None AND multiple local accounts share the same number.
        """

        query = (
            session.query(BrokerAccount)
            .filter(BrokerAccount.account_number == str(account_number))
            .filter(BrokerAccount.broker.in_(_TRADIER_ACCOUNT_BROKER_TYPES))
        )
        if user_id is not None:
            query = query.filter(BrokerAccount.user_id == int(user_id))
        matches = query.all()
        if not matches:
            raise ValueError(
                f"Tradier account {account_number} not found"
                + (f" for user {user_id}" if user_id is not None else "")
            )
        if len(matches) > 1:
            raise ValueError(
                f"Tradier account_number {account_number!r} matched "
                f"{len(matches)} accounts across users; caller must pass "
                "user_id to disambiguate (multi-tenancy safety)."
            )
        account: BrokerAccount = matches[0]

        self._connect(account, session)
        acct_no, reason = self._resolve_or_discover(account, session)
        if not acct_no:
            if reason == self._RESOLVE_REASON_PLACEHOLDER_COLLISION:
                return {
                    "status": "skipped",
                    "error": (
                        "Tradier placeholder account collided with an existing "
                        "real account for the same user; placeholder disabled. "
                        "The real account will sync on the next run."
                    ),
                    "permanent": False,
                }
            return {
                "status": "error",
                "error": (
                    "Tradier /user/profile returned no usable account for this "
                    "token; please re-link."
                ),
            }

        results: Dict[str, Any] = {"status": "success"}

        try:
            assert self._client is not None
            positions_raw = self._client.get_positions(acct_no)
            history_raw = self._client.get_history(acct_no)

            results.update(self._sync_positions(account, positions_raw, session))
            results.update(self._sync_options(account, positions_raw, session))
            results.update(self._sync_transactions(account, history_raw, session))
            results.update(self._sync_trades(account, history_raw, session))
            results.update(self._sync_dividends(account, history_raw, session))
            results.update(self._sync_balances(account, acct_no, session))
        except TradierAPIError as exc:
            logger.warning(
                "tradier sync: API error for user %s account %s: %s (permanent=%s)",
                account.user_id, account.id, exc, exc.permanent,
            )
            return {
                "status": "error",
                "error": str(exc),
                "permanent": exc.permanent,
            }

        # Closing-lot reconciliation matches SELLs to open lots. Run
        # inside a SAVEPOINT so a matcher failure rolls back just the
        # savepoint — the positions/options/transactions/trades we
        # already wrote above still commit.
        try:
            with session.begin_nested():
                match_result = reconcile_closing_lots(session, account)
            results["closed_lots_created"] = match_result.created
            results["closed_lots_updated"] = match_result.updated
            if match_result.unmatched_quantity > 0:
                logger.warning(
                    "tradier sync: account %s had %s unmatched sell-shares "
                    "during closing-lot reconciliation (first warning: %s)",
                    account.id,
                    match_result.unmatched_quantity,
                    match_result.warnings[0] if match_result.warnings else "n/a",
                )
        except Exception as exc:  # noqa: BLE001 — log + continue; sync is still successful
            logger.warning(
                "tradier sync: closing-lot reconciliation failed for account %s: %s",
                account.id, exc,
            )
            results["closed_lots_error"] = str(exc)

        session.flush()

        total_items = sum(v for v in results.values() if isinstance(v, int))
        logger.info(
            "tradier sync: user %s account %s (%s) synced %d total items: %s",
            account.user_id, account.id, account.account_number, total_items, results,
        )
        return results

    # ------------------------------------------------------------------
    # Section syncs
    # ------------------------------------------------------------------
    def _sync_positions(
        self,
        account: BrokerAccount,
        raw: List[Dict[str, Any]],
        session: Session,
    ) -> Dict[str, Any]:
        """Write stock positions from a pre-fetched ``/positions`` payload.

        Rows whose ``symbol`` parses as OSI (16–21 chars + OSI regex) are
        skipped here and handled by :meth:`_sync_options`.
        """

        written = 0
        skipped = 0
        errors = 0
        options_seen = 0
        total = len(raw)

        for pos_raw in raw:
            try:
                symbol = (pos_raw.get("symbol") or "").upper()
                if not symbol:
                    skipped += 1
                    continue
                if _is_option_symbol(symbol):
                    options_seen += 1
                    skipped += 1
                    continue

                qty = _to_decimal(pos_raw.get("quantity")) or Decimal("0")
                cost_basis = _to_decimal(pos_raw.get("cost_basis"))
                avg_cost: Optional[Decimal] = None
                if cost_basis is not None and qty not in (Decimal("0"), None):
                    # Tradier gives total cost basis, not per-share. Derive
                    # the per-share avg so downstream (Position.average_cost)
                    # is populated consistently with other brokers.
                    try:
                        avg_cost = cost_basis / abs(qty)
                    except (InvalidOperation, ZeroDivisionError):
                        avg_cost = None

                fields: Dict[str, Any] = {
                    "quantity": qty,
                    "instrument_type": "STOCK",
                    "position_type": (
                        PositionType.LONG if qty >= 0 else PositionType.SHORT
                    ),
                    "status": (
                        PositionStatus.OPEN if qty != 0 else PositionStatus.CLOSED
                    ),
                }
                if avg_cost is not None:
                    fields["average_cost"] = avg_cost
                if cost_basis is not None:
                    fields["total_cost_basis"] = cost_basis

                existing: Optional[Position] = (
                    session.query(Position)
                    .filter(
                        Position.user_id == account.user_id,
                        Position.account_id == account.id,
                        Position.symbol == symbol,
                    )
                    .first()
                )
                if existing is not None:
                    for k, v in fields.items():
                        setattr(existing, k, v)
                else:
                    session.add(
                        Position(
                            user_id=account.user_id,
                            account_id=account.id,
                            symbol=symbol,
                            currency=account.currency or "USD",
                            **fields,
                        )
                    )
                written += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "tradier sync: failed to upsert position for user %s account %s: %s",
                    account.user_id, account.id, exc,
                )

        session.flush()
        assert written + skipped + errors == total, (
            f"tradier positions counter drift: "
            f"{written}+{skipped}+{errors} != {total}"
        )
        logger.info(
            "tradier sync positions: user=%s account=%s written=%d skipped=%d "
            "errors=%d options_in_portfolio=%d",
            account.user_id, account.id, written, skipped, errors, options_seen,
        )
        return {
            "positions_synced": written,
            "positions_skipped": skipped,
            "positions_errors": errors,
        }

    def _sync_options(
        self,
        account: BrokerAccount,
        raw: List[Dict[str, Any]],
        session: Session,
    ) -> Dict[str, Any]:
        """Write option positions from the same ``/positions`` payload."""

        options = [
            p for p in raw
            if _is_option_symbol((p.get("symbol") or "").upper())
        ]

        written = 0
        skipped = 0
        errors = 0
        total = len(options)

        for opt_raw in options:
            try:
                osi = (opt_raw.get("symbol") or "").upper()
                parsed = _parse_osi_symbol(osi)
                if parsed is None:
                    skipped += 1
                    continue
                underlying = parsed["underlying"]
                expiry: date = parsed["expiry"]
                put_call: str = parsed["put_call"]
                strike: float = parsed["strike"]
                qty = int(_to_float(opt_raw.get("quantity")))
                cost_basis = _to_decimal(opt_raw.get("cost_basis"))

                if not underlying or strike <= 0:
                    skipped += 1
                    continue

                existing: Optional[Option] = (
                    session.query(Option)
                    .filter(
                        Option.user_id == account.user_id,
                        Option.account_id == account.id,
                        Option.underlying_symbol == underlying,
                        Option.strike_price == strike,
                        Option.expiry_date == expiry,
                        Option.option_type == put_call,
                    )
                    .first()
                )
                if existing is not None:
                    existing.open_quantity = qty
                    if cost_basis is not None:
                        existing.total_cost = cost_basis
                else:
                    session.add(
                        Option(
                            user_id=account.user_id,
                            account_id=account.id,
                            symbol=osi,
                            underlying_symbol=underlying,
                            strike_price=strike,
                            expiry_date=expiry,
                            option_type=put_call,
                            multiplier=100,
                            open_quantity=qty,
                            currency=account.currency or "USD",
                            data_source="TRADIER_API",
                            total_cost=cost_basis,
                        )
                    )
                written += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "tradier sync: failed to upsert option for user %s account %s: %s",
                    account.user_id, account.id, exc,
                )

        if written > 0 and not account.options_enabled:
            account.options_enabled = True

        session.flush()
        assert written + skipped + errors == total, (
            f"tradier options counter drift: "
            f"{written}+{skipped}+{errors} != {total}"
        )
        logger.info(
            "tradier sync options: user=%s account=%s written=%d skipped=%d errors=%d",
            account.user_id, account.id, written, skipped, errors,
        )
        return {
            "options_synced": written,
            "options_skipped": skipped,
            "options_errors": errors,
        }

    # ------------------------------------------------------------------
    # Helpers for history-feed extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _history_external_id(event: Dict[str, Any]) -> str:
        """Stable short id for a history row (Transaction + Trade idempotency).

        Tradier does not always include an explicit id. We form a raw key
        from ``date + type + amount +`` nested subfields, then blake2b-hash to
        ``tra_<8 hex>`` so ``Trade.execution_id`` (``String(50)`` unique) never
        exceeds the limit — same pattern as
        :mod:`app.services.silver.portfolio.closing_lot_matcher`.
        """

        parts = [
            str(event.get("date") or ""),
            str(event.get("type") or ""),
            str(event.get("amount") or ""),
        ]
        inner = (
            event.get("trade")
            or event.get("option")
            or event.get("dividend")
            or event.get("journal")
            or {}
        )
        if isinstance(inner, dict):
            parts.append(str(inner.get("symbol") or ""))
            parts.append(str(inner.get("description") or ""))
        raw_key = "|".join(parts)
        digest = hashlib.blake2b(raw_key.encode("utf-8"), digest_size=4).hexdigest()
        out = f"tra_{digest}"
        if len(out) > _EXECUTION_ID_MAX_LEN:
            raise ValueError(
                f"tradier _history_external_id length {len(out)} exceeds "
                f"execution_id cap {_EXECUTION_ID_MAX_LEN}"
            )
        return out

    @staticmethod
    def _trade_subrecord(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return the nested ``trade`` / ``option`` subrecord if present."""

        for key in ("trade", "option"):
            inner = event.get(key)
            if isinstance(inner, dict):
                return inner
        return None

    def _sync_transactions(
        self,
        account: BrokerAccount,
        raw: List[Dict[str, Any]],
        session: Session,
    ) -> Dict[str, Any]:
        """Upsert ``Transaction`` rows from the history feed."""

        written = 0
        skipped = 0
        errors = 0
        total = len(raw)

        for event in raw:
            try:
                event_type = (event.get("type") or "").lower()
                if not event_type:
                    skipped += 1
                    continue

                ext_id = self._history_external_id(event)
                if not ext_id:
                    skipped += 1
                    continue

                txn_type = _TRADIER_HISTORY_TYPE_MAP.get(
                    event_type, TransactionType.OTHER
                )
                sub = self._trade_subrecord(event)
                symbol = ""
                qty = 0.0
                price = 0.0
                commission = 0.0
                description: Optional[str] = None
                action: Optional[str] = None

                if sub is not None:
                    action = (sub.get("transaction_type") or "").lower() or None
                    symbol = (sub.get("symbol") or "").upper()
                    qty = _to_float(sub.get("quantity"))
                    price = _to_float(sub.get("price"))
                    commission = _to_float(sub.get("commission"))
                    description = (sub.get("description") or "").strip() or None
                    if action in _TRADIER_TRADE_ACTION_MAP:
                        txn_type = _TRADIER_TRADE_ACTION_MAP[action]

                amount = _to_float(event.get("amount"), qty * price)
                net_amount = amount - commission
                txn_date = _parse_tradier_datetime(event.get("date"))

                existing_txn = (
                    session.query(Transaction)
                    .filter(
                        Transaction.account_id == account.id,
                        Transaction.external_id == ext_id,
                    )
                    .first()
                )
                if existing_txn is None:
                    session.add(
                        Transaction(
                            account_id=account.id,
                            external_id=ext_id,
                            symbol=symbol or "CASH",
                            transaction_type=txn_type,
                            action=(action[:10] if action else None),
                            quantity=qty,
                            trade_price=price,
                            amount=amount,
                            net_amount=net_amount,
                            commission=commission,
                            currency=account.currency or "USD",
                            transaction_date=txn_date,
                            description=description,
                            source="TRADIER",
                        )
                    )
                    written += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "tradier sync: failed to upsert transaction for user %s "
                    "account %s: %s",
                    account.user_id, account.id, exc,
                )

        session.flush()
        assert written + skipped + errors == total, (
            f"tradier transactions counter drift: "
            f"{written}+{skipped}+{errors} != {total}"
        )
        logger.info(
            "tradier sync transactions: user=%s account=%s written=%d "
            "skipped=%d errors=%d",
            account.user_id, account.id, written, skipped, errors,
        )
        return {
            "transactions_synced": written,
            "transactions_skipped": skipped,
            "transactions_errors": errors,
        }

    def _sync_trades(
        self,
        account: BrokerAccount,
        raw: List[Dict[str, Any]],
        session: Session,
    ) -> Dict[str, Any]:
        """Mirror BUY/SELL history events into ``Trade`` rows.

        The closing-lot matcher (silver layer) consumes ``Trade`` rows —
        it will not see anything we only wrote to ``Transaction``. We
        populate ``execution_time``, ``is_opening``, and ``status='FILLED'``
        so the matcher can correctly attribute closes to opens.
        """

        written = 0
        skipped = 0
        errors = 0
        total = len(raw)

        for event in raw:
            try:
                sub = self._trade_subrecord(event)
                if sub is None:
                    skipped += 1
                    continue
                action = (sub.get("transaction_type") or "").lower()
                if action not in _TRADIER_TRADE_ACTION_MAP:
                    skipped += 1
                    continue
                symbol = (sub.get("symbol") or "").upper()
                qty = _to_float(sub.get("quantity"))
                price = _to_float(sub.get("price"))
                commission = _to_float(sub.get("commission"))
                if not symbol or qty == 0:
                    skipped += 1
                    continue

                side = (
                    "BUY"
                    if _TRADIER_TRADE_ACTION_MAP[action] == TransactionType.BUY
                    else "SELL"
                )
                # Opening vs closing semantics match the action name.
                # ``buy``/``buy_to_open``/``sell_short``/``sell_to_open``
                # are opening; the ``_to_close`` / ``buy_to_cover`` /
                # bare ``sell`` family are closing.
                if action in (
                    "buy",
                    "buy_to_open",
                    "sell_short",
                    "sell_to_open",
                ):
                    is_opening = True
                elif action in (
                    "buy_to_close",
                    "buy_to_cover",
                    "sell",
                    "sell_to_close",
                ):
                    is_opening = False
                else:  # defensive; shouldn't happen given the filter above
                    is_opening = side == "BUY"

                ext_id = self._history_external_id(event)
                execution_time = _parse_tradier_datetime(event.get("date"))

                existing_trade = (
                    session.query(Trade)
                    .filter(
                        Trade.account_id == account.id,
                        Trade.execution_id == ext_id,
                    )
                    .first()
                )
                if existing_trade is not None:
                    skipped += 1
                    continue

                session.add(
                    Trade(
                        account_id=account.id,
                        symbol=symbol,
                        side=side,
                        quantity=abs(qty),
                        price=price,
                        total_value=abs(qty * price),
                        commission=commission,
                        execution_id=ext_id,
                        execution_time=execution_time,
                        status="FILLED",
                        is_opening=is_opening,
                        is_paper_trade=False,
                    )
                )
                written += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "tradier sync: failed to upsert trade for user %s "
                    "account %s: %s",
                    account.user_id, account.id, exc,
                )

        session.flush()
        assert written + skipped + errors == total, (
            f"tradier trades counter drift: "
            f"{written}+{skipped}+{errors} != {total}"
        )
        logger.info(
            "tradier sync trades: user=%s account=%s written=%d skipped=%d errors=%d",
            account.user_id, account.id, written, skipped, errors,
        )
        return {
            "trades_synced": written,
            "trades_skipped": skipped,
            "trades_errors": errors,
        }

    def _sync_dividends(
        self,
        account: BrokerAccount,
        raw: List[Dict[str, Any]],
        session: Session,
    ) -> Dict[str, Any]:
        """Mirror ``dividend``-typed history rows into ``Dividend`` rows."""

        written = 0
        skipped = 0
        errors = 0
        total = len(raw)

        for event in raw:
            try:
                event_type = (event.get("type") or "").lower()
                if event_type != "dividend":
                    skipped += 1
                    continue
                sub = event.get("dividend") or event.get("journal") or {}
                symbol = ""
                if isinstance(sub, dict):
                    symbol = (sub.get("symbol") or "").upper()
                if not symbol:
                    # Dividend events occasionally come with symbol on the
                    # description field only; skip rather than write a
                    # dividend row against "CASH".
                    skipped += 1
                    continue

                amount = _to_float(event.get("amount"))
                txn_date = _parse_tradier_datetime(event.get("date"))
                ext_id = self._history_external_id(event)

                existing_div = (
                    session.query(Dividend)
                    .filter(
                        Dividend.account_id == account.id,
                        Dividend.external_id == ext_id,
                    )
                    .first()
                )
                if existing_div is not None:
                    skipped += 1
                    continue
                session.add(
                    Dividend(
                        account_id=account.id,
                        external_id=ext_id,
                        symbol=symbol,
                        ex_date=txn_date,
                        pay_date=txn_date,
                        dividend_per_share=0,
                        shares_held=0,
                        total_dividend=abs(amount),
                        tax_withheld=0,
                        net_dividend=abs(amount),
                        currency=account.currency or "USD",
                        source="tradier",
                    )
                )
                written += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "tradier sync: failed to upsert dividend for user %s "
                    "account %s: %s",
                    account.user_id, account.id, exc,
                )

        session.flush()
        assert written + skipped + errors == total, (
            f"tradier dividends counter drift: "
            f"{written}+{skipped}+{errors} != {total}"
        )
        logger.info(
            "tradier sync dividends: user=%s account=%s written=%d skipped=%d errors=%d",
            account.user_id, account.id, written, skipped, errors,
        )
        return {
            "dividends_synced": written,
            "dividends_skipped": skipped,
            "dividends_errors": errors,
        }

    def _sync_balances(
        self,
        account: BrokerAccount,
        account_id: str,
        session: Session,
    ) -> Dict[str, Any]:
        """Write a single :class:`AccountBalance` snapshot."""

        assert self._client is not None
        bal = self._client.get_balances(account_id)
        if not bal:
            logger.warning(
                "tradier sync balances: user=%s account=%s — empty balance payload",
                account.user_id, account.id,
            )
            return {"balances_synced": 0, "balances_skipped": 1, "balances_errors": 0}

        cash_block = bal.get("cash") or {}
        margin_block = bal.get("margin") or {}

        # ``total_cash`` is the catch-all "cash + sweep" number Tradier
        # uses at the top level; ``cash.cash_available`` is the narrower
        # withdrawable figure.
        cash_balance = _to_decimal(bal.get("total_cash"))
        available_funds = _to_decimal(cash_block.get("cash_available"))
        buying_power = _to_decimal(
            margin_block.get("stock_buying_power")
            or cash_block.get("cash_available")
            or bal.get("total_cash")
        )
        equity = _to_decimal(bal.get("total_equity"))
        net_liq = equity  # Tradier's ``total_equity`` matches net liq semantics.

        new_bal = AccountBalance(
            user_id=account.user_id,
            broker_account_id=account.id,
            balance_date=datetime.now(timezone.utc),
            cash_balance=cash_balance,
            net_liquidation=net_liq,
            buying_power=buying_power,
            available_funds=available_funds,
            equity=equity,
            data_source="TRADIER_API",
        )
        session.add(new_bal)
        session.flush()
        logger.info(
            "tradier sync balances: user=%s account=%s written=1",
            account.user_id, account.id,
        )
        return {"balances_synced": 1, "balances_skipped": 0, "balances_errors": 0}


__all__ = ["TradierSyncService"]
