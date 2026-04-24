#!/usr/bin/env python3
"""TastyTrade Sync Service
Pulls positions, transactions, balances, dividends from Tastytrade API and
persists to AxiomFolio broker-agnostic tables.

medallion: bronze
"""

from __future__ import annotations

import logging
from datetime import datetime as dt
from decimal import Decimal
import re
from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session
from backend.services.clients.tastytrade_client import TastyTradeClient
from backend.models import (
    BrokerAccount,
    Position,
    Option,
    Trade,
    Transaction,
    Dividend,
    AccountBalance,
    TaxLot,
)
from backend.models.tax_lot import TaxLotSource
# medallion: allow cross-layer import (bronze -> silver); resolves when backend.services.portfolio.account_credentials_service moves during Phase 0.C
from backend.services.portfolio.account_credentials_service import (
    account_credentials_service,
    CredentialsNotFoundError,
)
# medallion: allow cross-layer import (bronze -> silver); resolves when backend.services.portfolio.closing_lot_matcher moves during Phase 0.C
from backend.services.portfolio.closing_lot_matcher import reconcile_closing_lots
# medallion: allow cross-layer import (bronze -> silver); resolves when backend.services.portfolio.day_pnl_service moves during Phase 0.C
from backend.services.portfolio.day_pnl_service import recompute_day_pnl_for_rows
from backend.models.position import PositionType
from backend.models.transaction import TransactionType
from backend.models.account_balance import AccountBalanceType

logger = logging.getLogger(__name__)

# Broker-neutral keys for option-row drop logs (TastyTrade vs Schwab naming).
_OPTION_ROW_DROP_PREVIEW_KEYS = (
    "symbol",
    "option_symbol",
    "underlying_symbol",
    "expiration",
    "expiration_date",
    "strike",
    "strike_price",
    "put_call",
    "option_type",
    "quantity",
)


