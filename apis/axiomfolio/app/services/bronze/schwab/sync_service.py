"""Medallion layer: bronze. See docs/ARCHITECTURE.md and D127.

medallion: bronze
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.broker_account import BrokerAccount
from app.models.position import Position, PositionType, PositionStatus
from app.models.transaction import Transaction, TransactionType, Dividend
from app.models.trade import Trade
from app.models.account_balance import AccountBalance
from app.services.clients.schwab_client import SchwabClient
from app.services.portfolio.account_credentials_service import (
    account_credentials_service,
    CredentialsNotFoundError,
)
# medallion: allow silver for post-ingest tax-lot closing reconciliation
from app.services.silver.portfolio.closing_lot_matcher import (
    MatchResult,
    reconcile_closing_lots,
)
# medallion: allow silver for day PnL refresh after transaction ingest
from app.services.silver.portfolio.day_pnl_service import (
    recompute_day_pnl_for_rows,
    recompute_position_day_pnl,
)
from app.models.options import Option
from app.config import settings

logger = logging.getLogger(__name__)

# Redis observability: closing-lot reconciliation failure count. ``incr`` then
# ``expire`` on every failure sets a 7-day TTL from that event (fixed window per
# failure, not a single TTL from the first failure only).
RECONCILE_ANOMALY_KEY = "reconcile:anomaly:total"
_RECONCILE_ANOMALY_TTL_S = 60 * 60 * 24 * 7


def _record_reconcile_closing_lots_anomaly() -> None:
    try:
        # medallion: allow silver for market-data/Redis lookaside in sync I/O path
        from app.services.silver.market.market_data_service import infra

        r = getattr(infra, "redis_client", None)
        if r is None:
            return
        r.incr(RECONCILE_ANOMALY_KEY)
        r.expire(RECONCILE_ANOMALY_KEY, _RECONCILE_ANOMALY_TTL_S)
    except Exception as e:  # pragma: no cover - best-effort
        logger.warning("reconcile_anomaly: redis increment failed: %s", e)

SCHWAB_TYPE_MAP = {
    "TRADE": TransactionType.BUY,
    "RECEIVE_AND_DELIVER": TransactionType.TRANSFER,
    "DIVIDEND_OR_INTEREST": TransactionType.DIVIDEND,
    "JOURNAL": TransactionType.OTHER,
    "WIRE_IN": TransactionType.DEPOSIT,
    "WIRE_OUT": TransactionType.WITHDRAWAL,
    "ACH_IN": TransactionType.DEPOSIT,
    "ACH_OUT": TransactionType.WITHDRAWAL,
    "ACH_RECEIPT": TransactionType.DEPOSIT,
    "ACH_DISBURSEMENT": TransactionType.WITHDRAWAL,
    "CASH_RECEIPT": TransactionType.DEPOSIT,
    "CASH_DISBURSEMENT": TransactionType.WITHDRAWAL,
    "ELECTRONIC_FUND": TransactionType.DEPOSIT,
    "MEMORANDUM": TransactionType.OTHER,
    "MARGIN_CALL": TransactionType.OTHER,
    "MONEY_MARKET": TransactionType.OTHER,
    "SMA_ADJUSTMENT": TransactionType.OTHER,
}

_TRADE_TYPES = {"TRADE", "RECEIVE_AND_DELIVER"}


def _schwab_filled_is_opening_and_metadata(
    t: dict, side: str
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Derive ``is_opening`` and option ``trade_metadata`` for a filled Schwab leg.

    Schwab's Trader API provides ``positionEffect`` (OPENING/CLOSING) on transfer
    items. When present, it must drive ``is_opening`` so short options and
    covers match :func:`~app.services.silver.portfolio.closing_lot_matcher.reconcile_closing_lots`.
    When absent, we fall back to the equity-style heuristic (BUY opens, SELL closes),
    which is correct for long options only.
    """
    sym = (t.get("symbol") or "").upper()
    asset_type = (t.get("instrument_asset_type") or "").upper()
    is_option = asset_type in ("OPTION", "EQUITY_OPTION")
    if not is_option and (len(sym) > 15 or " " in sym):
        is_option = True
    pe = (t.get("position_effect") or "").upper()
    if pe in ("OPENING", "CLOSING"):
        is_opening = pe == "OPENING"
    else:
        is_opening = side == "BUY"
    if not is_option:
        return is_opening, None
    return is_opening, {"asset_category": "OPT", "multiplier": 100}


