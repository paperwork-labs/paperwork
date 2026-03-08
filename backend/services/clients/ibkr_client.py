#!/usr/bin/env python3
"""
Clean IBKR Client - Real-time Trading API
Focuses on real-time positions, trading, and market data via ib_insync.
Historical data and tax lots handled by separate FlexQuery client.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List
import os
import sys

try:
    from ib_insync import (
        IB,
        util,
        Contract,
        Stock,
        Option,
        MarketOrder,
        LimitOrder,
        StopOrder,
        StopLimitOrder,
    )

    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False
    IB = None
    MarketOrder = LimitOrder = StopOrder = StopLimitOrder = None

try:
    from backend.config import settings
except ImportError:
    from config import settings

logger = logging.getLogger(__name__)


def _safe_float(val) -> float | None:
    """Coerce value to float for DB Float columns; return None if invalid."""
    if val is None or val == "" or val == "None":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


class IBKRClient:
    """
    Clean IBKR client for real-time trading operations.

    Responsibilities:
    - Real-time positions and account data
    - Order placement and management
    - Live market data
    - Connection management (SINGLETON)

    NOT responsible for:
    - Historical statements (use FlexQuery)
    - Tax lot calculations (use FlexQuery)
    - CSV parsing (use FlexQuery)
    """

    _instance = None
    # Create locks lazily within an active event loop to avoid cross-loop issues in tests
    _lock = None

    def __new__(cls):
        """Singleton to prevent multiple connections."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True

        # Default connection params; force deterministic values in tests
        if (
            os.environ.get("PYTEST_CURRENT_TEST")
            or os.environ.get("AXIOMFOLIO_TESTING") == "1"
            or "pytest" in sys.modules
        ):
            self.host = "127.0.0.1"
            self.port = 7497
            self.client_id = 1
        else:
            self.host = getattr(settings, "IBKR_HOST", "127.0.0.1")
            self.port = int(getattr(settings, "IBKR_PORT", 7497))
            self.client_id = int(getattr(settings, "IBKR_CLIENT_ID", 1))

        # Lazy IB creation; allow tests to patch IB before instantiation
        self.ib = None
        self.connected = False
        self.managed_accounts = []

        # Health tracking expected by tests
        self.connection_health = {
            "status": "disconnected",
            "consecutive_failures": 0,
        }
        self.retry_count = 0

    async def connect(
        self,
        host: str | None = None,
        port: int | None = None,
        client_id: int | None = None,
    ) -> bool:
        """Connect to IBKR Gateway/TWS.

        Optional host/port/client_id override the instance defaults for this
        connection attempt (useful for per-user gateway settings).
        """
        if not IBKR_AVAILABLE:
            return False

        connect_host = host or self.host
        connect_port = port or self.port
        connect_client_id = client_id or self.client_id

        lock = self._lock
        if lock is None:
            lock = asyncio.Lock()
            self._lock = lock
        async with lock:
            await self._cleanup()

            try:
                logger.info("🔄 Connecting to IBKR Gateway at %s:%s ...", connect_host, connect_port)

                self.ib = IB()
                self.ib._owner_loop = asyncio.get_running_loop()

                test_mode = (
                    os.environ.get("AXIOMFOLIO_TESTING") == "1"
                    or "pytest" in sys.modules
                )
                timeout_s = 0.2 if test_mode else 15

                util.patchAsyncio()

                await asyncio.wait_for(
                    self.ib.connectAsync(
                        host=connect_host,
                        port=connect_port,
                        clientId=connect_client_id,
                    ),
                    timeout=timeout_s,
                )

                self.connected = bool(self.ib and self.ib.isConnected())
                if self.connected:
                    self.managed_accounts = self.ib.managedAccounts() or []
                    self.connection_health.update({"status": "connected"})
                    self.retry_count = 0
                    logger.info("✅ Connected to IBKR Gateway. Accounts: %s", self.managed_accounts)

                    # Subscribe to account summary so accountSummary() returns data
                    try:
                        self.ib.reqAccountSummary()
                        await asyncio.sleep(2)
                        logger.info("✅ Account summary subscription active")
                    except Exception as e:
                        logger.warning("Account summary subscription failed: %s", e)

                    return True

            except asyncio.TimeoutError:
                logger.warning("⏱️ IBKR Gateway connection timed out after %ss", timeout_s)
                self.connection_health["consecutive_failures"] = (
                    self.connection_health.get("consecutive_failures", 0) + 1
                )
            except Exception as e:
                logger.error("❌ Connection failed: %s", e)
                self.connection_health["consecutive_failures"] = (
                    self.connection_health.get("consecutive_failures", 0) + 1
                )
            await self._cleanup()
            return False

    async def connect_with_retry(self, max_attempts: int = 5) -> bool:
        """Retry connection up to max_attempts with exponential backoff."""
        for attempt in range(max_attempts):
            success = await self.connect()
            if success:
                self.retry_count = 0
                self.connection_health["consecutive_failures"] = 0
                return True
            self.retry_count += 1
            if attempt < max_attempts - 1:
                delay = min(2**attempt, 16)
                logger.warning(
                    "IB Gateway connect attempt %d/%d failed, retrying in %ds: %s",
                    attempt + 1,
                    max_attempts,
                    delay,
                    self.connection_health.get("status", "unknown"),
                )
                await asyncio.sleep(delay)
        return False

    def _generate_client_id(self) -> int:
        """Deprecated: tests expect deterministic client_id=1."""
        return self.client_id or 1

    async def _cleanup(self):
        """Clean up existing connection."""
        try:
            if self.ib:
                try:
                    self.ib.disconnect()
                except Exception as e:
                    logger.error(f"❌ Cleanup error: {e}")
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
        finally:
            self.connected = False
            self.managed_accounts = []
            # Keep client_id constant for tests
            self.ib = None

    async def get_positions(self, account_id: str) -> List[Dict]:
        """Get current positions for account."""
        if not await self._ensure_connected():
            return []

        try:
            positions = self.ib.positions(account_id)

            position_data = []
            for pos in positions:
                if pos.position != 0:  # Only non-zero positions
                    position_data.append(
                        {
                            "account": pos.account,
                            "symbol": pos.contract.symbol,
                            "position": float(pos.position),
                            "market_value": (
                                float(pos.marketValue) if pos.marketValue else 0.0
                            ),
                            "avg_cost": float(pos.avgCost) if pos.avgCost else 0.0,
                            "unrealized_pnl": (
                                float(pos.unrealizedPNL) if pos.unrealizedPNL else 0.0
                            ),
                            "contract_type": pos.contract.secType,
                            "currency": pos.contract.currency or "USD",
                            "exchange": pos.contract.exchange,
                        }
                    )

            logger.info(f"📊 Retrieved {len(position_data)} positions for {account_id}")
            return position_data

        except Exception as e:
            logger.error(f"❌ Error getting positions: {e}")
            return []

    async def get_account_summary(self, account_id: str) -> Dict:
        """Get account summary data for a specific account."""
        if not await self._ensure_connected():
            return {}

        try:
            all_items = self.ib.accountSummary()
            if not all_items:
                self.ib.reqAccountSummary()
                await asyncio.sleep(2)
                all_items = self.ib.accountSummary()

            summary_data = {}
            for item in all_items:
                if item.account == account_id:
                    summary_data[item.tag] = {
                        "value": item.value,
                        "currency": item.currency,
                    }

            logger.info("Retrieved account summary for %s (%d tags)", account_id, len(summary_data))
            return summary_data

        except Exception as e:
            logger.error("Error getting account summary for %s: %s", account_id, e)
            return {}

    async def _ensure_connected(self) -> bool:
        """Ensure we have a valid connection in the current event loop."""
        current_loop = asyncio.get_running_loop()
        ib_loop = getattr(self.ib, "_owner_loop", None) if self.ib else None

        if self.ib and self.ib.isConnected() and ib_loop is current_loop:
            return True

        if self.ib and ib_loop is not None and ib_loop is not current_loop:
            logger.warning(
                "IBKRClient: IB instance bound to different event loop — reconnecting in current loop"
            )
            try:
                self.ib.disconnect()
            except Exception:
                pass
            self.ib = None
            self.connected = False

        if not self.connected or not self.ib or not self.ib.isConnected():
            logger.info(
                "IBKR not connected; attempting auto-reconnect (host=%s, port=%s, client_id=%s)",
                self.host,
                self.port,
                self.client_id,
            )
            return await self.connect_with_retry()
        return True

    def get_status(self) -> Dict:
        """Get connection status."""
        return {
            "connected": self.connected,
            "client_id": self.client_id,
            "accounts": self.managed_accounts,
            "gateway_clients": (
                len(self.managed_accounts) if self.managed_accounts else 0
            ),
        }

    async def disconnect(self):
        """Properly disconnect and clear instance state."""
        try:
            if self.ib:
                try:
                    self.ib.disconnect()
                except Exception as e:
                    logger.error(f"❌ Cleanup error: {e}")
        finally:
            self.connected = False
            self.ib = None
            self.connection_health["status"] = "disconnected"
            logger.info("✅ IBKR disconnected")

    async def discover_managed_accounts(self) -> List[str]:
        """Discover managed accounts from IBKR if connected; safe for tests.
        Returns a list of account ids or empty list on failure.
        """
        try:
            if not await self._ensure_connected():
                return []
            accounts: List[str] = []
            try:
                accounts = list(self.ib.managedAccounts()) or []
            except Exception:
                accounts = []
            self.managed_accounts = accounts
            return accounts
        except Exception:
            return []

    def is_connected(self) -> bool:
        """Check if IB Gateway is currently connected."""
        return bool(self.connected and self.ib and self.ib.isConnected())

    async def get_option_greeks(
        self, contracts: list, timeout: float = 10.0
    ) -> List[Dict]:
        """Request market data for option contracts and extract Greeks.

        Each contract should be an ib_insync Option or similar Contract object.
        Returns a list of dicts with: symbol, strike, expiry, right, delta,
        gamma, theta, vega, implied_volatility, last_price, bid, ask.
        """
        if not IBKR_AVAILABLE or not await self._ensure_connected():
            return []

        results = []
        # Batch in groups of 50 to respect IBKR rate limits
        batch_size = 50
        for i in range(0, len(contracts), batch_size):
            batch = contracts[i : i + batch_size]
            tickers = []
            for contract in batch:
                try:
                    self.ib.qualifyContracts(contract)
                    ticker = self.ib.reqMktData(
                        contract, genericTickList="106,100", snapshot=True
                    )
                    tickers.append((contract, ticker))
                except Exception as e:
                    logger.debug("Greeks request failed for %s: %s", contract, e)

            if tickers:
                await asyncio.sleep(min(timeout, 5))

            for contract, ticker in tickers:
                try:
                    greeks = {}
                    if hasattr(ticker, "modelGreeks") and ticker.modelGreeks:
                        mg = ticker.modelGreeks
                        greeks = {
                            "delta": getattr(mg, "delta", None),
                            "gamma": getattr(mg, "gamma", None),
                            "theta": getattr(mg, "theta", None),
                            "vega": getattr(mg, "vega", None),
                            "implied_volatility": getattr(mg, "impliedVol", None),
                        }
                    results.append(
                        {
                            "symbol": contract.symbol,
                            "strike": contract.strike,
                            "expiry": contract.lastTradeDateOrContractMonth,
                            "right": contract.right,
                            "last_price": getattr(ticker, "last", None),
                            "bid": getattr(ticker, "bid", None),
                            "ask": getattr(ticker, "ask", None),
                            **greeks,
                        }
                    )
                    self.ib.cancelMktData(contract)
                except Exception as e:
                    logger.debug("Greeks parse failed: %s", e)

        logger.info("Retrieved Greeks for %d/%d contracts", len(results), len(contracts))
        return results

    async def get_option_chain(
        self, symbol: str, exchange: str = "SMART"
    ) -> Dict:
        """Fetch available option chain (expirations and strikes) for a symbol.

        Returns: { expirations: [...], chains: { "2026-03-21": { calls: [...], puts: [...] } } }
        """
        if not IBKR_AVAILABLE or not await self._ensure_connected():
            return {"expirations": [], "chains": {}}

        try:
            stock = Stock(symbol, exchange, "USD")
            self.ib.qualifyContracts(stock)
            chains = self.ib.reqSecDefOptParams(
                stock.symbol, "", stock.secType, stock.conId
            )

            if not chains:
                return {"expirations": [], "chains": {}}

            # Use the SMART exchange chain or fallback to first
            chain = next(
                (c for c in chains if c.exchange == "SMART"), chains[0]
            )

            expirations = sorted(chain.expirations)
            strikes = sorted(chain.strikes)

            result: Dict = {"expirations": expirations, "chains": {}}

            # For each expiration, build Option contracts and fetch Greeks
            for exp in expirations[:5]:  # Limit to 5 nearest expirations
                calls = []
                puts = []
                contracts = []

                for strike in strikes:
                    call = Option(symbol, exp, strike, "C", exchange)
                    put = Option(symbol, exp, strike, "P", exchange)
                    contracts.extend([call, put])

                if contracts:
                    greeks_data = await self.get_option_greeks(contracts)
                    for gd in greeks_data:
                        entry = {
                            "strike": gd["strike"],
                            "last": gd.get("last_price"),
                            "bid": gd.get("bid"),
                            "ask": gd.get("ask"),
                            "iv": gd.get("implied_volatility"),
                            "delta": gd.get("delta"),
                            "gamma": gd.get("gamma"),
                            "theta": gd.get("theta"),
                            "vega": gd.get("vega"),
                        }
                        if gd["right"] == "C":
                            calls.append(entry)
                        else:
                            puts.append(entry)

                result["chains"][exp] = {"calls": calls, "puts": puts}

            return result

        except Exception as e:
            logger.error("Option chain fetch failed for %s: %s", symbol, e)
            return {"expirations": [], "chains": {}}

    async def get_realtime_option_data(self, contract) -> Dict:
        """Get a snapshot of real-time option data for a single contract."""
        if not IBKR_AVAILABLE or not await self._ensure_connected():
            return {}

        try:
            self.ib.qualifyContracts(contract)
            ticker = self.ib.reqMktData(
                contract, genericTickList="106,100", snapshot=True
            )
            await asyncio.sleep(3)

            result = {
                "symbol": contract.symbol,
                "strike": contract.strike,
                "expiry": contract.lastTradeDateOrContractMonth,
                "right": contract.right,
                "last": getattr(ticker, "last", None),
                "bid": getattr(ticker, "bid", None),
                "ask": getattr(ticker, "ask", None),
                "volume": getattr(ticker, "volume", None),
                "open_interest": getattr(ticker, "openInterest", None),
            }

            if hasattr(ticker, "modelGreeks") and ticker.modelGreeks:
                mg = ticker.modelGreeks
                result.update(
                    {
                        "delta": getattr(mg, "delta", None),
                        "gamma": getattr(mg, "gamma", None),
                        "theta": getattr(mg, "theta", None),
                        "vega": getattr(mg, "vega", None),
                        "implied_volatility": getattr(mg, "impliedVol", None),
                    }
                )

            self.ib.cancelMktData(contract)
            return result

        except Exception as e:
            logger.error("Realtime option data failed: %s", e)
            return {}

    # --- Order execution helpers and methods ---

    def _build_contract(self, symbol: str) -> Contract:
        """Create a US stock contract for the given symbol."""
        return Stock(symbol, "SMART", "USD")

    def _build_order(
        self,
        action: str,
        quantity: float,
        order_type: str,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ):
        """Build an ib_insync Order from parameters.

        order_type: 'MKT', 'LMT', 'STP', 'STP_LMT' (or 'STP LMT')
        """
        action = str(action).upper()
        order_type = str(order_type).upper().replace(" ", "_")
        if order_type == "STP_LMT":
            order_type = "STP LMT"  # ib_insync uses space

        if order_type == "MKT":
            return MarketOrder(action, quantity)
        if order_type == "LMT":
            if limit_price is None:
                raise ValueError("limit_price required for LMT orders")
            return LimitOrder(action, quantity, float(limit_price))
        if order_type == "STP":
            if stop_price is None:
                raise ValueError("stop_price required for STP orders")
            return StopOrder(action, quantity, float(stop_price))
        if order_type in ("STP_LMT", "STP LMT"):
            if limit_price is None or stop_price is None:
                raise ValueError("limit_price and stop_price required for STP_LMT orders")
            return StopLimitOrder(
                action, quantity, float(limit_price), float(stop_price)
            )
        raise ValueError(f"Unsupported order_type: {order_type}")

    def _is_paper_trading(self) -> bool:
        """True if connected to paper trading.

        Authority: settings.IBKR_TRADING_MODE (paper|live).
        Fallback:  port-based detection per IB docs:
          - Paper ports: 7497 (TWS Paper), 4002 (Gateway Paper)
          - Live ports:  7496 (TWS Live),  4001 (Gateway Live)
        Port 8888 (extrange unified) is ambiguous; rely on IBKR_TRADING_MODE.
        """
        mode = getattr(settings, "IBKR_TRADING_MODE", "").lower()
        if mode == "paper":
            return True
        if mode == "live":
            return False
        port = getattr(self, "port", None) or getattr(
            settings, "IBKR_PORT", 7497
        )
        return int(port) in (7497, 4002)

    async def what_if_order(
        self,
        symbol: str,
        action: str,
        quantity: float,
        order_type: str,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> Dict:
        """Simulated order preview (commission, margin impact). No real order placed.

        Returns dict with: estimated_commission, estimated_margin_impact,
        estimated_equity_with_loan, maintenance_margin, initial_margin.
        """
        if not IBKR_AVAILABLE or not await self._ensure_connected():
            return {
                "estimated_commission": None,
                "estimated_margin_impact": None,
                "estimated_equity_with_loan": None,
                "maintenance_margin": None,
                "initial_margin": None,
                "error": "Not connected or ib_insync not available",
            }

        try:
            contract = self._build_contract(symbol)
            self.ib.qualifyContracts(contract)
            order = self._build_order(
                action, quantity, order_type, limit_price, stop_price
            )
            state = await self.ib.whatIfOrderAsync(contract, order)
            est_commission = None
            if (
                state.commission is not None
                and state.commission != getattr(util, "UNSET_DOUBLE", float("inf"))
            ):
                try:
                    est_commission = float(state.commission)
                except (TypeError, ValueError):
                    pass
            return {
                "estimated_commission": est_commission,
                "estimated_margin_impact": _safe_float(state.maintMarginChange),
                "estimated_equity_with_loan": _safe_float(state.equityWithLoanAfter),
                "maintenance_margin": _safe_float(state.maintMarginAfter),
                "initial_margin": _safe_float(state.initMarginAfter),
            }
        except Exception as e:
            logger.error("what_if_order failed for %s: %s", symbol, e)
            return {
                "estimated_commission": None,
                "estimated_margin_impact": None,
                "estimated_equity_with_loan": None,
                "maintenance_margin": None,
                "initial_margin": None,
                "error": str(e),
            }

    async def place_order(
        self,
        symbol: str,
        action: str,
        quantity: float,
        order_type: str,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> Dict:
        """Place a real order. Requires ENABLE_TRADING.

        action: 'BUY' or 'SELL'
        order_type: 'MKT', 'LMT', 'STP', 'STP_LMT'
        Returns dict with broker_order_id, status.
        """
        if not IBKR_AVAILABLE:
            return {"broker_order_id": None, "status": "error", "error": "ib_insync not available"}

        if not getattr(settings, "ENABLE_TRADING", False):
            return {
                "broker_order_id": None,
                "status": "rejected",
                "error": "ENABLE_TRADING is False",
            }

        if not await self._ensure_connected():
            return {
                "broker_order_id": None,
                "status": "error",
                "error": "Not connected to IBKR",
            }

        if not self._is_paper_trading():
            allow_live = getattr(settings, "ALLOW_LIVE_ORDERS", False)
            if isinstance(allow_live, str):
                allow_live = allow_live.strip().lower() in ("true", "1", "yes")
            if not allow_live:
                return {
                    "broker_order_id": None,
                    "status": "rejected",
                    "error": "Live orders blocked. Set ALLOW_LIVE_ORDERS=true to enable.",
                }
            port = getattr(self, "port", None) or getattr(settings, "IBKR_PORT", "?")
            mode = getattr(settings, "IBKR_TRADING_MODE", "unknown")
            logger.warning("Placing LIVE order: %s %s %s (port=%s, mode=%s)", action, quantity, symbol, port, mode)

        try:
            contract = self._build_contract(symbol)
            self.ib.qualifyContracts(contract)
            order = self._build_order(
                action, quantity, order_type, limit_price, stop_price
            )
            trade = self.ib.placeOrder(contract, order)
            broker_order_id = trade.order.orderId
            status = trade.orderStatus.status if trade.orderStatus else "Submitted"
            return {
                "broker_order_id": broker_order_id,
                "status": status,
            }
        except Exception as e:
            logger.error("place_order failed for %s: %s", symbol, e)
            return {
                "broker_order_id": None,
                "status": "error",
                "error": str(e),
            }

    async def cancel_order(self, broker_order_id: int | str) -> Dict:
        """Cancel an order by its broker order ID."""
        if not IBKR_AVAILABLE:
            return {"status": "error", "error": "ib_insync not available"}

        if not getattr(settings, "ENABLE_TRADING", False):
            return {"status": "rejected", "error": "ENABLE_TRADING is False"}

        if not await self._ensure_connected():
            return {"status": "error", "error": "Not connected to IBKR"}

        if not self._is_paper_trading():
            logger.warning("Cancelling LIVE order: broker_order_id=%s", broker_order_id)

        try:
            order_id = int(broker_order_id)
            for trade in self.ib.trades():
                if trade.order.orderId == order_id:
                    self.ib.cancelOrder(trade.order)
                    return {"broker_order_id": order_id, "status": "PendingCancel"}
            return {
                "broker_order_id": order_id,
                "status": "error",
                "error": f"Order {order_id} not found in session",
            }
        except Exception as e:
            logger.error("cancel_order failed for %s: %s", broker_order_id, e)
            return {"broker_order_id": broker_order_id, "status": "error", "error": str(e)}

    async def get_order_status(self, broker_order_id: int | str) -> Dict:
        """Return current order status from IB."""
        if not IBKR_AVAILABLE or not await self._ensure_connected():
            return {"broker_order_id": broker_order_id, "status": "unknown", "error": "Not connected"}

        try:
            order_id = int(broker_order_id)
            for trade in self.ib.trades():
                if trade.order.orderId == order_id:
                    status = trade.orderStatus.status if trade.orderStatus else "Unknown"
                    filled = getattr(trade.orderStatus, "filled", 0) or 0
                    remaining = getattr(trade.orderStatus, "remaining", 0) or 0
                    return {
                        "broker_order_id": order_id,
                        "status": status,
                        "filled": float(filled),
                        "remaining": float(remaining),
                    }
            return {
                "broker_order_id": order_id,
                "status": "unknown",
                "error": "Order not found in session",
            }
        except Exception as e:
            logger.error("get_order_status failed for %s: %s", broker_order_id, e)
            return {"broker_order_id": broker_order_id, "status": "unknown", "error": str(e)}


# Global singleton instance
ibkr_client = IBKRClient()