class TastyTradeSyncService:
    """High-level orchestrator for Tastytrade data → DB."""

    def __init__(self):
        self.client = TastyTradeClient()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    async def sync_account(
        self, db: Session, broker_account: BrokerAccount
    ) -> Dict[str, Any]:
        """Sync ALL objects for the given broker account. Returns row counts."""
        counts: Dict[str, Any] = {}

        # Per-user credentials: use AccountCredentialsService for decryption
        try:
            payload = account_credentials_service.get_decrypted(broker_account.id, db)
            ok = await self.client.connect_with_credentials(
                client_secret=payload["client_secret"],
                refresh_token=payload["refresh_token"],
            )
            if not ok:
                raise ConnectionError(
                    f"TastyTrade OAuth failed for account {broker_account.account_number}"
                )
        except CredentialsNotFoundError:
            # Dev fallback: env var credentials for seed accounts without stored creds
            await self.client.connect_with_retry()
        except Exception as exc:
            err_str = str(exc).lower()
            if "encrypt" in err_str or "token" in err_str or "fernet" in err_str:
                logger.error(
                    "Encryption/token error for TastyTrade account %s: %s — "
                    "credentials need to be re-entered.",
                    broker_account.account_number, exc,
                )
                raise ConnectionError(
                    f"Invalid encryption token — please re-enter your TastyTrade credentials "
                    f"on the Connections page. (Original error: {exc})"
                ) from exc
            raise

        # Ensure the requested account number exists in the connected TT session
        try:
            if getattr(self.client, "accounts", None):
                tt_numbers = [
                    getattr(a, "account_number", None) for a in self.client.accounts
                ]
                if broker_account.account_number not in tt_numbers and tt_numbers:
                    logger.warning(
                        "Account %s not found in TastyTrade session; updating to %s",
                        broker_account.account_number,
                        tt_numbers[0],
                    )
                    broker_account.account_number = tt_numbers[0]
                    db.add(broker_account)
                    db.commit()
        except Exception as exc:
            logger.warning("Failed to update account metadata: %s", exc)

        counts.update(await self._sync_positions(db, broker_account))
        counts.update(await self._sync_tax_lots(db, broker_account))
        counts.update(await self._sync_trades(db, broker_account))
        counts.update(await self._sync_transactions(db, broker_account))
        counts.update(await self._sync_dividends(db, broker_account))
        counts.update(await self._sync_account_balances(db, broker_account))

        # Reconcile synthetic CLOSED_LOT trades so Tax Center / realized-gains
        # endpoints reflect TastyTrade activity (TT only emits FILLED rows).
        # Use a SAVEPOINT so a matcher failure (IntegrityError, flush drift)
        # can be rolled back in isolation without poisoning the session for
        # the final ``db.commit()`` below — without this, a PendingRollback
        # would take the entire sync down even though positions/options/
        # transactions already persisted fine.
        try:
            with db.begin_nested():
                match_result = reconcile_closing_lots(db, broker_account)
            counts["closed_lots_created"] = match_result.created
            counts["closed_lots_updated"] = match_result.updated
            if match_result.unmatched_quantity > 0:
                logger.warning(
                    "TastyTrade sync: account %s had %s unmatched sell-shares "
                    "during closing-lot reconciliation",
                    broker_account.id, match_result.unmatched_quantity,
                )
        except Exception as exc:  # noqa: BLE001
            # begin_nested() auto-rolls back the SAVEPOINT on exception,
            # so the outer transaction stays clean.
            logger.warning(
                "TastyTrade sync: closing-lot reconciliation failed for account %s: %s",
                broker_account.id, exc,
            )
            counts["closed_lots_error"] = str(exc)

        db.commit()

        try:
            # medallion: allow cross-layer import (bronze -> silver); resolves when backend.services.portfolio.activity_aggregator moves during Phase 0.C
            from backend.services.portfolio.activity_aggregator import activity_aggregator
            activity_aggregator.refresh_materialized_views(db)
        except Exception as e:
            logger.warning("Activity MV refresh skipped: %s", e)

        logger.info("TastyTrade sync complete → %s", counts)
        return counts

    async def sync_account_comprehensive(
        self, account_number: str, db_session=None
    ) -> Dict[str, Any]:
        """Adapter to align with broker-agnostic sync interface used by BrokerSyncService."""
        db = db_session or self._get_db_session()
        try:
            # Resolve BrokerAccount by account_number
            ba = (
                db.query(BrokerAccount)
                .filter(BrokerAccount.account_number == account_number)
                .first()
            )
            if not ba:
                return {"status": "error", "error": "Broker account not found"}
            return await self.sync_account(db, ba)
        finally:
            if db_session is None:
                try:
                    db.close()
                except Exception:
                    pass

    def _get_db_session(self) -> Session:
        # Lazy import to avoid circulars
        from backend.database import SessionLocal

        return SessionLocal()

    # ------------------------------------------------------------------
    # Internal helpers (1 per table)
    # ------------------------------------------------------------------

    async def _sync_positions(self, db: Session, ba: BrokerAccount) -> Dict[str, Any]:
        data = await self.client.get_current_positions(ba.account_number)
        db.query(Position).filter_by(account_id=ba.id).delete()
        db.query(Option).filter_by(account_id=ba.id).delete()

        count = 0
        options_added = 0
        raw_option_rows = 0
        dropped_no_underlying = 0
        dropped_no_expiry = 0
        dropped_parse_error = 0
        seen_option_keys = set()
        touched_rows: list[Position] = []
        for pos in data:
            try:
                qty = float(pos.get("quantity", 0) or 0)
                if qty == 0:
                    continue

                instr_type = (pos.get("instrument_type") or "").lower()
                if "option" in instr_type:
                    raw_option_rows += 1
                    kwargs, drop_reason = self._option_position_kwargs(pos, ba)
                    if kwargs:
                        # dedupe by (account_id, underlying, strike, expiry, type)
                        key = (
                            ba.id,
                            kwargs.get("underlying_symbol"),
                            float(kwargs.get("strike_price")),
                            kwargs.get("expiry_date"),
                            kwargs.get("option_type"),
                        )
                        if key in seen_option_keys:
                            continue
                        seen_option_keys.add(key)
                        db.add(Option(**kwargs))
                        count += 1
                        options_added += 1
                    else:
                        if drop_reason == "no_underlying":
                            dropped_no_underlying += 1
                        elif drop_reason == "no_expiry":
                            dropped_no_expiry += 1
                        elif drop_reason == "zero_qty":
                            continue
                        else:
                            dropped_parse_error += 1
                        logger.warning(
                            "TastyTrade sync: dropping option row for account %s: reason=%s keys=%s raw=%s",
                            ba.id,
                            drop_reason,
                            list(pos.keys()),
                            {k: pos.get(k) for k in _OPTION_ROW_DROP_PREVIEW_KEYS},
                        )
                else:
                    kwargs = self._equity_position_kwargs(pos, ba)
                    if kwargs:
                        new_pos = Position(**kwargs)
                        db.add(new_pos)
                        touched_rows.append(new_pos)
                        count += 1
            except Exception as exc:
                logger.warning("Skipping TastyTrade position %s: %s", pos.get("symbol", "?"), exc)
                continue

        if options_added > 0 and not ba.options_enabled:
            ba.options_enabled = True

        db.flush()
        # Server-side day P&L recompute (D141) — TastyTrade's
        # ``get_current_positions`` does not surface day P&L; this is the
        # canonical place for it to land.
        day_pnl_stats = recompute_day_pnl_for_rows(db, touched_rows, "tastytrade")
        out: Dict[str, Any] = {
            "positions": count,
            "options_dropped_no_underlying": dropped_no_underlying,
            "options_dropped_no_expiry": dropped_no_expiry,
            "options_dropped_parse_error": dropped_parse_error,
            **day_pnl_stats,
        }
        dropped_total = dropped_no_underlying + dropped_no_expiry + dropped_parse_error
        if raw_option_rows > 0 and options_added == 0:
            logger.error(
                "TastyTrade sync: account %s had %d option rows from API but wrote 0 to DB. Dropped=%d. "
                "This is a silent-fallback violation.",
                ba.id,
                raw_option_rows,
                dropped_total,
            )
            out["options_silent_drop"] = True
        return out

    async def _sync_tax_lots(self, db: Session, ba: BrokerAccount) -> Dict[str, int]:
        """Generate tax lots from synced positions (one lot per position).

        TastyTrade's API doesn't expose per-lot data, so we approximate each
        position as a single lot using the average cost already on the Position
        row.  This keeps Tax Center / Workspace functional.
        """
        positions = db.query(Position).filter_by(account_id=ba.id).all()
        if not positions:
            return {"tax_lots": 0}

        db.query(TaxLot).filter_by(account_id=ba.id).delete()
        count = 0
        for pos in positions:
            try:
                qty = float(pos.quantity or 0)
                if qty == 0:
                    continue
                avg = float(pos.average_cost or 0)
                cost_basis = float(pos.total_cost_basis or 0) or (qty * avg)
                mkt_val = float(pos.market_value or 0)
                pnl = float(pos.unrealized_pnl or 0)
                pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0

                db.add(TaxLot(
                    user_id=ba.user_id,
                    account_id=ba.id,
                    lot_id=f"TT_{pos.symbol}_{count}",
                    symbol=pos.symbol,
                    quantity=qty,
                    cost_per_share=avg,
                    cost_basis=cost_basis,
                    current_price=float(pos.current_price or 0),
                    market_value=mkt_val,
                    unrealized_pnl=pnl,
                    unrealized_pnl_pct=pnl_pct,
                    currency="USD",
                    asset_category="STK",
                    source=TaxLotSource.CALCULATED,
                ))
                count += 1
            except Exception as exc:
                logger.warning("Skipping TastyTrade tax lot for %s: %s", pos.symbol, exc)
                continue

        db.flush()
        logger.info("Synced %d tax lots from TastyTrade positions for %s", count, ba.account_number)
        return {"tax_lots": count}

    async def _sync_trades(self, db: Session, ba: BrokerAccount) -> Dict[str, int]:
        """Idempotent trade sync from TastyTrade.

        Iron Law #1 (append-only ledger): never DELETE trades. Existing rows
        are preserved; rows that collide on the (account_id, execution_id)
        natural key are silently skipped via Postgres ON CONFLICT DO NOTHING.

        Iron Law #2 (idempotent bronze): re-running this sync produces the
        same persisted state — rowcounts may grow (new trades from the broker)
        but never shrink.

        Iron Law #5 (counter-based auditing): written/skipped/errors are
        reported per-call and their sum is asserted == input.
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        trades = await self.client.get_trade_history(ba.account_number, days=365)
        written = 0
        skipped = 0
        errors = 0
        seen_execs: set[str] = set()
        for t in trades:
            try:
                kwargs = self._trade_to_kwargs(t, ba)
            except Exception as exc:
                logger.warning("Skipping TastyTrade trade (build kwargs): %s", exc)
                errors += 1
                continue
            exec_id = kwargs.get("execution_id") or kwargs.get("order_id")
            if exec_id and exec_id in seen_execs:
                skipped += 1
                continue
            if exec_id:
                seen_execs.add(exec_id)
            stmt = pg_insert(Trade.__table__).values(**kwargs).on_conflict_do_nothing()
            result = db.execute(stmt)
            if result.rowcount == 1:
                written += 1
            else:
                skipped += 1
        db.flush()
        total = len(trades)
        if written + skipped + errors != total:
            logger.error(
                "TastyTrade trades sync counter mismatch account=%s "
                "written=%d skipped=%d errors=%d total=%d — Iron Law #5 violation",
                ba.account_number, written, skipped, errors, total,
            )
        logger.info(
            "TastyTrade trades sync account=%s written=%d skipped=%d errors=%d total=%d",
            ba.account_number, written, skipped, errors, total,
        )
        return {
            "trades": total,
            "written": written,
            "skipped": skipped,
            "errors": errors,
        }

    async def _sync_transactions(
        self, db: Session, ba: BrokerAccount
    ) -> Dict[str, int]:
        """Idempotent transaction sync from TastyTrade.

        Iron Law #1: never DELETE transactions (append-only ledger).
        Iron Law #2: re-run safely — any row colliding on either unique
            constraint (account_id + external_id OR account_id + execution_id)
            is skipped by ON CONFLICT DO NOTHING.
        Iron Law #5: counters reported, sum asserted.
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        txns = await self.client.get_transactions(ba.account_number, days=365)
        written = 0
        skipped = 0
        errors = 0
        seen_txn_ids: set[str] = set()
        for txn in txns:
            try:
                kwargs = self._txn_to_kwargs(txn, ba)
            except Exception as exc:
                logger.warning("Skipping TastyTrade transaction (build kwargs): %s", exc)
                errors += 1
                continue
            ext_id = (
                kwargs.get("external_id")
                or kwargs.get("execution_id")
                or kwargs.get("order_id")
            )
            if ext_id and ext_id in seen_txn_ids:
                skipped += 1
                continue
            if ext_id:
                seen_txn_ids.add(ext_id)
            stmt = pg_insert(Transaction.__table__).values(**kwargs).on_conflict_do_nothing()
            result = db.execute(stmt)
            if result.rowcount == 1:
                written += 1
            else:
                skipped += 1
        db.flush()
        total = len(txns)
        if written + skipped + errors != total:
            logger.error(
                "TastyTrade txns sync counter mismatch account=%s "
                "written=%d skipped=%d errors=%d total=%d — Iron Law #5 violation",
                ba.account_number, written, skipped, errors, total,
            )
        logger.info(
            "TastyTrade txns sync account=%s written=%d skipped=%d errors=%d total=%d",
            ba.account_number, written, skipped, errors, total,
        )
        return {
            "transactions": written,
            "written": written,
            "skipped": skipped,
            "errors": errors,
        }

    async def _sync_dividends(self, db: Session, ba: BrokerAccount) -> Dict[str, int]:
        divs = await self.client.get_dividends(ba.account_number, days=365)
        count = 0
        for d in divs:
            try:
                kwargs = self._div_to_kwargs(d, ba)
                ext_id = kwargs.get("external_id")
                if ext_id:
                    existing = db.query(Dividend).filter_by(
                        account_id=ba.id, external_id=ext_id
                    ).first()
                    if existing:
                        continue
                db.add(Dividend(**kwargs))
                count += 1
            except Exception as e:
                logger.debug("Dividend sync skip: %s", e)
                continue
        db.flush()
        return {"dividends": count}

    async def _sync_account_balances(
        self, db: Session, ba: BrokerAccount
    ) -> Dict[str, int]:
        bal = await self.client.get_account_balances(ba.account_number)
        if not bal:
            return {"account_balances": 0}
        nlv = bal.get("net_liquidating_value")
        cash = bal.get("cash_balance")
        if nlv is not None:
            ba.total_value = Decimal(str(nlv))
        if cash is not None:
            ba.cash_balance = Decimal(str(cash))
        db.query(AccountBalance).filter_by(broker_account_id=ba.id).delete()
        # Map fields to our model
        mapped = dict(
            user_id=ba.user_id,
            broker_account_id=ba.id,
            balance_type=AccountBalanceType.REALTIME,
            cash_balance=cash,
            net_liquidation=nlv,
            gross_position_value=(bal.get("long_margin_value", 0) or 0)
            + (bal.get("short_margin_value", 0) or 0),
            buying_power=nlv,
            data_source="TASTYTRADE",
        )
        db.add(AccountBalance(**mapped))
        db.flush()
        return {"account_balances": 1}

    # ------------------------------------------------------------------
    # Converters
    # ------------------------------------------------------------------

    def _equity_position_kwargs(self, p: Dict, ba: BrokerAccount) -> Dict:
        quantity = float(p.get("quantity", 0) or 0)
        avg_cost = p.get("average_open_price") or 0
        total_cost_basis = abs(quantity) * float(avg_cost)
        current_price = p.get("mark")
        market_value = p.get("mark_value") or (
            abs(quantity) * float(current_price or 0)
        )
        unrealized = None
        try:
            unrealized = float(market_value) - float(total_cost_basis)
        except Exception:
            pass
        position_type = PositionType.LONG if quantity >= 0 else PositionType.SHORT
        return dict(
            user_id=ba.user_id,
            account_id=ba.id,
            symbol=p.get("symbol"),
            quantity=abs(quantity),
            average_cost=avg_cost,
            total_cost_basis=total_cost_basis,
            market_value=market_value,
            instrument_type="STOCK",
            position_type=position_type,
            current_price=current_price,
            unrealized_pnl=unrealized,
        )

    def _trade_to_kwargs(self, t: Dict, ba: BrokerAccount) -> Dict:
        """Map a TastyTrade trade payload to ``Trade`` column kwargs.

        Fields required by the closing-lot matcher
        (:mod:`backend.services.portfolio.closing_lot_matcher`):

        * ``execution_time`` — the ordering key. Must be tz-aware; without
          it FIFO matching can't run and the Tax Center stays empty
          (observed regression that shipped with PR 394).
        * ``is_opening`` — ``True`` for BUYs, ``False`` for SELLs. The
          default on the model is ``True`` which would mis-classify
          every SELL as an opening trade and the matcher would produce
          zero ``CLOSED_LOT`` rows.
        * ``status`` — defaults to ``"FILLED"`` on the model, but we set
          it explicitly so any future change to the default doesn't
          silently break reconciliation.

        ``created_at`` is populated by ``server_default=now()`` — we no
        longer shoehorn the broker timestamp into it.
        """
        try:
            executed_at = dt.fromisoformat(t["executed_at"])
        except Exception:  # noqa: BLE001 — broker payload oddities
            executed_at = None
        side = (t.get("side") or "").upper()
        is_opening = side == "BUY"
        return dict(
            account_id=ba.id,
            symbol=t["symbol"],
            side=side or t.get("side"),
            quantity=t["quantity"],
            price=t["price"],
            order_id=t.get("order_id"),
            execution_id=t.get("execution_id"),
            execution_time=executed_at,
            is_opening=is_opening,
            status="FILLED",
        )

    def _txn_to_kwargs(self, tx: Dict, ba: BrokerAccount) -> Dict:
        # Compose datetime from separate date/time fields
        dt_str = f"{tx.get('date')}T{tx.get('time')}"
        try:
            txn_dt = dt.fromisoformat(dt_str)
        except Exception:
            txn_dt = dt.utcnow()

        action = (tx.get("action") or "").upper()
        if action == "BUY":
            ttype = TransactionType.BUY
        elif action == "SELL":
            ttype = TransactionType.SELL
        else:
            ttype = TransactionType.OTHER

        return dict(
            account_id=ba.id,
            symbol=tx.get("symbol", "CASH"),
            transaction_type=ttype,
            action=action,
            quantity=tx.get("quantity"),
            trade_price=tx.get("price"),
            amount=tx.get("amount"),
            commission=tx.get("commission"),
            net_amount=tx.get("net_amount"),
            currency=tx.get("currency", "USD"),
            transaction_date=txn_dt,
            external_id=tx.get("id"),
            order_id=tx.get("order_id"),
            execution_id=tx.get("execution_id"),
            source="tastytrade_enhanced",
            asset_category=(
                "OPT" if "option" in (tx.get("contract_type", "").lower()) else "STK"
            ),
        )

    def _div_to_kwargs(self, d: Dict, ba: BrokerAccount) -> Dict:
        ex_date = (
            dt.fromisoformat(d.get("date") + "T" + d.get("time"))
            if d.get("date") and d.get("time")
            else dt.utcnow()
        )
        total = abs(float(d.get("amount", 0) or 0))
        shares = abs(float(d.get("quantity", 0) or 0))
        per_share = (total / shares) if shares > 0 else total
        net_amount = abs(float(d.get("net_amount", 0) or 0)) or total
        tax_withheld = max(0.0, total - net_amount) if net_amount < total else 0.0
        return dict(
            account_id=ba.id,
            external_id=d.get("execution_id") or d.get("id") or None,
            symbol=d.get("symbol", ""),
            ex_date=ex_date,
            pay_date=ex_date,
            total_dividend=total,
            dividend_per_share=per_share,
            shares_held=shares,
            net_dividend=net_amount,
            tax_withheld=tax_withheld,
            currency=d.get("currency", "USD"),
            source="tastytrade",
            dividend_type="ORDINARY",
        )

    def _option_position_kwargs(self, p: Dict, ba: BrokerAccount) -> Tuple[Dict[str, Any], str]:
        """Return (kwargs, drop_reason) — drop_reason empty string on success."""
        quantity = int(abs(float(p.get("quantity", 0) or 0)))
        if quantity == 0:
            return {}, "zero_qty"
        # Try read directly from payload
        symbol = p.get("symbol") or ""
        underlying_symbol = p.get("underlying_symbol")
        strike_price = p.get("strike_price")
        option_type = (p.get("option_type") or "").upper()
        exp = p.get("expiration_date")
        exp_date = None
        if isinstance(exp, str):
            try:
                exp_date = dt.strptime(exp, "%Y-%m-%d").date()
            except Exception:
                exp_date = None
        elif exp and hasattr(exp, "strftime"):
            try:
                exp_date = exp
            except Exception:
                exp_date = None

        # Fallback: parse OCC-like option symbol, e.g. "SOUN  250815C00013000"
        if not (strike_price and exp_date and option_type and underlying_symbol):
            m = re.match(
                r"^([A-Z\.]{1,6})\s+(\d{6})([CP])(\d{8})$", symbol.strip().upper()
            )
            if m:
                underlying_symbol = underlying_symbol or m.group(1)
                yymmdd = m.group(2)
                yy, mm, dd = int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
                exp_date = (
                    exp_date
                    or dt.strptime(f"20{yy:02d}-{mm:02d}-{dd:02d}", "%Y-%m-%d").date()
                )
                option_type = option_type or ("CALL" if m.group(3) == "C" else "PUT")
                # strike encoded with 3 decimals in 8 digits
                strike_enc = m.group(4)
                strike_price = strike_price or (int(strike_enc) / 1000.0)

        # Required fields guard
        if strike_price is None or exp_date is None or not option_type:
            if not underlying_symbol:
                return {}, "no_underlying"
            if exp_date is None:
                return {}, "no_expiry"
            return {}, "parse_error"

        avg_cost = p.get("average_open_price") or 0
        mark_val = p.get("mark_value") or 0
        mult = p.get("multiplier", 100) or 100
        total_cost = abs(float(quantity)) * float(avg_cost) * float(mult)
        unrealized = (
            (float(mark_val) - float(total_cost)) if (mark_val is not None) else None
        )

        return (
            dict(
                user_id=ba.user_id,
                account_id=ba.id,
                symbol=symbol,
                underlying_symbol=underlying_symbol,
                strike_price=float(strike_price),
                expiry_date=exp_date,
                option_type=option_type,
                multiplier=mult,
                open_quantity=quantity,
                current_price=p.get("mark"),
                unrealized_pnl=unrealized,
                delta=p.get("delta"),
                gamma=p.get("gamma"),
                theta=p.get("theta"),
                vega=p.get("vega"),
                currency="USD",
                data_source="TASTYTRADE",
            ),
            "",
        )
