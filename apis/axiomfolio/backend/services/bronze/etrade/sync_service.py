"""E*TRADE bronze-layer sync service.

Mirrors the shape of :class:`backend.services.portfolio.schwab_sync_service.SchwabSyncService`:

* ``sync_account_comprehensive(account_number, session)`` — the single entry
  point invoked by :class:`backend.services.portfolio.broker_sync_service.BrokerSyncService`.
* Credentials live in :class:`backend.models.broker_oauth_connection.BrokerOAuthConnection`
  (OAuth broker foundation), not ``AccountCredentials`` — this is the first
  sync service built on top of the new OAuth plumbing and sets the pattern
  Fidelity/Tradier will follow.
* Per-symbol loops emit structured ``written / skipped / errors`` counters
  and assert ``written + skipped + errors == total`` so silent drops are
  loud (see ``.cursor/rules/no-silent-fallback.mdc``).

All queries filter by ``user_id`` — the cross-tenant-isolation test in
``backend/tests/services/bronze/etrade/test_sync_service_isolation.py``
pins the invariant.

Medallion layer: bronze. See docs/ARCHITECTURE.md and D127.

medallion: bronze
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.models.account_balance import AccountBalance
from backend.models.broker_account import BrokerAccount, BrokerType
from backend.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from backend.models.options import Option
from backend.models.position import Position, PositionStatus, PositionType
from backend.models.trade import Trade
from backend.models.transaction import Dividend, Transaction, TransactionType
from backend.services.bronze.etrade.client import (
    ETradeAPIError,
    ETradeBronzeClient,
)
from backend.services.oauth.encryption import (
    EncryptionDecryptError,
    EncryptionUnavailableError,
    decrypt,
)
# medallion: allow cross-layer import (bronze -> silver); resolves when backend.services.portfolio.day_pnl_service moves during Phase 0.C
from backend.services.portfolio.day_pnl_service import recompute_day_pnl_for_rows

logger = logging.getLogger(__name__)


# Sandbox-only in v1. ``ETradeBronzeClient`` unconditionally constructs an
# ``ETradeSandboxAdapter`` (sandbox base URL + sandbox consumer keys), so
# accepting ``"etrade"`` (live) on the connection row would call the
# sandbox API with a live access token and silently fetch wrong / 401
# data. Restrict to ``"etrade_sandbox"`` until the live adapter ships;
# promoting to live is an explicit code change plus a matching broker-id
# flip, which is the whole point of this guardrail. See docs/KNOWLEDGE.md
# D130 — future broker-specific bronze sync services follow this same
# narrow pattern.
_ETRADE_BROKER_IDS: Tuple[str, ...] = ("etrade_sandbox",)


# Mapping from E*TRADE's ``transactionType`` values to our canonical
# ``TransactionType`` enum. Values observed from the v1 API:
# https://apisb.etrade.com/docs/api/account/api-transaction-v1.html
_ETRADE_TYPE_MAP: Dict[str, TransactionType] = {
    "BUY": TransactionType.BUY,
    "SELL": TransactionType.SELL,
    "SHORT": TransactionType.SELL,
    "BUY_TO_COVER": TransactionType.BUY,
    "DIVIDEND": TransactionType.DIVIDEND,
    "INTEREST": TransactionType.BROKER_INTEREST_RECEIVED,
    "MARGIN_INT": TransactionType.BROKER_INTEREST_PAID,
    "TRANSFER": TransactionType.TRANSFER,
    "DEPOSIT": TransactionType.DEPOSIT,
    "WITHDRAWAL": TransactionType.WITHDRAWAL,
    "ATM": TransactionType.WITHDRAWAL,
    "FEE": TransactionType.OTHER_FEE,
    "COMMISSION": TransactionType.COMMISSION,
    "DIV": TransactionType.DIVIDEND,
    "REINVEST": TransactionType.DIVIDEND,
    "OTHER": TransactionType.OTHER,
}

# Transaction types that are "real" trades and should mirror into a Trade row.
_TRADE_ETRADE_TYPES = {"BUY", "SELL", "SHORT", "BUY_TO_COVER"}


def _to_decimal(value: Any) -> Optional[Decimal]:
    """Coerce E*TRADE's JSON numbers (or strings) into ``Decimal``.

    Returns ``None`` for missing / non-numeric inputs. E*TRADE mixes int and
    float types in the same response (e.g. ``quantity`` is float,
    ``costBasis`` is float, ``marketValue`` is float), so we normalize to
    ``Decimal`` via ``str()`` to avoid binary-float rounding.
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


