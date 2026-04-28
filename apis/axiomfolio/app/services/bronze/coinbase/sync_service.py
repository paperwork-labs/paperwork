"""Coinbase bronze-layer sync (v2 wallet API).

Read-only positions (spot wallets), transactions, and FILLED trade rows
for FIFO closing-lot reconstruction via ``reconcile_closing_lots``.

medallion: bronze
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.account_balance import AccountBalance
from app.models.broker_account import BrokerAccount, BrokerType
from app.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from app.models.position import Position, PositionStatus, PositionType
from app.models.trade import Trade
from app.models.transaction import Transaction, TransactionType
from app.services.bronze.coinbase.client import (
    CoinbaseAPIError,
    CoinbaseBronzeClient,
)
from app.services.oauth.encryption import (
    EncryptionDecryptError,
    EncryptionUnavailableError,
    decrypt,
)
from app.services.ops.bronze_silver_bridge import reconcile_closing_lots

logger = logging.getLogger(__name__)

_COINBASE_OAUTH_SLUG = "coinbase"
_COINBASE_ACCOUNT_TYPES: Tuple[BrokerType, ...] = (BrokerType.COINBASE,)
_PLACEHOLDER_PREFIX = "COINBASE_"
_EXECUTION_ID_MAX_LEN = 50

_FIAT_CODES = frozenset(
    {
        "USD",
        "EUR",
        "GBP",
        "CAD",
        "AUD",
        "JPY",
        "CHF",
    }
)


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _money_amount(money: Any) -> Optional[Decimal]:
    if not isinstance(money, dict):
        return None
    return _to_decimal(money.get("amount"))


def _parse_iso_dt(value: Any) -> datetime:
    if value is None or value == "":
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        raw = str(value).strip().replace("Z", "+00:00")
        result = datetime.fromisoformat(raw)
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _normalize_crypto_symbol(currency_code: str) -> str:
    code = (currency_code or "").strip().upper()
    if not code or code in _FIAT_CODES:
        return ""
    if "-" in code:
        return code
    return f"{code}-USD"


def _synthetic_external_id(account_id: str, txn_id: str) -> str:
    raw = f"{account_id}|{txn_id}".encode("utf-8")
    digest = hashlib.blake2b(raw, digest_size=8).hexdigest()
    return f"cbt_{digest}"


def _trade_execution_id(txn_id: str) -> str:
    tid = (txn_id or "").strip()
    candidate = f"cb_{tid}"
    if len(candidate) <= _EXECUTION_ID_MAX_LEN:
        return candidate
    digest = hashlib.blake2b(tid.encode("utf-8"), digest_size=16).hexdigest()
    out = f"cb_{digest}"
    assert len(out) <= _EXECUTION_ID_MAX_LEN
    return out


class CoinbaseSyncService:
    """Bronze ingestion from Coinbase ``/v2`` wallet endpoints."""

    def __init__(self, client: Optional[CoinbaseBronzeClient] = None) -> None:
        self._client: Optional[CoinbaseBronzeClient] = client

    @staticmethod
    def _oauth_broker_slug_for_account(account: BrokerAccount) -> str:
        if account.broker == BrokerType.COINBASE:
            return _COINBASE_OAUTH_SLUG
        raise ConnectionError(
            "This account is not a Coinbase broker; cannot load Coinbase OAuth."
        )

    def _load_connection(
        self, account: BrokerAccount, session: Session
    ) -> BrokerOAuthConnection:
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
                "No Coinbase OAuth connection found. Link Coinbase via the "
                "Connections page before syncing."
            )
        if conn.status != OAuthConnectionStatus.ACTIVE.value:
            raise ConnectionError(
                f"Coinbase OAuth connection is {conn.status}; please re-link "
                "on the Connections page."
            )
        if not conn.access_token_encrypted:
            raise ConnectionError(
                "Coinbase OAuth connection is missing an access token; please "
                "re-link on the Connections page."
            )
        return conn

    def _connect(self, account: BrokerAccount, session: Session) -> None:
        if self._client is not None:
            return
        conn = self._load_connection(account, session)
        try:
            access_token = decrypt(conn.access_token_encrypted)
        except (EncryptionUnavailableError, EncryptionDecryptError) as exc:
            raise ConnectionError(
                f"Failed to decrypt Coinbase credentials: {exc}. Re-link on "
                "the Connections page."
            ) from exc
        self._client = CoinbaseBronzeClient(access_token=access_token)

    _RESOLVE_REASON_NO_USER = "no_user"
    _RESOLVE_REASON_PLACEHOLDER_COLLISION = "placeholder_collision"

    def _resolve_or_discover(
        self, account: BrokerAccount, session: Session
    ) -> Tuple[Optional[str], Optional[str]]:
        assert self._client is not None
        try:
            user = self._client.get_user()
        except CoinbaseAPIError as exc:
            logger.warning(
                "coinbase sync: user lookup failed for account %s user %s: %s",
                account.id,
                account.user_id,
                exc,
            )
            return None, self._RESOLVE_REASON_NO_USER
        uid = str((user.get("id") or "")).strip()
        if not uid:
            return None, self._RESOLVE_REASON_NO_USER

        target = (account.account_number or "").strip()
        placeholder = (
            not target
            or target == "COINBASE_OAUTH"
            or target.startswith(_PLACEHOLDER_PREFIX)
        )

        if not placeholder and target != uid:
            logger.info(
                "coinbase sync: account %s user %s keeping account_number %s "
                "(API user %s)",
                account.id,
                account.user_id,
                target,
                uid,
            )
            return target, None

        if placeholder:
            existing = (
                session.query(BrokerAccount)
                .filter(
                    BrokerAccount.user_id == account.user_id,
                    BrokerAccount.broker == account.broker,
                    BrokerAccount.account_number == uid,
                )
                .first()
            )
            if existing and existing.id != account.id:
                logger.warning(
                    "coinbase sync: placeholder %d collides with %d for user %s",
                    account.id,
                    existing.id,
                    account.user_id,
                )
                try:
                    account.is_enabled = False
                    session.flush()
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "coinbase sync: failed to disable placeholder %s: %s",
                        account.id,
                        exc,
                    )
                return None, self._RESOLVE_REASON_PLACEHOLDER_COLLISION
            account.account_number = uid
            session.flush()
        return uid, None

    def sync_account_comprehensive(
        self,
        account_number: str,
        session: Session,
        *,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        query = (
            session.query(BrokerAccount)
            .filter(BrokerAccount.account_number == str(account_number))
            .filter(BrokerAccount.broker.in_(_COINBASE_ACCOUNT_TYPES))
        )
        if user_id is not None:
            query = query.filter(BrokerAccount.user_id == int(user_id))
        matches = query.all()
        if not matches:
            raise ValueError(
                f"Coinbase account {account_number} not found"
                + (f" for user {user_id}" if user_id is not None else "")
            )
        if len(matches) > 1:
            raise ValueError(
                f"Coinbase account_number {account_number!r} matched "
                f"{len(matches)} accounts; pass user_id (multi-tenancy)."
            )
        account = matches[0]

        self._connect(account, session)
        resolved, reason = self._resolve_or_discover(account, session)
        if not resolved:
            if reason == self._RESOLVE_REASON_PLACEHOLDER_COLLISION:
                return {
                    "status": "skipped",
                    "error": (
                        "Coinbase placeholder collided with an existing account "
                        "for this user; placeholder disabled."
                    ),
                    "permanent": False,
                }
            return {
                "status": "error",
                "error": "Coinbase /v2/user did not return a usable id; re-link.",
            }

        try:
            assert self._client is not None
            raw_accounts = self._client.list_all_accounts()
            results: Dict[str, Any] = {"status": "success"}
            results.update(self._sync_positions(account, raw_accounts, session))
            gtx = self._gather_transactions(raw_accounts)
            all_txns = gtx["pairs"]
            results["wallets_processed"] = gtx["wallets_processed"]
            results["wallets_tx_ok"] = gtx["wallets_tx_ok"]
            results["wallets_tx_failed"] = gtx["wallets_tx_failed"]
            wf = gtx["wallets_tx_failed"]
            wo = gtx["wallets_tx_ok"]
            if wf > 0:
                if wo > 0:
                    results["status"] = "partial"
                else:
                    results["status"] = "error"
                    results["error"] = (
                        "Coinbase transaction list failed for all wallets"
                    )
            results.update(self._sync_transactions(account, all_txns, session))
            results.update(self._sync_trades(account, all_txns, session))
            results.update(self._sync_balances(account, raw_accounts, session))
        except CoinbaseAPIError as exc:
            logger.warning(
                "coinbase sync: API error user %s account %s: %s permanent=%s",
                account.user_id,
                account.id,
                exc,
                exc.permanent,
            )
            return {
                "status": "error",
                "error": str(exc),
                "permanent": exc.permanent,
            }

        try:
            with session.begin_nested():
                match_result = reconcile_closing_lots(session, account)
            results["closed_lots_created"] = match_result.created
            results["closed_lots_updated"] = match_result.updated
            if match_result.unmatched_quantity > 0:
                logger.warning(
                    "coinbase sync: account %s unmatched sell qty %s (%s)",
                    account.id,
                    match_result.unmatched_quantity,
                    match_result.warnings[0] if match_result.warnings else "",
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "coinbase sync: closing-lot reconciliation failed account %s: %s",
                account.id,
                exc,
            )
            results["closed_lots_error"] = str(exc)

        session.flush()
        logger.info(
            "coinbase sync: user %s account %s complete %s",
            account.user_id,
            account.id,
            results,
        )
        return results

    def _gather_transactions(
        self, raw_accounts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        assert self._client is not None
        out: List[Tuple[str, Dict[str, Any]]] = []
        wallets_tx_ok = 0
        wallets_tx_failed = 0
        wallets_attempted = 0
        for acct in raw_accounts:
            acct_id = str(acct.get("id") or "").strip()
            if not acct_id:
                continue
            wallets_attempted += 1
            try:
                rows = self._client.list_transactions_for_account(acct_id)
            except CoinbaseAPIError as exc:
                wallets_tx_failed += 1
                logger.warning(
                    "coinbase sync: transactions for wallet %s failed: %s",
                    acct_id,
                    exc,
                )
                continue
            wallets_tx_ok += 1
            for txn in rows:
                out.append((acct_id, txn))
        assert (
            wallets_attempted == wallets_tx_ok + wallets_tx_failed
        ), "coinbase wallet tx counter drift"
        wallets_processed = wallets_attempted
        return {
            "pairs": out,
            "wallets_processed": wallets_processed,
            "wallets_tx_ok": wallets_tx_ok,
            "wallets_tx_failed": wallets_tx_failed,
        }

    def _sync_positions(
        self,
        account: BrokerAccount,
        raw_accounts: List[Dict[str, Any]],
        session: Session,
    ) -> Dict[str, Any]:
        aggregates: Dict[str, Decimal] = {}
        consumed = 0
        skipped = 0
        errors = 0
        total = len(raw_accounts)

        for row in raw_accounts:
            try:
                acct_type = (row.get("type") or "").lower()
                cur = row.get("currency") or {}
                code = (cur.get("code") or "").upper()
                if not code:
                    skipped += 1
                    continue
                if acct_type == "fiat" or code in _FIAT_CODES:
                    skipped += 1
                    continue
                sym = _normalize_crypto_symbol(code)
                if not sym:
                    skipped += 1
                    continue
                bal = _money_amount(row.get("balance")) or Decimal("0")
                if bal == 0:
                    skipped += 1
                    continue
                aggregates[sym] = aggregates.get(sym, Decimal("0")) + bal
                consumed += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "coinbase sync: position row failed user %s account %s: %s",
                    account.user_id,
                    account.id,
                    exc,
                )

        assert (
            consumed + skipped + errors == total
        ), f"coinbase position row drift {consumed}+{skipped}+{errors}!={total}"

        written = 0
        upsert_errors = 0
        n_agg = len(aggregates)
        for sym, qty in aggregates.items():
            try:
                fields = {
                    "quantity": qty,
                    "instrument_type": "CRYPTO",
                    "position_type": (
                        PositionType.LONG if qty >= 0 else PositionType.SHORT
                    ),
                    "status": (
                        PositionStatus.OPEN if qty != 0 else PositionStatus.CLOSED
                    ),
                }
                existing = (
                    session.query(Position)
                    .filter(
                        Position.user_id == account.user_id,
                        Position.account_id == account.id,
                        Position.symbol == sym,
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
                            symbol=sym,
                            currency=account.currency or "USD",
                            **fields,
                        )
                    )
                written += 1
            except Exception as exc:  # noqa: BLE001
                upsert_errors += 1
                logger.warning(
                    "coinbase sync: upsert position user %s account %s: %s",
                    account.user_id,
                    account.id,
                    exc,
                )

        session.flush()
        assert (
            written + upsert_errors == n_agg
        ), f"coinbase aggregate upsert drift {written}+{upsert_errors}!={n_agg}"
        logger.info(
            "coinbase positions: user=%s account=%s symbols=%d row_skipped=%d "
            "row_errors=%d upsert_errors=%d",
            account.user_id,
            account.id,
            written,
            skipped,
            errors,
            upsert_errors,
        )
        return {
            "positions_synced": written,
            "positions_skipped": skipped,
            "positions_errors": errors + upsert_errors,
        }

    @staticmethod
    def _txn_type_map(coinbase_type: str) -> TransactionType:
        t = (coinbase_type or "").lower()
        if t in ("buy",):
            return TransactionType.BUY
        if t in ("sell",):
            return TransactionType.SELL
        if t in ("fiat_deposit",):
            return TransactionType.DEPOSIT
        if t in ("fiat_withdrawal",):
            return TransactionType.WITHDRAWAL
        if t in ("send",):
            return TransactionType.WITHDRAWAL
        if t in ("receive",):
            return TransactionType.TRANSFER
        if t in ("transfer",):
            return TransactionType.TRANSFER
        if t in ("advanced_trade_fill", "trade"):
            return TransactionType.BUY
        return TransactionType.OTHER

    def _sync_transactions(
        self,
        account: BrokerAccount,
        pairs: List[Tuple[str, Dict[str, Any]]],
        session: Session,
    ) -> Dict[str, Any]:
        written = 0
        skipped = 0
        errors = 0
        total = len(pairs)

        for wallet_id, txn in pairs:
            try:
                txn_id = str(txn.get("id") or "").strip()
                if not txn_id:
                    skipped += 1
                    continue
                ext = _synthetic_external_id(wallet_id, txn_id)
                cb_type = str(txn.get("type") or "")
                txn_type = self._txn_type_map(cb_type)
                amt_obj = txn.get("amount") or {}
                native = txn.get("native_amount") or {}
                cur_code = (
                    str(amt_obj.get("currency") or "").upper()
                    if isinstance(amt_obj, dict)
                    else ""
                )
                sym = _normalize_crypto_symbol(cur_code) or cur_code or "CASH"
                qty = _money_amount(amt_obj) or Decimal("0")
                native_amt = _money_amount(native) or Decimal("0")
                trade_px = Decimal("0")
                if qty != 0:
                    try:
                        trade_px = abs(native_amt / qty)
                    except (InvalidOperation, ZeroDivisionError):
                        trade_px = Decimal("0")
                when = _parse_iso_dt(txn.get("created_at"))

                existing = (
                    session.query(Transaction)
                    .filter(
                        Transaction.account_id == account.id,
                        Transaction.external_id == ext,
                    )
                    .first()
                )
                if existing is None:
                    session.add(
                        Transaction(
                            account_id=account.id,
                            external_id=ext,
                            symbol=sym,
                            transaction_type=txn_type,
                            action=(cb_type[:10] if cb_type else None),
                            quantity=float(qty),
                            trade_price=float(trade_px),
                            amount=float(native_amt),
                            net_amount=float(native_amt),
                            commission=0.0,
                            currency=account.currency or "USD",
                            transaction_date=when,
                            description=(
                                str(txn.get("description") or "")[:500] or None
                            ),
                            source="COINBASE",
                        )
                    )
                    written += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "coinbase sync: transaction upsert failed user %s: %s",
                    account.user_id,
                    exc,
                )

        session.flush()
        assert (
            written + skipped + errors == total
        ), f"coinbase txn counter drift {written}+{skipped}+{errors}!={total}"
        return {
            "transactions_synced": written,
            "transactions_skipped": skipped,
            "transactions_errors": errors,
        }

    def _extract_fee_usd(self, txn: Dict[str, Any]) -> Decimal:
        fee_total = Decimal("0")
        for key in ("buy", "sell", "trade"):
            block = txn.get(key)
            if not isinstance(block, dict):
                continue
            fee = block.get("fee")
            if isinstance(fee, dict):
                if str(fee.get("currency") or "").upper() == "USD":
                    amt = _money_amount(fee)
                    if amt is not None:
                        fee_total += abs(amt)
        return fee_total

    def _sync_trades(
        self,
        account: BrokerAccount,
        pairs: List[Tuple[str, Dict[str, Any]]],
        session: Session,
    ) -> Dict[str, Any]:
        written = 0
        skipped = 0
        errors = 0
        total = len(pairs)

        for wallet_id, txn in pairs:
            try:
                txn_id = str(txn.get("id") or "").strip()
                status = (txn.get("status") or "").lower()
                if not txn_id or status != "completed":
                    skipped += 1
                    continue

                cb_type = (txn.get("type") or "").lower()
                exec_id = _trade_execution_id(txn_id)

                side: Optional[str] = None
                is_opening = True
                symbol = ""
                qty = Decimal("0")
                price = Decimal("0")
                commission = self._extract_fee_usd(txn)
                execution_time = _parse_iso_dt(txn.get("created_at"))
                meta: Dict[str, Any] = {"asset_category": "CRYPTO"}

                if cb_type == "buy":
                    side = "BUY"
                    is_opening = True
                    amt = txn.get("amount") or {}
                    native = txn.get("native_amount") or {}
                    code = str(amt.get("currency") or "").upper()
                    symbol = _normalize_crypto_symbol(code)
                    qty = abs(_money_amount(amt) or Decimal("0"))
                    native_usd = abs(_money_amount(native) or Decimal("0"))
                    if qty > 0:
                        price = native_usd / qty
                elif cb_type == "sell":
                    side = "SELL"
                    is_opening = False
                    amt = txn.get("amount") or {}
                    native = txn.get("native_amount") or {}
                    code = str(amt.get("currency") or "").upper()
                    symbol = _normalize_crypto_symbol(code)
                    qty = abs(_money_amount(amt) or Decimal("0"))
                    native_usd = abs(_money_amount(native) or Decimal("0"))
                    if qty > 0:
                        price = native_usd / qty
                elif cb_type == "advanced_trade_fill":
                    fill = txn.get("advanced_trade_fill") or {}
                    if not isinstance(fill, dict):
                        skipped += 1
                        continue
                    order_side = (fill.get("order_side") or "").upper()
                    if order_side == "BUY":
                        side = "BUY"
                        is_opening = True
                    elif order_side == "SELL":
                        side = "SELL"
                        is_opening = False
                    else:
                        skipped += 1
                        continue
                    product = str(fill.get("product_id") or "").upper()
                    symbol = (
                        product if "-" in product else _normalize_crypto_symbol(product)
                    )
                    amt = txn.get("amount") or {}
                    qty = abs(_money_amount(amt) or Decimal("0"))
                    price = abs(_to_decimal(fill.get("fill_price")) or Decimal("0"))
                    if price == 0 and qty > 0:
                        native = txn.get("native_amount") or {}
                        native_usd = abs(_money_amount(native) or Decimal("0"))
                        try:
                            price = native_usd / qty
                        except (InvalidOperation, ZeroDivisionError):
                            price = Decimal("0")
                    comm = fill.get("commission")
                    if comm is not None:
                        cdec = _to_decimal(comm)
                        if cdec is not None:
                            commission = abs(cdec)
                elif cb_type == "trade":
                    tr = txn.get("trade") or {}
                    if not isinstance(tr, dict):
                        skipped += 1
                        continue
                    # Best-effort: infer side from amount sign if present
                    amt = txn.get("amount") or {}
                    raw_amt = _money_amount(amt) or Decimal("0")
                    if raw_amt >= 0:
                        side = "BUY"
                        is_opening = True
                    else:
                        side = "SELL"
                        is_opening = False
                    code = str(amt.get("currency") or "").upper()
                    symbol = _normalize_crypto_symbol(code)
                    qty = abs(raw_amt)
                    native = txn.get("native_amount") or {}
                    native_usd = abs(_money_amount(native) or Decimal("0"))
                    if qty > 0:
                        price = native_usd / qty
                else:
                    skipped += 1
                    continue

                if not side or not symbol or qty <= 0 or price < 0:
                    skipped += 1
                    continue

                existing_trade = (
                    session.query(Trade)
                    .filter(
                        Trade.account_id == account.id,
                        Trade.execution_id == exec_id,
                    )
                    .first()
                )
                if existing_trade is not None:
                    skipped += 1
                    continue

                total_value = qty * price
                session.add(
                    Trade(
                        account_id=account.id,
                        symbol=symbol,
                        side=side,
                        quantity=qty,
                        price=price,
                        total_value=total_value,
                        commission=commission,
                        execution_id=exec_id,
                        execution_time=execution_time,
                        status="FILLED",
                        is_opening=is_opening,
                        is_paper_trade=False,
                        trade_metadata=meta,
                    )
                )
                written += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "coinbase sync: trade upsert failed user %s wallet %s: %s",
                    account.user_id,
                    wallet_id,
                    exc,
                )

        session.flush()
        assert (
            written + skipped + errors == total
        ), f"coinbase trades counter drift {written}+{skipped}+{errors}!={total}"
        return {
            "trades_synced": written,
            "trades_skipped": skipped,
            "trades_errors": errors,
        }

    def _sync_balances(
        self,
        account: BrokerAccount,
        raw_accounts: List[Dict[str, Any]],
        session: Session,
    ) -> Dict[str, Any]:
        cash_total = Decimal("0")
        for row in raw_accounts:
            acct_type = (row.get("type") or "").lower()
            cur = row.get("currency") or {}
            code = (cur.get("code") or "").upper()
            if acct_type != "fiat" or code != "USD":
                continue
            bal = _money_amount(row.get("balance"))
            if bal is not None:
                cash_total += bal

        if cash_total == 0 and not any(
            (r.get("type") or "").lower() == "fiat" for r in raw_accounts
        ):
            logger.warning(
                "coinbase sync: no USD fiat wallet user=%s account=%s",
                account.user_id,
                account.id,
            )
            return {
                "balances_synced": 0,
                "balances_skipped": 1,
                "balances_errors": 0,
            }

        new_bal = AccountBalance(
            user_id=account.user_id,
            broker_account_id=account.id,
            balance_date=datetime.now(timezone.utc),
            cash_balance=cash_total,
            net_liquidation=cash_total,
            buying_power=cash_total,
            available_funds=cash_total,
            equity=cash_total,
            data_source="COINBASE_API",
        )
        session.add(new_bal)
        session.flush()
        return {"balances_synced": 1, "balances_skipped": 0, "balances_errors": 0}


__all__ = ["CoinbaseSyncService"]