class SchwabSyncService:
    """Schwab account sync: positions, transactions, dividends, balances, trades."""

    def __init__(self, client: SchwabClient | None = None):
        self._client = client or SchwabClient()

    async def _connect(self, account: BrokerAccount, session: Session) -> None:
        """Authenticate the Schwab client using stored OAuth tokens."""
        try:
            payload = account_credentials_service.get_decrypted(account.id, session)
            access_token = payload.get("access_token")
            refresh_token = payload.get("refresh_token")
            ok = await self._client.connect_with_credentials(
                access_token=access_token or "",
                refresh_token=refresh_token or "",
            )
            if not ok:
                raise ConnectionError(
                    f"Schwab sync: connect_with_credentials returned False for "
                    f"account {account.account_number}. Check SCHWAB_CLIENT_ID "
                    f"and SCHWAB_REDIRECT_URI are configured."
                )

            def _persist_refreshed_tokens(new_access: str, new_refresh: str) -> None:
                """Callback: persist refreshed OAuth tokens back to AccountCredentials."""
                try:
                    account_credentials_service.update_encrypted(
                        account.id,
                        {"access_token": new_access, "refresh_token": new_refresh},
                        session,
                    )
                    session.flush()
                    logger.info("Schwab sync: persisted refreshed tokens for account %s", account.account_number)
                except Exception as persist_exc:
                    logger.error("Schwab sync: failed to persist refreshed tokens: %s", persist_exc)

            self._client.set_token_refresh_callback(_persist_refreshed_tokens)
        except CredentialsNotFoundError:
            raise ConnectionError(
                "No Schwab credentials found. Please link your Schwab account "
                "via the Connections page (OAuth flow) before syncing."
            )
        except Exception as exc:
            err_str = str(exc).lower()
            if "encrypt" in err_str or "token" in err_str or "fernet" in err_str:
                raise ConnectionError(
                    f"Invalid encryption token — please re-link your Schwab account "
                    f"on the Connections page. (Original error: {exc})"
                ) from exc
            raise

    async def _resolve_or_discover(self, account: BrokerAccount, session: Session) -> None:
        """If account_number is a placeholder, discover real accounts and fix it."""
        real_looking = (
            account.account_number
            and account.account_number not in ("SCHWAB_OAUTH", "")
            and not account.account_number.startswith("SCHWAB_")
        )
        if real_looking:
            return

        logger.warning(
            "Schwab sync: account %d has placeholder number '%s', "
            "attempting account discovery",
            account.id, account.account_number,
        )
        schwab_accounts = await self._client.get_accounts()
        if not schwab_accounts:
            logger.error("Schwab sync: account discovery returned 0 accounts")
            return

        first = schwab_accounts[0]
        real_num = first.get("account_number", "")
        if not real_num:
            return

        existing = (
            session.query(BrokerAccount)
            .filter(
                BrokerAccount.user_id == account.user_id,
                BrokerAccount.broker == account.broker,
                BrokerAccount.account_number == real_num,
            )
            .first()
        )
        if existing and existing.id != account.id:
            logger.info(
                "Schwab sync: real account %s already exists (id=%d), "
                "skipping placeholder %d",
                real_num, existing.id, account.id,
            )
            return

        logger.info(
            "Schwab sync: auto-correcting account %d: '%s' -> '%s'",
            account.id, account.account_number, real_num,
        )
        account.account_number = real_num
        session.flush()

    async def sync_account_comprehensive(self, account_number: str, session: Session) -> Dict:
        account: BrokerAccount | None = (
            session.query(BrokerAccount)
            .filter(BrokerAccount.account_number == str(account_number))
            .first()
        )
        if not account:
            raise ValueError(f"Schwab account {account_number} not found")

        await self._connect(account, session)
        await self._resolve_or_discover(account, session)

        results: Dict[str, Any] = {"status": "success"}

        pos_result = await self._sync_positions(account, session)
        results.update(pos_result)

        opt_result = await self._sync_options(account, session)
        results.update(opt_result)

        txn_result = await self._sync_transactions(account, session)
        results.update(txn_result)

        bal_result = await self._sync_balances(account, session)
        results.update(bal_result)

        price_result = await self._refresh_prices(account, session)
        results.update(price_result)

        session.flush()

        self._enrich_positions_from_snapshots(account, session)

        # Reconcile synthetic CLOSED_LOT trades from FILLED executions so the
        # Tax Center and /stocks/realized return correct data. Schwab's API
        # does not emit closed-lot records (unlike IBKR FlexQuery), so we
        # derive them ourselves. Idempotent, safe to run every sync.
        # Run inside a SAVEPOINT: if the matcher blows up mid-flush (IntegrityError,
        # constraint drift), ``begin_nested()`` rolls back just the savepoint so
        # the outer transaction stays clean and the positions/options/transactions
        # already written earlier in the sync still commit downstream.
        # Pytest ``db_session`` already uses a savepoint; an extra ``begin_nested``
        # can raise ``InvalidRequestError`` (often on context exit). If
        # ``reconcile_closing_lots`` already returned, a second run would only
        # hit idempotent update paths and skew counters — only fall back when
        # the matcher has not run yet.
        try:
            match_result: MatchResult | None = None
            try:
                with session.begin_nested():
                    match_result = reconcile_closing_lots(session, account)
            except InvalidRequestError as nested_exc:
                err = str(nested_exc).lower()
                if "closed transaction" in err and "context manager" in err:
                    if match_result is None:
                        match_result = reconcile_closing_lots(session, account)
                else:
                    raise
            assert match_result is not None
            results["closed_lots_created"] = match_result.created
            results["closed_lots_updated"] = match_result.updated
            results["option_tax_lots_created"] = match_result.option_lots_created
            results["option_tax_lots_updated"] = match_result.option_lots_updated
            if match_result.unmatched_quantity > 0:
                logger.warning(
                    "Schwab sync: account %s had %s unmatched sell-shares "
                    "during closing-lot reconciliation (first warning: %s)",
                    account.id,
                    match_result.unmatched_quantity,
                    match_result.warnings[0] if match_result.warnings else "n/a",
                )
        except Exception as exc:  # noqa: BLE001
            _record_reconcile_closing_lots_anomaly()
            logger.warning(
                "reconcile_closing_lots failed for user=%s account=%s: %s",
                account.user_id,
                account.account_number,
                exc,
            )
            results["closed_lots_error"] = str(exc)
            if str(settings.ENVIRONMENT or "").lower() == "development":
                raise

        total_items = sum(v for v in results.values() if isinstance(v, int))
        if total_items == 0 and self._client.connected:
            logger.warning(
                "Schwab sync: completed for account %s (%s) but returned 0 items "
                "across all categories. Possible API issue or empty account.",
                account.id, account.account_number,
            )
        else:
            logger.info(
                "Schwab sync: account %s (%s) synced %d total items: %s",
                account.id, account.account_number, total_items, results,
            )

        return results

    async def _refresh_prices(self, account: BrokerAccount, session: Session) -> Dict:
        """Fetch current prices concurrently and update position market data."""
        # medallion: allow silver for market-data/Redis lookaside in sync I/O path
        from app.services.silver.market.market_data_service import quote

        positions = (
            session.query(Position)
            .filter(
                Position.account_id == account.id,
                Position.status == PositionStatus.OPEN,
                Position.quantity != 0,
            )
            .all()
        )
        symbols = sorted({p.symbol for p in positions if p.symbol})
        if not symbols:
            return {"prices_refreshed": 0}

        results = await asyncio.gather(
            *(quote.get_current_price(sym) for sym in symbols),
            return_exceptions=True,
        )
        price_map = {}
        for sym, res in zip(symbols, results):
            if isinstance(res, (int, float)) and res > 0:
                price_map[sym] = float(res)

        updated = 0
        touched: list[Position] = []
        for p in positions:
            price = price_map.get(p.symbol)
            if price:
                p.update_market_data(price)
                updated += 1
                touched.append(p)
        session.flush()
        logger.info("Schwab sync: refreshed prices for %d/%d positions", updated, len(positions))
        day_pnl_stats = recompute_day_pnl_for_rows(session, touched, "schwab_refresh_prices")
        return {"prices_refreshed": updated, **day_pnl_stats}

    @staticmethod
    def _enrich_positions_from_snapshots(account: BrokerAccount, session: Session) -> None:
        """Backfill sector/market_cap from MarketSnapshot for any open positions with NULLs."""
        from app.models.market_data import MarketSnapshot

        positions = (
            session.query(Position)
            .filter(
                Position.account_id == account.id,
                Position.status == PositionStatus.OPEN,
                (Position.sector.is_(None)) | (Position.market_cap.is_(None)),
            )
            .all()
        )
        if not positions:
            return
        symbols = list({p.symbol.upper() for p in positions if p.symbol})
        snaps = (
            session.query(MarketSnapshot)
            .filter(MarketSnapshot.analysis_type == "technical_snapshot", MarketSnapshot.symbol.in_(symbols))
            .all()
        )
        snap_map = {}
        for s in snaps:
            sym = (s.symbol or "").upper()
            if sym and sym not in snap_map:
                snap_map[sym] = s
        enriched = 0
        for p in positions:
            snap = snap_map.get((p.symbol or "").upper())
            if not snap:
                continue
            if p.sector is None and getattr(snap, "sector", None):
                p.sector = snap.sector
                enriched += 1
            if p.market_cap is None and getattr(snap, "market_cap", None):
                p.market_cap = snap.market_cap
        if enriched:
            logger.info("Schwab sync: enriched %d positions with sector/market_cap from MarketSnapshot", enriched)

    async def _sync_positions(self, account: BrokerAccount, session: Session) -> Dict:
        positions = await self._client.get_positions(account_number=account.account_number)
        created = 0
        updated = 0
        touched_rows: list[Position] = []
        for p in positions:
            sym = (p.get("symbol") or "").upper()
            if not sym:
                continue
            qty = Decimal(str(p.get("quantity", 0)))
            avg_cost = Decimal(str(p.get("average_cost"))) if p.get("average_cost") is not None else None
            total_cost = Decimal(str(p.get("total_cost_basis"))) if p.get("total_cost_basis") is not None else None
            mkt_val = Decimal(str(p["market_value"])) if p.get("market_value") is not None else None
            day_pnl = Decimal(str(p["day_pnl"])) if p.get("day_pnl") is not None else None
            day_pnl_pct = Decimal(str(p["day_pnl_pct"])) if p.get("day_pnl_pct") is not None else None

            fields = {
                "quantity": qty,
                "average_cost": avg_cost,
                "total_cost_basis": total_cost,
                "instrument_type": "STOCK",
                "position_type": PositionType.LONG if qty >= 0 else PositionType.SHORT,
                "status": PositionStatus.OPEN if qty != 0 else PositionStatus.CLOSED,
            }
            if mkt_val is not None:
                fields["market_value"] = mkt_val
                if qty != 0:
                    fields["current_price"] = mkt_val / abs(qty)
            # Broker day_pnl / day_pnl_pct are advisory only (D141). We log
            # at debug level so drift vs server recompute is observable, but
            # we do NOT persist the broker value: it silently corrupts across
            # splits and cross-session refreshes (RIVN -$55,691 regression).
            if day_pnl is not None:
                logger.debug(
                    "schwab day_pnl advisory: symbol=%s broker_day_pnl=%s broker_day_pnl_pct=%s",
                    sym,
                    day_pnl,
                    day_pnl_pct,
                )
            if avg_cost and total_cost is None and qty != 0:
                fields["total_cost_basis"] = avg_cost * abs(qty)
            elif total_cost and avg_cost is None and qty != 0:
                fields["average_cost"] = total_cost / abs(qty)

            existing: Position | None = (
                session.query(Position)
                .filter(Position.account_id == account.id, Position.symbol == sym)
                .first()
            )
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                updated += 1
                touched_rows.append(existing)
            else:
                new_pos = Position(
                    user_id=account.user_id,
                    account_id=account.id,
                    symbol=sym,
                    currency=account.currency or "USD",
                    **fields,
                )
                session.add(new_pos)
                created += 1
                touched_rows.append(new_pos)
        session.flush()

        # Server-side day P&L recompute (D141).
        day_pnl_stats = recompute_day_pnl_for_rows(session, touched_rows, "schwab")
        return {
            "positions_created": created,
            "positions_updated": updated,
            **day_pnl_stats,
        }

    async def _sync_options(self, account: BrokerAccount, session: Session) -> Dict:
        """Sync option positions from Schwab API."""
        raw = await self._client.get_options_positions(account_number=account.account_number)
        created = 0
        updated = 0
        dropped_no_underlying = 0
        dropped_no_expiry = 0
        dropped_parse_error = 0

        def _row_preview(option_row: Dict[str, Any]) -> Dict[str, Any]:
            return {k: option_row.get(k) for k in ("symbol", "option_symbol", "expiration", "strike", "quantity")}

        for o in raw:
            underlying = (o.get("symbol") or "").upper()
            strike = float(o.get("strike", 0))
            put_call = (o.get("put_call") or "CALL").upper()
            expiry_str = o.get("expiration") or ""
            qty = int(o.get("quantity", 0))
            if not underlying:
                dropped_no_underlying += 1
                logger.warning(
                    "Schwab sync: dropping option row for account %s: reason=%s keys=%s raw=%s",
                    account.id,
                    "no_underlying",
                    list(o.keys()),
                    _row_preview(o),
                )
                continue
            if not expiry_str:
                dropped_no_expiry += 1
                logger.warning(
                    "Schwab sync: dropping option row for account %s: reason=%s keys=%s raw=%s",
                    account.id,
                    "no_expiry",
                    list(o.keys()),
                    _row_preview(o),
                )
                continue

            expiry_date = _parse_schwab_expiry_to_date(expiry_str)
            if not expiry_date:
                dropped_parse_error += 1
                logger.warning(
                    "Schwab sync: dropping option row for account %s: reason=%s keys=%s raw=%s",
                    account.id,
                    "expiry_parse_error",
                    list(o.keys()),
                    _row_preview(o),
                )
                continue

            existing = (
                session.query(Option)
                .filter(
                    Option.account_id == account.id,
                    Option.underlying_symbol == underlying,
                    Option.strike_price == strike,
                    Option.expiry_date == expiry_date,
                    Option.option_type == put_call,
                )
                .first()
            )
            if existing:
                existing.open_quantity = qty
                existing.current_price = Decimal(str(o.get("market_value", 0))) / max(abs(qty) * 100, 1) if qty else None
                existing.total_cost = Decimal(str(o.get("average_cost", 0) * abs(qty) * 100)) if o.get("average_cost") else None
                updated += 1
            else:
                session.add(Option(
                    user_id=account.user_id,
                    account_id=account.id,
                    symbol=o.get("option_symbol") or f"{underlying}{expiry_date:%y%m%d}{put_call[0]}{strike:.0f}",
                    underlying_symbol=underlying,
                    strike_price=strike,
                    expiry_date=expiry_date,
                    option_type=put_call,
                    multiplier=100,
                    open_quantity=qty,
                    currency=account.currency or "USD",
                    data_source="SCHWAB_API",
                ))
                created += 1

        if (created + updated) > 0 and not account.options_enabled:
            account.options_enabled = True

        session.flush()
        dropped_total = dropped_no_underlying + dropped_no_expiry + dropped_parse_error
        out: Dict[str, Any] = {
            "options_created": created,
            "options_updated": updated,
            "options_dropped_no_underlying": dropped_no_underlying,
            "options_dropped_no_expiry": dropped_no_expiry,
            "options_dropped_parse_error": dropped_parse_error,
        }
        if len(raw) > 0 and created == 0 and updated == 0:
            logger.error(
                "Schwab sync: account %s had %d options from API but wrote 0 to DB. Dropped=%d. "
                "This is a silent-fallback violation.",
                account.id,
                len(raw),
                dropped_total,
            )
            out["options_silent_drop"] = True
        return out

    async def _sync_transactions(self, account: BrokerAccount, session: Session) -> Dict:
        """Sync transactions from Schwab API and split into transactions, trades, and dividends."""
        raw_txns = await self._client.get_transactions(account_number=account.account_number)
        txn_count = 0
        trade_count = 0
        dividend_count = 0
        transfer_cost_map: Dict[str, float] = {}

        for t in raw_txns:
            ext_id = str(t.get("id") or "").strip()
            if not ext_id:
                continue

            action = (t.get("action") or "").upper()
            sym = (t.get("symbol") or "").upper()
            qty = float(t.get("quantity", 0) or 0)
            price = float(t.get("price", 0) or 0)
            commission = float(t.get("commission", 0) or 0)
            amount = float(t.get("amount", 0) or qty * price)
            net_amount = amount - commission
            txn_type = SCHWAB_TYPE_MAP.get(action, TransactionType.OTHER)
            txn_date_str = t.get("date") or t.get("transactionDate")
            txn_date = _parse_date(txn_date_str) if txn_date_str else datetime.now(timezone.utc)
            sub_account = t.get("sub_account", "")

            desc_parts = [t.get("description") or ""]
            if sub_account:
                desc_parts.append(f"[{sub_account}]")
            description = " ".join(p for p in desc_parts if p).strip()

            # For ACATS transfers, capture cost basis from transferItems
            transfer_cost = t.get("transfer_cost_basis")
            if action == "RECEIVE_AND_DELIVER" and sym and transfer_cost and transfer_cost > 0:
                transfer_cost_map[sym] = transfer_cost

            existing_txn = (
                session.query(Transaction)
                .filter(Transaction.account_id == account.id, Transaction.external_id == ext_id)
                .first()
            )
            if not existing_txn:
                new_txn = Transaction(
                    account_id=account.id,
                    external_id=ext_id,
                    symbol=sym or "CASH",
                    transaction_type=txn_type,
                    action=action[:10] if action else None,
                    quantity=qty,
                    trade_price=price,
                    amount=amount,
                    net_amount=net_amount,
                    commission=commission,
                    currency=account.currency or "USD",
                    transaction_date=txn_date,
                    description=description or None,
                    source="SCHWAB",
                )
                session.add(new_txn)
                txn_count += 1

            if action in _TRADE_TYPES and sym:
                side = "BUY" if qty > 0 else "SELL"
                is_opening, opt_meta = _schwab_filled_is_opening_and_metadata(
                    {**t, "symbol": sym},
                    side,
                )
                existing_trade = (
                    session.query(Trade)
                    .filter(Trade.account_id == account.id, Trade.execution_id == ext_id)
                    .first()
                )
                if not existing_trade:
                    session.add(Trade(
                        account_id=account.id,
                        symbol=sym,
                        side=side,
                        quantity=abs(qty),
                        price=price,
                        total_value=abs(qty * price),
                        commission=commission,
                        execution_id=ext_id,
                        execution_time=txn_date,
                        status="FILLED",
                        is_opening=is_opening,
                        is_paper_trade=False,
                        trade_metadata=opt_meta,
                    ))
                    trade_count += 1
                else:
                    pe = (t.get("position_effect") or "").upper()
                    if pe in ("OPENING", "CLOSING") and existing_trade.is_opening != is_opening:
                        existing_trade.is_opening = is_opening
                    if opt_meta:
                        merged = {**(existing_trade.trade_metadata or {}), **opt_meta}
                        if merged != (existing_trade.trade_metadata or {}):
                            existing_trade.trade_metadata = merged
                            flag_modified(existing_trade, "trade_metadata")

            if txn_type == TransactionType.DIVIDEND and sym:
                existing_div = (
                    session.query(Dividend)
                    .filter(Dividend.account_id == account.id, Dividend.external_id == ext_id)
                    .first()
                )
                if not existing_div:
                    session.add(Dividend(
                        account_id=account.id,
                        external_id=ext_id,
                        symbol=sym,
                        ex_date=txn_date,
                        pay_date=txn_date,
                        dividend_per_share=0,
                        shares_held=0,
                        total_dividend=abs(amount),
                        tax_withheld=0,
                        net_dividend=abs(amount),
                        currency=account.currency or "USD",
                        source="schwab",
                    ))
                    dividend_count += 1

        session.flush()

        # Reconcile cost basis for positions missing it, using ACATS transfer cost or local trades
        positions_missing_cost = (
            session.query(Position)
            .filter(
                Position.account_id == account.id,
                Position.status == PositionStatus.OPEN,
                Position.quantity != 0,
                (Position.average_cost == None) | (Position.average_cost == 0),  # noqa: E711
            )
            .all()
        )
        reconciled = 0
        for pos in positions_missing_cost:
            cost = transfer_cost_map.get(pos.symbol)
            if cost and cost > 0 and pos.quantity and pos.quantity != 0:
                pos.total_cost_basis = Decimal(str(cost))
                pos.average_cost = Decimal(str(cost)) / abs(pos.quantity)
                reconciled += 1
                continue
            # Fallback: compute from local BUY/TRANSFER transactions
            buy_txns = (
                session.query(Transaction)
                .filter(
                    Transaction.account_id == account.id,
                    Transaction.symbol == pos.symbol,
                    Transaction.transaction_type.in_([TransactionType.BUY, TransactionType.TRANSFER]),
                    Transaction.trade_price > 0,
                    Transaction.quantity > 0,
                )
                .all()
            )
            if buy_txns:
                total_qty = sum(float(tx.quantity or 0) for tx in buy_txns)
                total_cost = sum(float(tx.quantity or 0) * float(tx.trade_price or 0) for tx in buy_txns)
                if total_qty > 0:
                    pos.average_cost = Decimal(str(total_cost / total_qty))
                    pos.total_cost_basis = pos.average_cost * abs(pos.quantity)
                    reconciled += 1
        if reconciled:
            session.flush()
            logger.info("Schwab sync: reconciled cost basis for %d positions", reconciled)

        return {
            "transactions_synced": txn_count,
            "trades_synced": trade_count,
            "dividends_synced": dividend_count,
        }

    async def _sync_balances(self, account: BrokerAccount, session: Session) -> Dict:
        """Sync account balances from Schwab API."""
        bal = await self._client.get_account_balances(account_number=account.account_number)
        if not bal:
            return {"balances_synced": 0}

        nlv = bal.get("net_liquidating_value")
        cash = bal.get("cash_balance")
        if nlv is not None:
            account.total_value = Decimal(str(nlv))
        if cash is not None:
            account.cash_balance = Decimal(str(cash))

        new_bal = AccountBalance(
            user_id=account.user_id,
            broker_account_id=account.id,
            balance_date=datetime.now(timezone.utc),
            cash_balance=cash,
            net_liquidation=nlv,
            buying_power=bal.get("equity_buying_power"),
            available_funds=bal.get("available_funds"),
            equity=bal.get("equity"),
            initial_margin_req=bal.get("long_margin_value"),
            maintenance_margin_req=bal.get("maintenance_requirement"),
            sma=bal.get("sma"),
            data_source="SCHWAB_API",
        )
        session.add(new_bal)
        session.flush()
        return {"balances_synced": 1}


def _parse_schwab_expiry_to_date(val: str) -> Optional[date]:
    """Parse Schwab / OCC expiry strings without defaulting to 'now' on failure."""
    if not val or not str(val).strip():
        return None
    s = str(val).strip()
    if isinstance(s, str) and "T" in s:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            pass
    try:
        return datetime.fromisoformat(s[:10]).date()
    except (ValueError, TypeError):
        pass
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


def _parse_date(val: Any) -> datetime:
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)