def _parse_etrade_datetime(value: Any) -> datetime:
    """Parse an E*TRADE date/time value.

    E*TRADE returns epoch milliseconds for ``transactionDate`` and
    ``settlementDate``. Fallback to ``datetime.fromisoformat`` for any
    stringy values we might encounter in non-transaction payloads.
    """

    if value is None or value == "":
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        # E*TRADE uses epoch milliseconds in the v1 transactions payload.
        try:
            return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _parse_option_expiry(raw: Dict[str, Any]) -> Optional[date]:
    """Build a ``date`` from E*TRADE's ``expiryYear/Month/Day`` triple."""

    try:
        year = int(raw.get("expiryYear") or 0)
        month = int(raw.get("expiryMonth") or 0)
        day = int(raw.get("expiryDay") or 0)
    except (TypeError, ValueError):
        return None
    if not (year and month and day):
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


class ETradeSyncService:
    """Bronze ingestion from E*TRADE's v1 sandbox data API.

    The caller (``BrokerSyncService``) passes in a fresh SQLAlchemy
    ``Session``; we never create sessions inside the service and we never
    commit — the caller controls the transaction boundary.
    """

    def __init__(self, client: Optional[ETradeBronzeClient] = None) -> None:
        # ``client`` is optional so the broker dispatcher can instantiate the
        # service cheaply and tests can inject a stub. The real client needs
        # credentials so we defer construction until ``_connect``.
        self._client: Optional[ETradeBronzeClient] = client

    # ------------------------------------------------------------------
    # Credentials + account discovery
    # ------------------------------------------------------------------
    def _load_connection(
        self, account: BrokerAccount, session: Session
    ) -> BrokerOAuthConnection:
        """Load the ACTIVE OAuth connection for this user + E*TRADE.

        Filters by ``user_id`` (multi-tenancy) and both accepted broker ids.
        Raises ``ConnectionError`` with a user-actionable message on miss.
        """

        conn: Optional[BrokerOAuthConnection] = (
            session.query(BrokerOAuthConnection)
            .filter(
                BrokerOAuthConnection.user_id == account.user_id,
                BrokerOAuthConnection.broker.in_(_ETRADE_BROKER_IDS),
            )
            .order_by(BrokerOAuthConnection.updated_at.desc())
            .first()
        )
        if conn is None:
            raise ConnectionError(
                "No E*TRADE OAuth connection found. Link your E*TRADE account "
                "via the Connections page before syncing."
            )
        if conn.status != OAuthConnectionStatus.ACTIVE.value:
            raise ConnectionError(
                f"E*TRADE OAuth connection is {conn.status}; please re-link on "
                "the Connections page."
            )
        if not conn.access_token_encrypted or not conn.refresh_token_encrypted:
            # OAuth 1.0a stores the access-token *secret* under refresh_token.
            raise ConnectionError(
                "E*TRADE OAuth connection is missing access token or access "
                "token secret; please re-link on the Connections page."
            )
        return conn

    def _connect(self, account: BrokerAccount, session: Session) -> None:
        """Instantiate the bronze client with decrypted tokens."""

        if self._client is not None:
            return  # pre-injected (tests)

        conn = self._load_connection(account, session)
        try:
            access_token = decrypt(conn.access_token_encrypted)
            # OAuth 1.0a: refresh_token_encrypted holds the access_token_secret.
            access_token_secret = decrypt(conn.refresh_token_encrypted)
        except (EncryptionUnavailableError, EncryptionDecryptError) as exc:
            raise ConnectionError(
                f"Failed to decrypt E*TRADE credentials: {exc}. Re-link your "
                "E*TRADE account on the Connections page."
            ) from exc

        self._client = ETradeBronzeClient(
            access_token=access_token,
            access_token_secret=access_token_secret,
        )

    # Sentinel reason codes returned alongside ``None`` from
    # :meth:`_resolve_or_discover`. Kept as module-level-ish string
    # constants so both the resolver and the caller share one vocabulary
    # instead of embedding remediation copy in two places.
    _RESOLVE_REASON_NO_ACCOUNTS = "no_accounts"
    _RESOLVE_REASON_PLACEHOLDER_COLLISION = "placeholder_collision"

    def _resolve_or_discover(
        self, account: BrokerAccount, session: Session
    ) -> Tuple[Optional[str], Optional[str]]:
        """Map the local ``account_number`` to E*TRADE's ``accountIdKey``.

        The API routes balance/portfolio/transactions off an opaque
        ``accountIdKey`` (not the displayable ``accountId``). We pull the
        full list, find the row whose ``accountId`` matches our local
        ``account_number``, and return the key.

        If the local row is still on a placeholder (e.g. ``ETRADE_OAUTH``),
        we pick the first live account and repoint ``account.account_number``
        to the real ``accountId`` (matching the Schwab placeholder flow).

        Returns ``(account_id_key, reason)``:

        * On success: ``(<key>, None)``.
        * On ``/v1/accounts/list`` returning zero rows:
          ``(None, _RESOLVE_REASON_NO_ACCOUNTS)`` — the token is alive but
          the user has closed/removed all accounts, or the connection
          grant was never account-scoped. User-actionable: re-link.
        * On a placeholder colliding with a real account already owned by
          the same user: ``(None, _RESOLVE_REASON_PLACEHOLDER_COLLISION)`` —
          the placeholder is disabled here and the real account will be
          picked up on the next Beat fan-out. Not user-actionable; the
          caller should surface "skipped, duplicate placeholder" rather
          than "please re-link".
        """

        assert self._client is not None  # _connect sets this

        accounts = self._client.list_accounts()
        if not accounts:
            logger.warning(
                "etrade sync: account %s (user %s) — /v1/accounts/list returned 0 accounts",
                account.id, account.user_id,
            )
            return None, self._RESOLVE_REASON_NO_ACCOUNTS

        target = (account.account_number or "").strip()
        placeholder = (
            not target
            or target == "ETRADE_OAUTH"
            or target.startswith("ETRADE_")
        )

        match: Optional[Dict[str, Any]] = None
        if not placeholder:
            match = next(
                (a for a in accounts if str(a.get("accountId", "")) == target),
                None,
            )

        if match is None:
            # Placeholder or drift: take the first non-CLOSED account.
            match = next(
                (
                    a
                    for a in accounts
                    if (a.get("accountStatus") or "").upper() != "CLOSED"
                ),
                accounts[0],
            )
            real_id = str(match.get("accountId") or "").strip()
            if real_id and real_id != target:
                # Cross-tenant safety: never repoint onto an account_number
                # already owned by a different user.
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
                    # The placeholder account we were handed is a duplicate
                    # of a real account that already exists for this user.
                    # Returning the accountIdKey here would cause the rest
                    # of ``sync_account_comprehensive`` to write positions/
                    # transactions/balances under the *placeholder*'s
                    # ``account.id`` — creating duplicate rows. Disable the
                    # placeholder and bail; the real account will be picked
                    # up by the next Beat fan-out.
                    logger.warning(
                        "etrade sync: placeholder account %d collides with "
                        "real account %d for user %d (account_number=%s); "
                        "disabling placeholder and skipping this run.",
                        account.id, existing.id, account.user_id, real_id,
                    )
                    try:
                        account.is_enabled = False
                        session.flush()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "etrade sync: failed to disable placeholder %d: %s",
                            account.id, exc,
                        )
                    return None, self._RESOLVE_REASON_PLACEHOLDER_COLLISION
                logger.info(
                    "etrade sync: auto-correcting account %d for user %d: "
                    "'%s' -> '%s'",
                    account.id, account.user_id, target, real_id,
                )
                account.account_number = real_id
                session.flush()

        key = str(match.get("accountIdKey") or "").strip()
        if not key:
            # Matched a row but its accountIdKey is empty — that's the
            # same "token is alive but this account is not usable" shape
            # as no_accounts; surface it the same way.
            return None, self._RESOLVE_REASON_NO_ACCOUNTS
        return key, None

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
        """Sync a single E*TRADE account end-to-end.

        ``account_number`` is *not* globally unique across tenants (D88 /
        ``no-hallucinated-ui-labels.mdc``): two different users can both
        hold an account numbered ``12345``. When ``user_id`` is supplied
        (the standard path from ``BrokerSyncService``), we scope the
        lookup to that user. If no ``user_id`` is passed and multiple
        accounts match, we refuse to guess and raise loudly rather than
        silently picking the first row.
        """
        query = (
            session.query(BrokerAccount)
            .filter(BrokerAccount.account_number == str(account_number))
            .filter(BrokerAccount.broker == BrokerType.ETRADE)
        )
        if user_id is not None:
            query = query.filter(BrokerAccount.user_id == int(user_id))
        matches = query.all()
        if not matches:
            raise ValueError(
                f"E*TRADE account {account_number} not found"
                + (f" for user {user_id}" if user_id is not None else "")
            )
        if len(matches) > 1:
            # user_id was None and account_number collided across tenants.
            # Fail-closed: the caller must pass user_id to disambiguate.
            raise ValueError(
                f"E*TRADE account_number {account_number!r} matched "
                f"{len(matches)} accounts across users; caller must pass "
                "user_id to disambiguate (multi-tenancy safety)."
            )
        account: BrokerAccount = matches[0]

        self._connect(account, session)
        account_id_key, reason = self._resolve_or_discover(account, session)
        if not account_id_key:
            if reason == self._RESOLVE_REASON_PLACEHOLDER_COLLISION:
                # Placeholder disabled inside the resolver; don't push the
                # user through the generic "please re-link" remediation —
                # the real account is fine and the next Beat fan-out will
                # sync it.
                return {
                    "status": "skipped",
                    "error": (
                        "E*TRADE placeholder account collided with an existing "
                        "real account for the same user; placeholder disabled. "
                        "The real account will sync on the next run."
                    ),
                    "permanent": False,
                }
            # Default / no_accounts path: token is alive but saw zero
            # usable accounts. User-actionable.
            return {
                "status": "error",
                "error": (
                    "E*TRADE /v1/accounts/list returned no usable account for this "
                    "token; please re-link."
                ),
            }

        results: Dict[str, Any] = {"status": "success"}

        try:
            # Fetch the portfolio once — E*TRADE's ``/portfolio`` is the
            # source for BOTH stock positions and options positions (they
            # are distinguished only by ``Product.securityType``). Calling
            # ``get_portfolio`` separately from ``_sync_positions`` and
            # ``_sync_options`` doubles latency per account and gets us
            # twice as close to the per-token rate limit for no benefit.
            assert self._client is not None
            portfolio_raw = self._client.get_portfolio(account_id_key)
            results.update(
                self._sync_positions(account, portfolio_raw, session)
            )
            results.update(
                self._sync_options(account, portfolio_raw, session)
            )
            results.update(self._sync_transactions(account, account_id_key, session))
            results.update(self._sync_balances(account, account_id_key, session))
        except ETradeAPIError as exc:
            # Permanent = user-actionable (reauth), transient = retry by Celery.
            logger.warning(
                "etrade sync: API error for user %s account %s: %s (permanent=%s)",
                account.user_id, account.id, exc, exc.permanent,
            )
            return {
                "status": "error",
                "error": str(exc),
                "permanent": exc.permanent,
            }

        session.flush()

        total_items = sum(v for v in results.values() if isinstance(v, int))
        logger.info(
            "etrade sync: user %s account %s (%s) synced %d total items: %s",
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
        """Write stock positions from a pre-fetched ``/portfolio`` payload.

        The caller (``sync_account_comprehensive``) owns the
        ``get_portfolio`` call so it can be shared with ``_sync_options``;
        this method is now pure-write. See PR #395 Copilot follow-up.
        """
        written = 0
        skipped = 0
        errors = 0
        options_seen = 0
        total = len(raw)
        touched_rows: List[Position] = []

        for pos_raw in raw:
            try:
                product = pos_raw.get("Product") or {}
                security_type = (product.get("securityType") or "").upper()
                if security_type == "OPTN":
                    # Options are written by _sync_options; skip here so we
                    # don't double-count them as stock positions.
                    options_seen += 1
                    skipped += 1
                    continue

                symbol = (product.get("symbol") or "").upper()
                if not symbol:
                    skipped += 1
                    continue

                qty = _to_decimal(pos_raw.get("quantity")) or Decimal("0")
                avg_cost = _to_decimal(pos_raw.get("costPerShare"))
                total_cost = _to_decimal(pos_raw.get("totalCost"))
                market_value = _to_decimal(pos_raw.get("marketValue"))
                day_gain = _to_decimal(pos_raw.get("daysGain"))
                day_gain_pct = _to_decimal(pos_raw.get("daysGainPct"))
                current_price = _to_decimal(pos_raw.get("Quick", {}).get("lastTrade"))

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
                if total_cost is not None:
                    fields["total_cost_basis"] = total_cost
                elif avg_cost is not None and qty != 0:
                    fields["total_cost_basis"] = avg_cost * abs(qty)
                if market_value is not None:
                    fields["market_value"] = market_value
                if current_price is not None:
                    fields["current_price"] = current_price
                elif market_value is not None and qty != 0:
                    fields["current_price"] = market_value / abs(qty)
                # Broker day_gain / day_gain_pct are advisory only (D141).
                # Log at debug for drift measurement; NEVER persist: the
                # broker baseline silently corrupts across splits and
                # cross-session refreshes.
                if day_gain is not None or day_gain_pct is not None:
                    logger.debug(
                        "etrade day_pnl advisory: symbol=%s broker_days_gain=%s "
                        "broker_days_gain_pct=%s",
                        symbol,
                        day_gain,
                        day_gain_pct,
                    )

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
                    touched_rows.append(existing)
                else:
                    new_pos = Position(
                        user_id=account.user_id,
                        account_id=account.id,
                        symbol=symbol,
                        currency=account.currency or "USD",
                        **fields,
                    )
                    session.add(new_pos)
                    touched_rows.append(new_pos)
                written += 1
            except Exception as exc:  # noqa: BLE001 — per-row isolation
                errors += 1
                logger.warning(
                    "etrade sync: failed to upsert position for user %s account %s: %s",
                    account.user_id, account.id, exc,
                )

        session.flush()
        assert written + skipped + errors == total, (
            f"etrade positions counter drift: {written}+{skipped}+{errors} != {total}"
        )
        logger.info(
            "etrade sync positions: user=%s account=%s written=%d skipped=%d "
            "errors=%d options_in_portfolio=%d",
            account.user_id, account.id, written, skipped, errors, options_seen,
        )

        # Server-side day P&L recompute (D141).
        day_pnl_stats = recompute_day_pnl_for_rows(session, touched_rows, "etrade")

        return {
            "positions_synced": written,
            "positions_skipped": skipped,
            "positions_errors": errors,
            **day_pnl_stats,
        }

    def _sync_options(
        self,
        account: BrokerAccount,
        raw: List[Dict[str, Any]],
        session: Session,
    ) -> Dict[str, Any]:
        """Write options positions from the same pre-fetched ``/portfolio``
        payload that ``_sync_positions`` consumed (see PR #395 Copilot
        follow-up)."""
        options = [
            p
            for p in raw
            if (p.get("Product") or {}).get("securityType", "").upper() == "OPTN"
        ]

        written = 0
        skipped = 0
        errors = 0
        total = len(options)

        for opt_raw in options:
            try:
                product = opt_raw.get("Product") or {}
                # E*TRADE's Product.symbol for an option holds the *underlying*
                # ticker (e.g. "MSFT"); the full OSI-style contract key lives
                # in Product.osiKey (e.g. "MSFT240119C00400000"). We store the
                # underlying in `underlying_symbol` and prefer osiKey for the
                # `symbol` column so downstream identity matches broker.
                underlying = (product.get("symbol") or "").upper()
                osi_key = (product.get("osiKey") or "").upper() or None
                strike = _to_float(product.get("strikePrice"))
                put_call = (product.get("callPut") or "CALL").upper()
                expiry = _parse_option_expiry(product)
                qty = int(_to_float(opt_raw.get("quantity")))
                market_value = _to_decimal(opt_raw.get("marketValue"))
                cost_per_share = _to_decimal(opt_raw.get("costPerShare"))

                if not underlying or not expiry or strike <= 0:
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
                    if market_value is not None and qty:
                        existing.current_price = market_value / max(
                            abs(qty) * 100, 1
                        )
                    if cost_per_share is not None and qty:
                        existing.total_cost = cost_per_share * abs(qty) * 100
                else:
                    session.add(
                        Option(
                            user_id=account.user_id,
                            account_id=account.id,
                            symbol=(
                                osi_key
                                or f"{underlying}{expiry:%y%m%d}"
                                f"{put_call[0]}{strike:.0f}"
                            ),
                            underlying_symbol=underlying,
                            strike_price=strike,
                            expiry_date=expiry,
                            option_type=put_call,
                            multiplier=100,
                            open_quantity=qty,
                            currency=account.currency or "USD",
                            data_source="ETRADE_API",
                        )
                    )
                written += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "etrade sync: failed to upsert option for user %s account %s: %s",
                    account.user_id, account.id, exc,
                )

        # Broker-level capability flag: if we ever see an option on this
        # account, mark options_enabled so downstream UI (Options pages,
        # strategy rules) surfaces correctly.
        if written > 0 and not account.options_enabled:
            account.options_enabled = True

        session.flush()
        assert written + skipped + errors == total, (
            f"etrade options counter drift: {written}+{skipped}+{errors} != {total}"
        )
        logger.info(
            "etrade sync options: user=%s account=%s written=%d skipped=%d errors=%d",
            account.user_id, account.id, written, skipped, errors,
        )
        return {
            "options_synced": written,
            "options_skipped": skipped,
            "options_errors": errors,
        }

    def _sync_transactions(
        self,
        account: BrokerAccount,
        account_id_key: str,
        session: Session,
    ) -> Dict[str, Any]:
        assert self._client is not None
        raw = self._client.get_transactions(account_id_key)

        written = 0
        skipped = 0
        errors = 0
        trades_created = 0
        dividends_created = 0
        total = len(raw)

        for txn_raw in raw:
            try:
                ext_id = str(txn_raw.get("transactionId") or "").strip()
                if not ext_id:
                    skipped += 1
                    continue

                brokerage = txn_raw.get("brokerage") or {}
                product = brokerage.get("product") or {}
                action = (txn_raw.get("transactionType") or "").upper()
                symbol = (product.get("symbol") or brokerage.get("symbol") or "").upper()
                qty = _to_float(brokerage.get("quantity"))
                price = _to_float(brokerage.get("price"))
                commission = _to_float(brokerage.get("fee"))
                amount = _to_float(txn_raw.get("amount"), qty * price)
                net_amount = amount - commission
                txn_date = _parse_etrade_datetime(txn_raw.get("transactionDate"))
                description = (txn_raw.get("description") or "").strip() or None
                txn_type = _ETRADE_TYPE_MAP.get(action, TransactionType.OTHER)

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
                            action=action[:10] if action else None,
                            quantity=qty,
                            trade_price=price,
                            amount=amount,
                            net_amount=net_amount,
                            commission=commission,
                            currency=account.currency or "USD",
                            transaction_date=txn_date,
                            description=description,
                            source="ETRADE",
                        )
                    )
                    written += 1
                else:
                    skipped += 1

                # Mirror trades (idempotent on execution_id).
                if action in _TRADE_ETRADE_TYPES and symbol and qty:
                    side = "BUY" if action in {"BUY", "BUY_TO_COVER"} else "SELL"
                    existing_trade = (
                        session.query(Trade)
                        .filter(
                            Trade.account_id == account.id,
                            Trade.execution_id == ext_id,
                        )
                        .first()
                    )
                    if existing_trade is None:
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
                                execution_time=txn_date,
                                status="FILLED",
                                is_opening=(side == "BUY"),
                                is_paper_trade=False,
                            )
                        )
                        trades_created += 1

                # Mirror dividends (idempotent on external_id).
                if txn_type == TransactionType.DIVIDEND and symbol:
                    existing_div = (
                        session.query(Dividend)
                        .filter(
                            Dividend.account_id == account.id,
                            Dividend.external_id == ext_id,
                        )
                        .first()
                    )
                    if existing_div is None:
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
                                source="etrade",
                            )
                        )
                        dividends_created += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "etrade sync: failed to upsert transaction for user %s account %s: %s",
                    account.user_id, account.id, exc,
                )

        session.flush()
        assert written + skipped + errors == total, (
            f"etrade transactions counter drift: {written}+{skipped}+{errors} != {total}"
        )
        logger.info(
            "etrade sync transactions: user=%s account=%s written=%d skipped=%d "
            "errors=%d trades=%d dividends=%d",
            account.user_id, account.id, written, skipped, errors,
            trades_created, dividends_created,
        )
        return {
            "transactions_synced": written,
            "transactions_skipped": skipped,
            "transactions_errors": errors,
            "trades_synced": trades_created,
            "dividends_synced": dividends_created,
        }

    def _sync_balances(
        self,
        account: BrokerAccount,
        account_id_key: str,
        session: Session,
    ) -> Dict[str, Any]:
        assert self._client is not None
        bal = self._client.get_balance(account_id_key)
        if not bal:
            logger.warning(
                "etrade sync balances: user=%s account=%s — empty balance payload",
                account.user_id, account.id,
            )
            return {"balances_synced": 0, "balances_skipped": 1, "balances_errors": 0}

        computed = bal.get("Computed") or {}
        # ``RealTimeValues`` is a top-level sibling of ``Computed`` in the
        # E*TRADE ``BalanceResponse`` envelope, not a child. Reading it off
        # ``computed`` silently produced ``None`` for net_liq / equity even
        # on well-formed payloads (fixture pins this in
        # ``test_sync_service_records_real_time_balance``).
        real_time = bal.get("RealTimeValues") or {}
        cash_balance = _to_decimal(computed.get("cashBalance"))
        net_liq = _to_decimal(real_time.get("totalAccountValue"))
        available_funds = _to_decimal(computed.get("cashAvailableForWithdrawal"))
        buying_power = _to_decimal(
            computed.get("cashBuyingPower") or computed.get("marginBuyingPower")
        )
        equity = _to_decimal(real_time.get("totalLongValue"))

        new_bal = AccountBalance(
            user_id=account.user_id,
            broker_account_id=account.id,
            balance_date=datetime.now(timezone.utc),
            cash_balance=cash_balance,
            net_liquidation=net_liq,
            buying_power=buying_power,
            available_funds=available_funds,
            equity=equity,
            data_source="ETRADE_API",
        )
        session.add(new_bal)
        session.flush()
        logger.info(
            "etrade sync balances: user=%s account=%s written=1",
            account.user_id, account.id,
        )
        return {"balances_synced": 1, "balances_skipped": 0, "balances_errors": 0}


__all__ = ["ETradeSyncService"]
