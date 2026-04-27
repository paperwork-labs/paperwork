"""
TastyTrade Client
Production-grade TastyTrade integration using OAuth (SDK v12+).
All SDK methods are async; this client exposes an async-first API.

medallion: ops
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

try:
    import tastytrade as _tt_module
    # SDK v12.0.2 defaults to api.tastyworks.com (legacy domain).
    # TastyTrade's OAuth portal (my.tastytrade.com) issues grants for
    # api.tastytrade.com, so we must override before any Session is created.
    _tt_module.API_URL = "https://api.tastytrade.com"

    from tastytrade import Session, Account
    from tastytrade.account import CurrentPosition, Transaction
    from tastytrade.instruments import Equity, Option
    from tastytrade.order import InstrumentType

    TASTYTRADE_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("tastytrade SDK not available - TastyTrade integration disabled")
    TASTYTRADE_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)


class TastyTradeClient:
    """
    Production-grade TastyTrade client using OAuth authentication (SDK v12+).

    Auth flow:
      1. User creates an OAuth app at my.tastytrade.com
      2. Gets a client_secret and generates a refresh_token (never expires)
      3. Session(provider_secret, refresh_token) handles token refresh automatically
    """

    def __init__(self):
        self.session: Optional[Any] = None
        self.accounts: List[Any] = []
        self.connected = False
        self.connection_start_time: Optional[datetime] = None
        self.retry_count = 0
        self.max_retries = 3
        self.base_retry_delay = 2
        self._lock = asyncio.Lock() if TASTYTRADE_AVAILABLE else None
        self.connection_health: Dict[str, Any] = {
            "status": "disconnected",
            "last_successful_request": None,
            "consecutive_failures": 0,
            "connection_uptime": 0,
        }

    async def connect_with_retry(self, max_attempts: int = 3) -> bool:
        """Connect to TastyTrade using OAuth credentials from settings."""
        if not TASTYTRADE_AVAILABLE:
            return False
        if not self._lock:
            return False

        async with self._lock:
            for attempt in range(max_attempts):
                try:
                    logger.info(
                        "TastyTrade connection attempt %d/%d", attempt + 1, max_attempts
                    )

                    client_secret = getattr(settings, "TASTYTRADE_CLIENT_SECRET", None)
                    refresh_token = getattr(settings, "TASTYTRADE_REFRESH_TOKEN", None)
                    is_test_env = settings.TASTYTRADE_IS_TEST

                    if not client_secret or not refresh_token:
                        logger.error(
                            "TastyTrade OAuth credentials not configured "
                            "(TASTYTRADE_CLIENT_SECRET / TASTYTRADE_REFRESH_TOKEN)"
                        )
                        return False

                    self.session = Session(
                        client_secret, refresh_token, is_test=is_test_env
                    )
                    self.accounts = await Account.get(self.session)

                    if not self.accounts:
                        raise Exception("No TastyTrade accounts found")

                    self.connected = True
                    self.connection_start_time = datetime.now(UTC)
                    self.retry_count = 0
                    self.connection_health.update(
                        {
                            "status": "connected",
                            "last_successful_request": datetime.now(UTC),
                            "consecutive_failures": 0,
                            "connection_uptime": 0,
                        }
                    )

                    await self._verify_connection()

                    env_label = "TEST" if is_test_env else "PRODUCTION"
                    logger.info(
                        "Connected to TastyTrade %s — %d accounts",
                        env_label,
                        len(self.accounts),
                    )
                    return True

                except Exception as e:
                    logger.error(
                        "TastyTrade connection attempt %d failed: %s",
                        attempt + 1,
                        e,
                    )
                    self.connected = False
                    if attempt < max_attempts - 1:
                        wait_time = self.base_retry_delay * (2 ** attempt)
                        logger.info("Waiting %ds before retry...", wait_time)
                        await asyncio.sleep(wait_time)

            logger.error(
                "Failed to connect to TastyTrade after %d attempts", max_attempts
            )
            return False

    async def connect_with_credentials(
        self,
        client_secret: str,
        refresh_token: str,
        is_test_env: Optional[bool] = None,
        **_kwargs: Any,
    ) -> bool:
        """Connect using explicitly provided OAuth credentials."""
        if not TASTYTRADE_AVAILABLE:
            return False
        try:
            is_test = (
                is_test_env if is_test_env is not None else settings.TASTYTRADE_IS_TEST
            )
            self.session = Session(client_secret, refresh_token, is_test=is_test)
            self.accounts = await Account.get(self.session)
            if not self.accounts:
                raise Exception("No TastyTrade accounts found")
            self.connected = True
            self.connection_start_time = datetime.now(UTC)
            self.connection_health.update(
                {
                    "status": "connected",
                    "last_successful_request": datetime.now(UTC),
                    "consecutive_failures": 0,
                    "connection_uptime": 0,
                }
            )
            return True
        except Exception as e:
            logger.error("TastyTrade login failed: %s", e)
            self.connection_health["last_error"] = str(e)
            self.connected = False
            self.session = None
            self.accounts = []
            return False

    async def _verify_connection(self) -> bool:
        try:
            if not self.accounts:
                return True
            account = self.accounts[0]
            await account.get_balances(self.session)
            self.connection_health.update(
                {"last_successful_request": datetime.now(UTC), "consecutive_failures": 0}
            )
            logger.info("Verification: TastyTrade connection healthy")
            return True
        except Exception as e:
            logger.warning("Verification: TastyTrade connection issue: %s", e)
            self.connection_health["consecutive_failures"] += 1
            return False

    async def disconnect(self):
        try:
            self.session = None
            self.connected = False
            self.connection_start_time = None
            self.accounts = []
            self.connection_health["status"] = "disconnected"
            logger.info("TastyTrade disconnected")
        except Exception as e:
            logger.warning("Error during TastyTrade disconnect: %s", e)

    # -----------------------------------------------------------------
    # Account helpers
    # -----------------------------------------------------------------

    def _find_account(self, account_number: Optional[str] = None) -> Optional[Any]:
        if not self.connected or not self.accounts:
            return None
        if account_number:
            return next(
                (a for a in self.accounts if a.account_number == account_number),
                None,
            )
        return self.accounts[0] if self.accounts else None

    async def get_accounts(self) -> List[Dict[str, Any]]:
        try:
            if not self.connected or not self.accounts:
                return []
            accounts_data = []
            for account in self.accounts:
                accounts_data.append(
                    {
                        "account_number": account.account_number,
                        "nickname": getattr(account, "nickname", ""),
                        "account_type": getattr(
                            account, "account_type_name", "Unknown"
                        ),
                        "is_closed": getattr(account, "is_closed", False),
                        "is_firm_error": getattr(account, "is_firm_error", False),
                        "is_firm_proprietary": getattr(
                            account, "is_firm_proprietary", False
                        ),
                        "is_futures_approved": getattr(
                            account, "is_futures_approved", False
                        ),
                        "is_test_drive": getattr(account, "is_test_drive", False),
                    }
                )
            logger.info("Retrieved %d TastyTrade accounts", len(accounts_data))
            return accounts_data
        except Exception as e:
            logger.error("Error getting TastyTrade accounts: %s", e)
            return []

    # -----------------------------------------------------------------
    # Positions
    # -----------------------------------------------------------------

    async def get_current_positions(
        self, account_number: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        try:
            target = self._find_account(account_number)
            if not target:
                return []

            positions = await target.get_positions(self.session)
            results = []
            for p in positions:
                try:
                    results.append(self._position_to_dict(p, target.account_number))
                except Exception as e:
                    logger.error("Error processing position %s: %s", getattr(p, "symbol", "?"), e)
            logger.info(
                "Retrieved %d TastyTrade positions for %s",
                len(results),
                target.account_number,
            )
            return results
        except Exception as e:
            logger.error("Error getting TastyTrade positions: %s", e)
            return []

    def _position_to_dict(self, position: Any, account_number: str) -> Dict[str, Any]:
        sf = _safe_float
        ss = _safe_str

        instrument_type_val = getattr(position, "instrument_type", None)
        if hasattr(instrument_type_val, "value"):
            instrument_type_val = instrument_type_val.value

        data: Dict[str, Any] = {
            "symbol": position.symbol,
            "instrument_type": instrument_type_val or "Unknown",
            "quantity": sf(position.quantity),
            "quantity_direction": ss(getattr(position, "quantity_direction", None)),
            "close_price": sf(getattr(position, "close_price", None)),
            "average_open_price": sf(getattr(position, "average_open_price", None)),
            "average_yearly_market_close_price": sf(
                getattr(position, "average_yearly_market_close_price", None)
            ),
            "average_daily_market_close_price": sf(
                getattr(position, "average_daily_market_close_price", None)
            ),
            "multiplier": sf(getattr(position, "multiplier", None), 1.0),
            "cost_effect": ss(getattr(position, "cost_effect", None)),
            "is_suppressed": bool(getattr(position, "is_suppressed", False)),
            "is_frozen": bool(getattr(position, "is_frozen", False)),
            "realized_day_gain": sf(getattr(position, "realized_day_gain", None)),
            "realized_day_gain_effect": ss(
                getattr(position, "realized_day_gain_effect", None), "None"
            ),
            "realized_day_gain_date": getattr(position, "realized_day_gain_date", None),
            "realized_today": sf(getattr(position, "realized_today", None)),
            "created_at": getattr(position, "created_at", None),
            "updated_at": getattr(position, "updated_at", None),
            "mark": sf(getattr(position, "mark", None)),
            "mark_value": sf(getattr(position, "mark_value", None)),
            "restricted_quantity": sf(getattr(position, "restricted_quantity", None)),
            "expired_quantity": sf(getattr(position, "expired_quantity", None)),
            "expiring_quantity": sf(getattr(position, "expiring_quantity", None)),
            "right_quantity": sf(getattr(position, "right_quantity", None)),
            "pending_quantity": sf(getattr(position, "pending_quantity", None)),
            "account_number": account_number,
        }

        if hasattr(position, "underlying_symbol"):
            data.update(
                {
                    "underlying_symbol": getattr(position, "underlying_symbol", ""),
                    "product_code": getattr(position, "product_code", ""),
                    "exchange": getattr(position, "exchange", ""),
                    "listed_market": getattr(position, "listed_market", ""),
                    "description": getattr(position, "description", ""),
                    "is_closing_only": getattr(position, "is_closing_only", False),
                    "active": getattr(position, "active", True),
                }
            )

        if instrument_type_val in ("Equity Option", "Index Option"):
            data.update(
                {
                    "option_type": getattr(position, "option_type", ""),
                    "strike_price": sf(getattr(position, "strike_price", 0)),
                    "expiration_date": getattr(position, "expiration_date", None),
                    "days_to_expiration": getattr(position, "days_to_expiration", 0),
                    "delta": sf(getattr(position, "delta", None)),
                    "gamma": sf(getattr(position, "gamma", None)),
                    "theta": sf(getattr(position, "theta", None)),
                    "vega": sf(getattr(position, "vega", None)),
                }
            )

        return data

    # -----------------------------------------------------------------
    # Transaction / trade history
    # -----------------------------------------------------------------

    async def get_transaction_history(
        self, account_number: str, days: int = 365
    ) -> List[Dict[str, Any]]:
        """Simple transaction list (id, account_number, symbol, action, quantity, price, commission)."""
        try:
            if not self.connected:
                return []
            account = self._find_account(account_number)
            if not account:
                return []
            txns = await account.get_history(self.session)
            results = []
            for t in txns or []:
                try:
                    results.append(
                        {
                            "id": getattr(t, "id", ""),
                            "account_number": account.account_number,
                            "symbol": getattr(t, "symbol", ""),
                            "action": getattr(t, "action", ""),
                            "quantity": float(getattr(t, "quantity", 0) or 0),
                            "price": float(getattr(t, "price", 0) or 0),
                            "commission": float(getattr(t, "commission", 0) or 0),
                        }
                    )
                except Exception as e:
                    logger.warning(
                        "Skipping TastyTrade history row (normalize failed): %s", e
                    )
                    continue
            return results
        except Exception as e:
            logger.warning("TastyTrade get_history (raw) failed for %s: %s", account_number, e)
            return []

    async def get_trade_history(
        self, account_number: str, days: int = 365
    ) -> List[Dict[str, Any]]:
        """Return filled trades as dicts for sync service."""
        if not TASTYTRADE_AVAILABLE:
            return []
        try:
            account = self._find_account(account_number)
            if not account:
                return []
            start = datetime.now(timezone.utc) - timedelta(days=days)
            end = datetime.now(timezone.utc)
            txns = await account.get_history(
                self.session, start_date=start.date(), end_date=end.date()
            )
            results: List[Dict[str, Any]] = []
            for t in txns:
                try:
                    txn_type = getattr(t, "transaction_type", "")
                    if hasattr(txn_type, "value"):
                        txn_type = txn_type.value
                    if txn_type != "Trade":
                        continue
                    transformed = self._transform_tastytrade_transaction(
                        t, account_number
                    )
                    if not transformed:
                        continue
                    executed_iso = (
                        f"{transformed.get('date')}T{transformed.get('time')}"
                    )
                    results.append(
                        {
                            "symbol": transformed.get("symbol", ""),
                            "side": transformed.get("action", ""),
                            "quantity": float(transformed.get("quantity", 0) or 0),
                            "price": float(transformed.get("price", 0) or 0),
                            "order_id": str(transformed.get("order_id", "") or ""),
                            "execution_id": str(
                                transformed.get("execution_id", "") or ""
                            ),
                            "executed_at": executed_iso,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        "Skipping TastyTrade trade history row for %s: %s",
                        account_number,
                        e,
                    )
                    continue
            return results
        except Exception as e:
            logger.error("TT trade history error: %s", e)
            return []

    async def get_transactions(
        self, account_number: str, days: int = 365
    ) -> List[Dict[str, Any]]:
        if not TASTYTRADE_AVAILABLE:
            return []
        try:
            account = self._find_account(account_number)
            if not account:
                return []
            start = datetime.now(timezone.utc) - timedelta(days=days)
            end = datetime.now(timezone.utc)
            txns = await account.get_history(
                self.session, start_date=start.date(), end_date=end.date()
            )
            return [
                self._transform_tastytrade_transaction(t, account_number)
                for t in txns
                if self._transform_tastytrade_transaction(t, account_number)
            ]
        except Exception as e:
            logger.error("TT transactions error: %s", e)
            return []

    async def get_dividends(
        self, account_number: str, days: int = 365
    ) -> List[Dict[str, Any]]:
        if not TASTYTRADE_AVAILABLE:
            return []
        try:
            account = self._find_account(account_number)
            if not account:
                return []
            start = datetime.now(timezone.utc) - timedelta(days=days)
            end = datetime.now(timezone.utc)
            txns = await account.get_history(
                self.session, start_date=start.date(), end_date=end.date()
            )
            results = []
            for t in txns:
                txn_type = getattr(t, "transaction_type", "")
                if hasattr(txn_type, "value"):
                    txn_type = txn_type.value
                if txn_type in ("Dividend", "Cash Dividend"):
                    transformed = self._transform_tastytrade_transaction(
                        t, account_number
                    )
                    if transformed:
                        results.append(transformed)
            return results
        except Exception as e:
            logger.error("TT dividends error: %s", e)
            return []

    async def get_account_balances(self, account_number: str) -> Dict[str, Any]:
        if not TASTYTRADE_AVAILABLE:
            return {}
        try:
            account = self._find_account(account_number)
            if not account:
                return {}
            bal = await account.get_balances(self.session)
            return {
                "cash_balance": float(getattr(bal, "cash_balance", 0) or 0),
                "net_liquidating_value": float(
                    getattr(bal, "net_liquidating_value", 0) or 0
                ),
                "long_margin_value": float(
                    getattr(bal, "long_margineable_value", 0) or 0
                ),
                "short_margin_value": float(
                    getattr(bal, "short_margineable_value", 0) or 0
                ),
                "equity_buying_power": float(
                    getattr(bal, "equity_buying_power", 0) or 0
                ),
                "derivative_buying_power": float(
                    getattr(bal, "derivative_buying_power", 0) or 0
                ),
                "day_trading_buying_power": float(
                    getattr(bal, "day_trading_buying_power", 0) or 0
                ),
                "maintenance_requirement": float(
                    getattr(bal, "maintenance_requirement", 0) or 0
                ),
                "margin_equity": float(getattr(bal, "margin_equity", 0) or 0),
            }
        except Exception as e:
            logger.error("TT balance error: %s", e)
            return {}

    # -----------------------------------------------------------------
    # Enhanced statements & tax lots
    # -----------------------------------------------------------------

    async def get_enhanced_account_statements(
        self, account_number: str, days: int = 365
    ) -> List[Dict[str, Any]]:
        """Comprehensive transaction history in standardized format."""
        if not self.connected:
            return []
        try:
            account = self._find_account(account_number)
            if not account:
                return []

            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=days)

            raw_transactions = await account.get_history(
                self.session,
                start_date=start_date.date(),
                end_date=end_date.date(),
                per_page=250,
            )

            all_transactions = []
            for txn in raw_transactions:
                transaction = self._transform_tastytrade_transaction(
                    txn, account_number, raw_transactions
                )
                if transaction:
                    all_transactions.append(transaction)

            all_transactions.sort(
                key=lambda x: f"{x['date']} {x['time']}", reverse=True
            )
            logger.info(
                "Enhanced TastyTrade statements: %d transactions for %s",
                len(all_transactions),
                account_number,
            )
            return all_transactions
        except Exception as e:
            logger.error("Error getting TastyTrade enhanced statements: %s", e)
            return []

    async def get_enhanced_tax_lots(self, account_number: str) -> List[Dict[str, Any]]:
        """Tax lots from positions with P&L calculations."""
        if not self.connected:
            return []
        try:
            account = self._find_account(account_number)
            if not account:
                return []

            positions = await account.get_positions(self.session)
            tax_lots = []
            for position in positions:
                try:
                    qty = float(position.quantity)
                    if qty == 0:
                        continue

                    cost_per_share = float(position.average_open_price)
                    current_price = (
                        float(position.close_price)
                        if position.close_price
                        else cost_per_share
                    )

                    instrument_type_val = getattr(position, "instrument_type", None)
                    if hasattr(instrument_type_val, "value"):
                        instrument_type_val = instrument_type_val.value

                    multiplier = float(getattr(position, "multiplier", 1) or 1)
                    if instrument_type_val in ("Equity Option", "Future Option"):
                        multiplier = 100

                    cost_basis = abs(qty) * cost_per_share * multiplier
                    market_value = abs(qty) * current_price * multiplier
                    unrealized_pnl = market_value - cost_basis
                    unrealized_pnl_pct = (
                        (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
                    )

                    acq_date = getattr(position, "created_at", datetime.now(UTC))
                    if hasattr(acq_date, "strftime"):
                        acq_str = acq_date.strftime("%Y-%m-%d")
                    else:
                        acq_str = datetime.now(UTC).strftime("%Y-%m-%d")
                    try:
                        days_held = (
                            datetime.now(UTC) - datetime.strptime(acq_str, "%Y-%m-%d").replace(tzinfo=UTC)
                        ).days
                    except Exception as e:
                        logger.warning(
                            "TastyTrade days_held parse failed for %s (acq_str=%s): %s",
                            getattr(position, "symbol", "?"),
                            acq_str,
                            e,
                        )
                        days_held = 0

                    tax_lots.append(
                        {
                            "lot_id": f"enhanced_tt_{position.symbol}_{account_number}",
                            "account_id": account_number,
                            "symbol": position.symbol,
                            "acquisition_date": acq_str,
                            "quantity": abs(qty),
                            "cost_per_share": cost_per_share,
                            "current_price": current_price,
                            "cost_basis": cost_basis,
                            "market_value": market_value,
                            "unrealized_pnl": unrealized_pnl,
                            "unrealized_pnl_pct": unrealized_pnl_pct,
                            "days_held": days_held,
                            "is_long_term": days_held >= 365,
                            "contract_type": instrument_type_val or "Unknown",
                            "currency": "USD",
                            "execution_id": f"tt_pos_{position.symbol}",
                            "source": "tastytrade_enhanced",
                            "multiplier": multiplier,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        "Error processing TastyTrade position %s: %s",
                        getattr(position, "symbol", "?"),
                        e,
                    )
            logger.info(
                "Enhanced TastyTrade tax lots: %d lots for %s",
                len(tax_lots),
                account_number,
            )
            return tax_lots
        except Exception as e:
            logger.error("Error getting TastyTrade enhanced tax lots: %s", e)
            return []

    async def get_account_info(self, account_number: str) -> Dict[str, Any]:
        if not self.connected:
            await self.connect_with_retry()
        try:
            account = self._find_account(account_number)
            if not account:
                return {"error": f"Account {account_number} not found"}

            balances = await account.get_balances(self.session)
            positions = await account.get_positions(self.session)

            return {
                "account_number": account_number,
                "account_type": getattr(account, "account_type_name", "Individual"),
                "broker": "TASTYTRADE",
                "net_liquidating_value": float(balances.net_liquidating_value),
                "total_cash": float(balances.cash_balance),
                "buying_power": float(balances.equity_buying_power),
                "day_trading_buying_power": float(balances.day_trading_buying_power),
                "positions_count": len(positions),
                "maintenance_requirement": float(balances.maintenance_requirement),
                "margin_equity": float(balances.margin_equity),
                "last_updated": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            logger.error("Error getting TastyTrade account info: %s", e)
            return {"error": str(e)}

    # -----------------------------------------------------------------
    # Transaction transformer
    # -----------------------------------------------------------------

    def _transform_tastytrade_transaction(
        self, txn: Any, account_number: str, all_transactions: Optional[List[Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Transform a TastyTrade Transaction object to a standardized dict."""
        try:
            executed_at = getattr(txn, "executed_at", None) or getattr(
                txn, "transaction_date", None
            )
            if not executed_at:
                return None

            action = str(getattr(txn, "action", "") or "")
            transaction_type = (
                "BUY" if ("Buy" in action or "Deposit" in action) else "SELL"
            )

            symbol = getattr(txn, "symbol", "CASH") or "CASH"
            underlying_symbol = getattr(txn, "underlying_symbol", None)

            instrument_type = getattr(txn, "instrument_type", "CASH")
            if hasattr(instrument_type, "value"):
                instrument_type = instrument_type.value
            instrument_type = instrument_type or "CASH"

            quantity = float(getattr(txn, "quantity", 0) or 0)
            price = float(getattr(txn, "price", 0) or 0)
            value = float(getattr(txn, "value", 0) or 0)
            commission = float(getattr(txn, "commission", 0) or 0)
            fees = float(getattr(txn, "regulatory_fees", 0) or 0)
            net_value = float(getattr(txn, "net_value", value) or value)

            clearing_date = getattr(txn, "clearing_date", None)
            settlement_date = (
                clearing_date.strftime("%Y-%m-%d") if clearing_date else None
            )

            txn_id = str(
                getattr(txn, "id", "")
                or f"tt_{account_number}_{executed_at.timestamp()}"
            )
            order_id = str(getattr(txn, "order_id", "") or "")

            description = self._build_transaction_description(
                symbol, instrument_type, action, value, txn, executed_at, all_transactions
            )

            return {
                "id": f"tt_{txn_id}",
                "order_id": order_id,
                "account": account_number,
                "symbol": symbol,
                "description": description,
                "type": "TRADE",
                "action": transaction_type,
                "quantity": abs(quantity),
                "price": price,
                "amount": abs(value),
                "commission": commission,
                "currency": "USD",
                "exchange": "TASTYTRADE",
                "date": executed_at.strftime("%Y-%m-%d"),
                "time": executed_at.strftime("%H:%M:%S"),
                "settlement_date": settlement_date,
                "source": "tastytrade_enhanced",
                "contract_type": str(instrument_type),
                "execution_id": str(txn_id),
                "net_amount": net_value,
            }
        except Exception as e:
            logger.warning("Error transforming TastyTrade transaction: %s", e)
            return None

    def _build_transaction_description(
        self,
        symbol: str,
        instrument_type: str,
        action: str,
        value: float,
        txn: Any,
        executed_at: Any,
        all_transactions: Optional[List[Any]],
    ) -> str:
        """Build enhanced description with option correlation for CASH transactions."""
        if symbol != "CASH":
            if instrument_type in ("Equity Option", "Future Option", "Option"):
                strike = getattr(txn, "strike_price", "")
                exp_date = getattr(txn, "expiration_date", "")
                option_type = getattr(txn, "option_type", "")
                if strike and exp_date and option_type:
                    exp_str = (
                        exp_date.strftime("%m/%d/%y")
                        if hasattr(exp_date, "strftime")
                        else str(exp_date)
                    )
                    return f"{symbol} {str(option_type).upper()} ${strike} exp {exp_str} - {action}"
                return f"{symbol} Option - {action}"
            return f"{symbol} {action}"

        related_option = self._find_related_option(executed_at, all_transactions)
        action_map = {
            "SELL_TO_CLOSE": "Settlement",
            "SELL_TO_OPEN": "Credit",
            "BUY_TO_CLOSE": "Debit",
            "BUY_TO_OPEN": "Debit",
            "Assignment": "Assignment",
            "Exercise": "Exercise",
            "Expiration": "Expiration",
        }

        if related_option:
            opt_desc = related_option["symbol"]
            if related_option.get("option_type") and related_option.get("strike"):
                opt_desc += f" {related_option['option_type'].upper()} ${related_option['strike']}"
            if related_option.get("expiration"):
                try:
                    exp = related_option["expiration"]
                    exp_str = (
                        exp.strftime("%m/%d/%y") if hasattr(exp, "strftime") else str(exp)
                    )
                    opt_desc += f" exp {exp_str}"
                except Exception as e:
                    logger.warning(
                        "TastyTrade transaction description: expiration format failed: %s", e
                    )
            label = next(
                (v for k, v in action_map.items() if k in action), "Settlement"
            )
            return f"CASH {label}: {opt_desc} ${abs(value):.2f}"

        label = next((v for k, v in action_map.items() if k in action), "Transaction")
        return f"CASH {label}: {action} ${abs(value):.2f}"

    @staticmethod
    def _find_related_option(
        executed_at: Any, all_transactions: Optional[List[Any]]
    ) -> Optional[Dict[str, Any]]:
        if not all_transactions or not executed_at:
            return None
        window = timedelta(minutes=5)
        for other in all_transactions:
            try:
                other_at = getattr(other, "executed_at", None) or getattr(
                    other, "transaction_date", None
                )
                if not other_at:
                    continue
                if abs((executed_at - other_at).total_seconds()) > window.total_seconds():
                    continue
                other_symbol = getattr(other, "symbol", "")
                other_type = getattr(other, "instrument_type", "")
                if hasattr(other_type, "value"):
                    other_type = other_type.value
                if other_symbol and other_symbol != "CASH" and "Option" in str(other_type):
                    return {
                        "symbol": other_symbol,
                        "instrument_type": other_type,
                        "strike": getattr(other, "strike_price", ""),
                        "option_type": getattr(other, "option_type", ""),
                        "expiration": getattr(other, "expiration_date", ""),
                        "action": getattr(other, "action", ""),
                    }
            except Exception as e:
                logger.warning("TastyTrade _find_related_option: skip candidate: %s", e)
                continue
        return None


# -----------------------------------------------------------------
# Module-level helpers
# -----------------------------------------------------------------


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, default: str = "Unknown") -> str:
    if value is None:
        return default
    return str(value)
