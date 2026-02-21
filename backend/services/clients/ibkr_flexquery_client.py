#!/usr/bin/env python3
"""
IBKR FlexQuery Client - Official Tax Lots & Historical Data
Uses IBKR's FlexQuery API to get official tax lots, cost basis, and statements.
This is the CORRECT way to get tax lot data instead of manual calculations.
"""

import asyncio
import logging
import aiohttp
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional
import os
import sys

try:
    from backend.config import settings
except ImportError:
    from config import settings

logger = logging.getLogger(__name__)

_IBKR_ACCT_PREFIXES = ("U", "F", "D", "I", "S")


def _is_placeholder_account(account_id: str | None) -> bool:
    """Return True when *account_id* is missing or not a real IBKR account number.

    Real IBKR account numbers start with a letter prefix (U, F, D, I, S)
    followed by digits, e.g. ``U19490886``.  Anything else (None, empty
    string, legacy placeholders like ``"IBKR_FLEX"``) is treated as a
    placeholder and XML account-filtering is skipped so that all accounts
    in the FlexQuery report are included.
    """
    if not account_id:
        return True
    aid = account_id.strip()
    if not aid:
        return True
    if not aid[0].upper() in _IBKR_ACCT_PREFIXES:
        return True
    return not aid[1:].isdigit()


class IBKRFlexQueryClient:
    """
    FlexQuery client for official IBKR reporting data.

    Gets official data from IBKR's reporting system:
    - Tax lots with official cost basis
    - Activity statements
    - Trade confirmations
    - 1099 reporting data

    This is the authoritative source for tax lot information.

    Constructor accepts optional token and query_id for per-account credentials.
    If not provided, falls back to settings.IBKR_FLEX_TOKEN / IBKR_FLEX_QUERY_ID.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        query_id: Optional[str] = None,
    ):
        self.base_url = (
            "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
        )

        # Use provided credentials over settings
        if token is not None and token.strip():
            self.token = token.strip().strip('"').strip("'")
        else:
            _raw_token = getattr(settings, "IBKR_FLEX_TOKEN", None)
            try:
                self.token = _raw_token.strip().strip('"').strip("'") if _raw_token else None
            except Exception:
                self.token = _raw_token

        if query_id is not None and str(query_id).strip():
            self.query_id = str(query_id).strip().strip('"').strip("'")
        else:
            _raw_query = getattr(settings, "IBKR_FLEX_QUERY_ID", None)
            try:
                self.query_id = (
                    _raw_query.strip().strip('"').strip("'") if _raw_query else None
                )
            except Exception:
                self.query_id = _raw_query

        # Simple in-memory report cache: {account_id: (timestamp, raw_xml)}
        self._report_cache: dict[str, tuple[float, str]] = {}

    @staticmethod
    def extract_account_ids(xml_data: str) -> list[str]:
        """Extract unique IBKR account IDs from a FlexQuery XML report."""
        try:
            root = ET.fromstring(xml_data)
            ids: set[str] = set()
            for stmt in root.iter("FlexStatement"):
                aid = stmt.get("accountId", "").strip()
                if aid:
                    ids.add(aid)
            if not ids:
                for elem in root.iter():
                    aid = elem.get("accountId", "").strip()
                    if aid:
                        ids.add(aid)
            return sorted(ids)
        except Exception:
            return []

    async def validate_credentials(self) -> tuple[bool, str]:
        """Quick check that token + query_id are accepted by IBKR (single request, no retries)."""
        if not self.token or not self.query_id:
            return False, "FlexQuery token or query ID is missing."
        url = f"{self.base_url}/SendRequest"
        params = {"t": self.token, "q": self.query_id, "v": "3"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    body = await resp.text()
                    root = ET.fromstring(body)
                    status = root.findtext("Status")
                    if status == "Success":
                        return True, "Credentials valid."
                    err = root.findtext("ErrorMessage") or "Unknown IBKR error"
                    return False, err
        except Exception as exc:
            return False, f"Validation request failed: {exc}"

    async def get_full_report(
        self, account_id: str, cache_ttl_seconds: int = 60
    ) -> Optional[str]:
        """Fetch one FlexQuery report per account and cache briefly to avoid collisions.

        Returns full raw XML string or None if unavailable.
        """
        if not self.token or not self.query_id:
            logger.error("❌ FlexQuery token/query_id not configured")
            return None

        import time

        now = time.time()
        cached = self._report_cache.get(account_id)
        if cached and (now - cached[0] <= cache_ttl_seconds) and cached[1]:
            return cached[1]

        try:
            # Never pass the acct param on the initial request.  Most FlexQuery
            # setups are global (all accounts); adding the acct filter often
            # triggers "Account is invalid" errors and extra retry delays.
            acct_for_request = None
            ref_code = await self._request_report(acct_for_request)
            if not ref_code:
                return None

            # Poll for readiness
            max_attempts, delay = 20, 6.0
            for _ in range(max_attempts):
                data = await self._get_report(ref_code, acct_for_request)
                if data:
                    self._report_cache[account_id] = (time.time(), data)
                    return data
                await asyncio.sleep(delay)
            return None
        except Exception as e:
            logger.error(f"❌ Error getting full report: {e}")
            return None

    async def get_official_tax_lots(self, account_id: str) -> List[Dict]:
        """
        Get official tax lots from IBKR FlexQuery.
        This is the CORRECT source for tax lot data.
        """
        if not self.token or not self.query_id:
            logger.error("❌ FlexQuery token/query_id not configured")
            logger.info("📋 Setup required:")
            logger.info("   1. Go to IBKR Client Portal > Reports > Flex Queries")
            logger.info("   2. Create FlexQuery with 'Open Positions' section")
            logger.info("   3. Enable FlexQuery Web Service and get token")
            logger.info("   4. Set IBKR_FLEX_TOKEN and IBKR_FLEX_QUERY_ID in env")
            return []

        try:
            logger.info(f"📊 Requesting official tax lots for {account_id}")

            report_data = await self.get_full_report(account_id)
            if not report_data:
                return []

            # Step 3: Parse tax lots from XML
            tax_lots = self._parse_tax_lots(report_data, account_id)

            logger.info(f"✅ Retrieved {len(tax_lots)} official tax lots")
            return tax_lots

        except Exception as e:
            logger.error(f"❌ Error getting official tax lots: {e}")
            return []

    async def get_option_positions(self, account_id: str) -> List[Dict]:
        """
        Get option positions from IBKR FlexQuery OpenPositions section.
        Parses option-specific data for Option records.
        """
        if not self.token or not self.query_id:
            logger.error("❌ FlexQuery token/query_id not configured for options")
            return []

        try:
            logger.info(f"📊 Requesting option positions for {account_id}")

            report_data = await self.get_full_report(account_id)
            if not report_data:
                return []

            # Step 3: Parse option positions from XML
            option_positions = self._parse_option_positions(report_data, account_id)

            logger.info(f"✅ Retrieved {len(option_positions)} option positions")
            return option_positions

        except Exception as e:
            logger.error(f"❌ Error getting option positions: {e}")
            return []

    async def get_historical_option_exercises(self, account_id: str) -> List[Dict]:
        """
        Get historical option exercises and assignments from IBKR FlexQuery OptionEAE section.
        Parses option exercise/assignment history for tax and P&L tracking.
        """
        if not self.token or not self.query_id:
            logger.error(
                "❌ FlexQuery token/query_id not configured for option exercises"
            )
            return []

        try:
            logger.info(f"📊 Requesting historical option exercises for {account_id}")

            report_data = await self.get_full_report(account_id)
            if not report_data:
                return []

            # Step 3: Parse option exercises from XML
            option_exercises = self._parse_option_exercises(report_data, account_id)

            logger.info(
                f"✅ Retrieved {len(option_exercises)} historical option exercises"
            )
            return option_exercises

        except Exception as e:
            logger.error(f"❌ Error getting historical option exercises: {e}")
            return []

    async def _request_report(self, account_id: Optional[str] = None) -> Optional[str]:
        """Request FlexQuery report generation with exponential back-off (40→80→160 s)."""
        url = f"{self.base_url}/SendRequest"
        params = {"t": self.token, "q": self.query_id, "v": "3"}
        if account_id:
            params["acct"] = account_id

        # Test-aware throttling: drastically reduce waits/attempts under pytest/CI
        is_testing = (
            os.environ.get("AXIOMFOLIO_TESTING") == "1" or "pytest" in sys.modules
        )
        if is_testing:
            delays = [0, 0.05, 0.1]
            max_attempts = 2
        else:
            delays = [0, 40, 80, 160]  # attempt 0 delay == 0 so we fire immediately
            max_attempts = 3
        for attempt in range(max_attempts):
            if attempt > 0:
                wait = delays[attempt]
                logger.warning(
                    f"⏳ FlexQuery throttled – retrying in {wait}s (attempt {attempt + 1}/{max_attempts})"
                )
                await asyncio.sleep(wait)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        xml_content = await response.text()

                        # Hard 429 status check
                        if response.status == 429:
                            continue  # triggers back-off loop

                        # Parse XML regardless to find error messages
                        try:
                            root = ET.fromstring(xml_content)
                        except ET.ParseError:
                            root = None

                        if root is not None:
                            status_tag = root.find("Status")
                            if status_tag is not None and status_tag.text == "Success":
                                ref_code_tag = root.find("ReferenceCode")
                                if ref_code_tag is not None:
                                    logger.info(
                                        f"✅ Report requested: {ref_code_tag.text}"
                                    )
                                    return ref_code_tag.text
                            else:
                                # Detect rate-limit / invalid account errors
                                err_msg_tag = root.find("ErrorMessage")
                                err_text = (
                                    err_msg_tag.text if err_msg_tag is not None else ""
                                )
                                if any(
                                    keyword in err_text
                                    for keyword in ["Too many requests", "rate limit"]
                                ):
                                    logger.warning(f"⚠️  FlexQuery error: {err_text}")
                                    continue  # retry with backoff
                                if "Account is invalid" in err_text and params.get(
                                    "acct"
                                ):
                                    # Fallback: try again WITHOUT acct filter — many Flex setups are global
                                    logger.warning(
                                        "⚠️  Account-specific FlexQuery failed; retrying without acct filter"
                                    )
                                    params.pop("acct", None)
                                    continue  # retry same attempt counter
                                logger.error(
                                    f"❌ Report request failed: {err_text or 'Unknown error'}"
                                )
                                return None
                        else:
                            # Non-XML or other HTTP failure
                            if response.status != 200:
                                logger.error(
                                    f"❌ HTTP error requesting report: {response.status}"
                                )
                                continue  # retry on non-200 as well
                            # Unknown payload but status OK – break
                            logger.error(
                                "❌ Unexpected response while requesting report"
                            )
                            return None
            except Exception as e:
                logger.error(f"❌ Exception requesting report: {e}")
                continue  # retry

        logger.error("❌ FlexQuery report request failed after retries")
        return None

    async def _get_report(
        self, reference_code: str, account_id: Optional[str] = None
    ) -> Optional[str]:
        """Retrieve generated FlexQuery report."""
        url = f"{self.base_url}/GetStatement"
        params = {"t": self.token, "q": reference_code, "v": "3"}
        if account_id:
            params["acct"] = account_id

        is_testing = (
            os.environ.get("AXIOMFOLIO_TESTING") == "1" or "pytest" in sys.modules
        )
        max_attempts = 2 if is_testing else 6  # keep runs fast in tests
        for attempt in range(max_attempts):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            content = await response.text()

                            # Treat plain IN_PROGRESS response as not ready
                            if content and content.strip().upper() == "IN_PROGRESS":
                                if is_testing:
                                    logger.info(
                                        "⏳ Report IN_PROGRESS (test mode) → returning None"
                                    )
                                    return None
                                await asyncio.sleep(10)
                                continue

                            # Check if it's XML error or actual report
                            if "FlexStatementResponse" in content:
                                # IBKR returns FlexStatementResponse when the
                                # report is still generating or the request had
                                # an error.  The real data comes back as
                                # FlexQueryResponse.
                                if is_testing:
                                    logger.info(
                                        "⏳ Report still processing (test mode) → returning None"
                                    )
                                    return None
                                else:
                                    logger.info(
                                        "⏳ Report still processing (attempt %d/%d)",
                                        attempt + 1,
                                        max_attempts,
                                    )
                                    await asyncio.sleep(10)
                                    continue
                            elif "FlexQueryResponse" in content:
                                logger.info("✅ Report ready (%d bytes)", len(content))
                                return content
                            else:
                                logger.warning(
                                    "Unexpected FlexQuery response (%d bytes): %.200s",
                                    len(content),
                                    content,
                                )
                                await asyncio.sleep(10)
                                continue
                        else:
                            logger.error(
                                f"❌ HTTP error getting report: {response.status}"
                            )

            except Exception as e:
                logger.error(f"❌ Error getting report: {e}")

            if attempt < max_attempts - 1:
                await asyncio.sleep(0.1 if is_testing else 10)

        logger.error("❌ Report timeout - try again later")
        return None

    def _parse_tax_lots(self, xml_data: str, account_id: str) -> List[Dict]:
        """Parse tax lots from FlexQuery Trades section - REAL COST BASIS VERSION."""
        try:
            root = ET.fromstring(xml_data)

            # Find Trades section - this has the REAL cost basis data
            trades_section = root.find(".//Trades")
            if trades_section is None:
                logger.error("❌ No Trades section found in FlexQuery")
                return []

            logger.info(f"✅ Found {len(trades_section)} trades in FlexQuery")

            filter_account = account_id
            if _is_placeholder_account(account_id):
                for trade in trades_section:
                    aid = trade.get("accountId", "")
                    if aid:
                        filter_account = aid
                        break
                if not filter_account:
                    flex_stmt = root.find(".//FlexStatements/FlexStatement")
                    if flex_stmt is not None:
                        filter_account = flex_stmt.get("accountId", "") or ""

            # Reconstruct cost basis from actual trading history
            positions = {}  # symbol -> {quantity, total_cost, lots: []}

            # Process trades chronologically to build tax lots
            for trade in trades_section:
                # Filter by account
                trade_account = trade.get("accountId", "")
                if filter_account and trade_account != filter_account:
                    continue

                symbol = trade.get("symbol", "")
                if not symbol:
                    continue

                try:
                    quantity = float(trade.get("quantity", "0"))
                    trade_price = float(trade.get("tradePrice", "0"))
                    trade_date = trade.get("tradeDate", "")
                    trade_id = trade.get("tradeID", "")
                    asset_category = trade.get(
                        "assetCategory", "STK"
                    )  # CRITICAL: Get actual asset type

                    # CRITICAL FIX: Skip aggregated trades with "MULTI" dates
                    # These represent aggregated positions that duplicate individual trades
                    if trade_date == "MULTI" or trade_date == "":
                        logger.debug(
                            f"⚠️  Skipping aggregated trade: {symbol} {quantity} shares (date: {trade_date})"
                        )
                        continue

                    # CRITICAL FIX: Skip trades with empty tradeID
                    # FlexQuery often returns duplicate trades - one with empty ID and one with real ID
                    # The one with real ID is the authoritative record
                    if not trade_id or trade_id.strip() == "":
                        logger.debug(
                            f"⚠️  Skipping duplicate trade with empty ID: {symbol} {quantity} shares on {trade_date}"
                        )
                        continue

                    if quantity == 0 or trade_price == 0:
                        continue

                    # Initialize symbol tracking
                    if symbol not in positions:
                        positions[symbol] = {
                            "total_quantity": 0,
                            "total_cost": 0,
                            "lots": [],  # List of individual purchase lots
                            "current_price": 0,  # Will get from OpenPositions
                            "asset_category": asset_category,  # Track asset type
                        }

                    if quantity > 0:  # BUY trade - add new tax lot
                        lot_cost = quantity * trade_price
                        tax_lot = {
                            "lot_id": f"REAL_{trade_account}_{symbol}_{trade_id}",
                            "symbol": symbol,
                            "quantity": quantity,
                            "cost_per_share": trade_price,
                            "cost_basis": lot_cost,
                            "acquisition_date": trade_date,
                            "trade_id": trade_id,
                            "remaining_quantity": quantity,  # Track remaining after sales
                        }
                        positions[symbol]["lots"].append(tax_lot)
                        positions[symbol]["total_quantity"] += quantity
                        positions[symbol]["total_cost"] += lot_cost

                    else:  # SELL trade - reduce tax lots using FIFO
                        sell_quantity = abs(quantity)
                        remaining_to_sell = sell_quantity

                        # Apply FIFO to existing lots
                        for lot in positions[symbol]["lots"]:
                            if remaining_to_sell <= 0:
                                break

                            if lot["remaining_quantity"] > 0:
                                quantity_from_lot = min(
                                    lot["remaining_quantity"], remaining_to_sell
                                )
                                lot["remaining_quantity"] -= quantity_from_lot
                                remaining_to_sell -= quantity_from_lot

                                # Update positions totals
                                cost_reduction = (
                                    quantity_from_lot * lot["cost_per_share"]
                                )
                                positions[symbol]["total_quantity"] -= quantity_from_lot
                                positions[symbol]["total_cost"] -= cost_reduction

                except (ValueError, TypeError):
                    continue

            # Get current prices from OpenPositions section
            open_positions = root.find(".//OpenPositions")
            current_prices = {}
            if open_positions is not None:
                for position in open_positions:
                    pos_symbol = position.get("symbol", "")
                    current_price = float(position.get("markPrice", "0"))
                    if pos_symbol and current_price > 0:
                        current_prices[pos_symbol] = current_price

            # Create final tax lot records for current positions
            tax_lots = []
            for symbol, position_data in positions.items():
                if position_data["total_quantity"] <= 0:
                    continue  # Skip sold positions

                current_price = current_prices.get(symbol, 0)

                # Create tax lots from remaining purchase lots
                for lot in position_data["lots"]:
                    if lot["remaining_quantity"] <= 0:
                        continue  # Skip fully sold lots

                    # Calculate values for remaining quantity
                    remaining_qty = lot["remaining_quantity"]
                    remaining_cost = remaining_qty * lot["cost_per_share"]
                    current_value = (
                        remaining_qty * current_price if current_price > 0 else 0
                    )
                    unrealized_pnl = current_value - remaining_cost
                    unrealized_pnl_pct = (
                        (unrealized_pnl / remaining_cost * 100)
                        if remaining_cost > 0
                        else 0
                    )

                    tax_lot = {
                        "lot_id": lot["lot_id"],
                        "account_id": filter_account or account_id,
                        "symbol": symbol,
                        "quantity": remaining_qty,
                        "cost_per_share": lot["cost_per_share"],
                        "cost_basis": remaining_cost,
                        "current_price": current_price,
                        "market_value": current_value,
                        "unrealized_pnl": unrealized_pnl,
                        "unrealized_pnl_pct": unrealized_pnl_pct,
                        "currency": "USD",
                        # Back-compat: downstream expects a contract_type field
                        # (STK/OPT/etc). For reconstructed equity lots, map to asset_category.
                        "contract_type": position_data["asset_category"],
                        "asset_category": position_data[
                            "asset_category"
                        ],  # Use actual asset type
                        "source": "ibkr_trades_reconstructed",
                        "acquisition_date": lot["acquisition_date"],
                        "trade_id": lot["trade_id"],
                        "last_updated": datetime.now().isoformat(),
                    }

                    tax_lots.append(tax_lot)

            logger.info(
                f"✅ Reconstructed {len(tax_lots)} real tax lots from {len(trades_section)} trades"
            )
            return tax_lots

        except Exception as e:
            logger.error(f"❌ Error parsing trades for tax lots: {e}")
            import traceback

            traceback.print_exc()
            return []

    def _parse_option_positions(self, xml_data: str, account_id: str) -> List[Dict]:
        """Parse option positions from FlexQuery OpenPositions section."""
        try:
            root = ET.fromstring(xml_data)
            option_positions = []

            # Find OpenPositions section
            open_positions_section = root.find(".//OpenPositions")
            if open_positions_section is None:
                logger.warning("No OpenPositions section found in FlexQuery XML")
                return []

            logger.info(
                f"📊 Found {len(open_positions_section)} open positions in FlexQuery"
            )

            filter_account = account_id
            if _is_placeholder_account(account_id):
                for pos in open_positions_section:
                    aid = pos.get("accountId", "")
                    if aid:
                        filter_account = aid
                        break

            for position in open_positions_section:
                try:
                    # Filter by account
                    pos_account = position.get("accountId", "")
                    if filter_account and pos_account != filter_account:
                        continue

                    # Only process SUMMARY-level option positions (skip LOT rows)
                    asset_category = position.get("assetCategory") or position.get("assetClass") or ""
                    if asset_category != "OPT":
                        continue

                    level = (position.get("levelOfDetail") or "").upper()
                    if level and level != "SUMMARY":
                        continue

                    symbol = position.get("symbol", "")
                    if not symbol:
                        continue

                    # Parse option-specific fields
                    underlying_symbol = position.get("underlyingSymbol", "")
                    strike_price = float(position.get("strike", "0") or 0)
                    expiry_date = position.get("expiry", "")
                    option_type = position.get("putCall", "")  # 'P' or 'C'
                    multiplier = float(position.get("multiplier", "100") or 100)

                    # Position data
                    qty_attr = position.get("position")
                    if qty_attr is None:
                        qty_attr = position.get("quantity")
                    quantity = float(qty_attr or 0)
                    market_price = float(position.get("markPrice", "0") or 0)
                    market_value = float(position.get("positionValue", "0") or position.get("marketValue", "0") or 0)
                    unrealized_pnl = float(position.get("unrealizedPnl", "0") or position.get("fifoPnlUnrealized", "0") or 0)

                    # Parse expiry date
                    try:
                        expiry_datetime = (
                            datetime.strptime(expiry_date, "%Y%m%d")
                            if expiry_date
                            else None
                        )
                    except ValueError:
                        expiry_datetime = None

                    option_position = {
                        "account_id": filter_account or account_id,
                        "symbol": symbol,
                        "underlying_symbol": underlying_symbol,
                        "strike_price": strike_price,
                        "expiry_date": expiry_datetime,
                        "option_type": "CALL" if option_type.upper() == "C" else "PUT",
                        "multiplier": multiplier,
                        "open_quantity": abs(int(quantity)),  # Convert to integer for contracts
                        "current_price": market_price,
                        "market_value": market_value,
                        "unrealized_pnl": unrealized_pnl,
                        "currency": position.get("currency", "USD"),
                        "data_source": "ibkr_flexquery",
                    }

                    option_positions.append(option_position)

                except (ValueError, TypeError) as e:
                    logger.error(f"Error parsing option position: {e}")
                    continue

            logger.info(
                f"✅ Parsed {len(option_positions)} option positions from FlexQuery"
            )
            return option_positions

        except Exception as e:
            logger.error(f"❌ Error parsing option positions: {e}")
            import traceback

            traceback.print_exc()
            return []

    def _parse_stock_positions(self, xml_data: str, account_id: str) -> List[Dict]:
        """Parse stock/ETF positions from FlexQuery OpenPositions (SUMMARY level)."""
        try:
            root = ET.fromstring(xml_data)
            positions: List[Dict] = []

            section = root.find(".//OpenPositions")
            if section is None:
                return []

            filter_account = account_id
            if _is_placeholder_account(account_id):
                for pos in section:
                    aid = pos.get("accountId", "")
                    if aid:
                        filter_account = aid
                        break

            for pos in section:
                try:
                    pos_account = pos.get("accountId", "")
                    if filter_account and pos_account != filter_account:
                        continue

                    cat = (pos.get("assetCategory") or "").upper()
                    if cat not in ("STK", "ETF"):
                        continue

                    level = (pos.get("levelOfDetail") or "").upper()
                    if level != "SUMMARY":
                        continue

                    symbol = pos.get("symbol", "")
                    if not symbol:
                        continue

                    quantity = float(pos.get("position", "0") or 0)
                    if quantity == 0:
                        continue

                    positions.append({
                        "symbol": symbol,
                        "description": pos.get("description", ""),
                        "quantity": quantity,
                        "cost_basis_price": float(pos.get("costBasisPrice", "0") or 0),
                        "cost_basis_money": float(pos.get("costBasisMoney", "0") or 0),
                        "mark_price": float(pos.get("markPrice", "0") or 0),
                        "market_value": float(pos.get("positionValue", "0") or 0),
                        "unrealized_pnl": float(pos.get("fifoPnlUnrealized", "0") or 0),
                        "pct_of_nav": pos.get("percentOfNAV", ""),
                        "currency": pos.get("currency", "USD"),
                        "asset_category": cat,
                        "side": pos.get("side", "Long"),
                    })
                except (ValueError, TypeError):
                    continue

            logger.info("Parsed %d stock/ETF positions from OpenPositions", len(positions))
            return positions

        except Exception as e:
            logger.error("Error parsing stock positions: %s", e)
            return []

    def _parse_option_exercises(self, xml_data: str, account_id: str) -> List[Dict]:
        """Parse historical option exercises/assignments from FlexQuery OptionEAE section."""
        try:
            root = ET.fromstring(xml_data)
            option_exercises = []

            # Find OptionEAE section (Exercise, Assignment, Expiration)
            option_eae_section = root.find(".//OptionEAE")
            if option_eae_section is None:
                logger.warning("No OptionEAE section found in FlexQuery XML")
                return []

            logger.info(
                f"📊 Found {len(option_eae_section)} option exercises/assignments in FlexQuery"
            )

            filter_account = account_id
            if _is_placeholder_account(account_id):
                for ex in option_eae_section:
                    aid = ex.get("accountId", "")
                    if aid:
                        filter_account = aid
                        break

            for exercise in option_eae_section:
                try:
                    # Filter by account
                    exercise_account = exercise.get("accountId", "")
                    if filter_account and exercise_account != filter_account:
                        continue

                    symbol = exercise.get("symbol", "")
                    if not symbol:
                        continue

                    # Parse option exercise/assignment data
                    underlying_symbol = exercise.get("underlyingSymbol", "")
                    strike_price = float(exercise.get("strike", "0"))
                    expiry_date = exercise.get("expiry", "")
                    option_type = exercise.get("putCall", "")  # 'P' or 'C'
                    multiplier = float(exercise.get("multiplier", "100"))

                    # Exercise/Assignment details
                    exercised_quantity = int(
                        float(exercise.get("exercisedQuantity", "0"))
                    )
                    assigned_quantity = int(
                        float(exercise.get("assignedQuantity", "0"))
                    )
                    exercise_date = exercise.get("exerciseDate", "")
                    exercise_price = float(exercise.get("exercisePrice", "0"))
                    assignment_date = exercise.get("assignmentDate", "")

                    # Financial details
                    proceeds = float(exercise.get("proceeds", "0"))
                    commission = float(exercise.get("commission", "0"))

                    # Parse dates
                    try:
                        expiry_datetime = (
                            datetime.strptime(expiry_date, "%Y%m%d")
                            if expiry_date
                            else None
                        )
                    except ValueError:
                        expiry_datetime = None

                    try:
                        exercise_datetime = (
                            datetime.strptime(exercise_date, "%Y%m%d")
                            if exercise_date
                            else None
                        )
                    except ValueError:
                        exercise_datetime = None

                    try:
                        assignment_datetime = (
                            datetime.strptime(assignment_date, "%Y%m%d")
                            if assignment_date
                            else None
                        )
                    except ValueError:
                        assignment_datetime = None

                    # Determine total quantity (exercised or assigned)
                    total_quantity = exercised_quantity + assigned_quantity

                    option_exercise = {
                        "account_id": filter_account or account_id,
                        "symbol": symbol,
                        "underlying_symbol": underlying_symbol,
                        "strike_price": strike_price,
                        "expiry_date": expiry_datetime,
                        "option_type": "CALL" if option_type.upper() == "C" else "PUT",
                        "multiplier": multiplier,
                        "exercised_quantity": exercised_quantity,
                        "assigned_quantity": assigned_quantity,
                        "open_quantity": total_quantity,  # Total contracts affected
                        "exercise_date": exercise_datetime,
                        "exercise_price": exercise_price,
                        "assignment_date": assignment_datetime,
                        "proceeds": proceeds,
                        "commission": commission,
                        "currency": exercise.get("currency", "USD"),
                        "data_source": "ibkr_flexquery_eae",
                        "realized_pnl": proceeds - commission,  # Calculate realized P&L
                    }

                    option_exercises.append(option_exercise)

                except (ValueError, TypeError) as e:
                    logger.error(f"Error parsing option exercise: {e}")
                    continue

            logger.info(
                f"✅ Parsed {len(option_exercises)} option exercises from FlexQuery OptionEAE"
            )
            return option_exercises

        except Exception as e:
            logger.error(f"❌ Error parsing option exercises: {e}")
            import traceback

            traceback.print_exc()
            return []

    def _parse_enhanced_instruments(self, xml_data: str, account_id: str) -> List[Dict]:
        """Parse comprehensive instrument data from all FlexQuery sections."""
        try:
            root = ET.fromstring(xml_data)
            instruments = {}  # symbol -> instrument_data

            logger.info("📊 Parsing enhanced instruments from all FlexQuery sections")

            # Find all sections that contain instrument data
            flex_statements = root.find(".//FlexStatements")
            if flex_statements is None:
                logger.warning("No FlexStatements found")
                return []

            for statement in flex_statements:
                statement_account = statement.get("accountId", "")
                if account_id and not _is_placeholder_account(account_id) and statement_account != account_id:
                    continue

                # 1. Parse from OpenPositions (current holdings)
                open_positions = statement.find("OpenPositions")
                if open_positions is not None:
                    for position in open_positions:
                        symbol = position.get("symbol", "")
                        if not symbol:
                            continue

                        asset_category = position.get("assetCategory", "STK")

                        instrument_data = {
                            "symbol": symbol,
                            "name": position.get("description", symbol),
                            "asset_category": asset_category,
                            "currency": position.get("currency", "USD"),
                            "exchange": position.get("listingExchange", "UNKNOWN"),
                            "data_source": "ibkr_flexquery_positions",
                        }

                        # Option-specific data
                        if asset_category == "OPT":
                            instrument_data.update(
                                {
                                    "underlying_symbol": position.get(
                                        "underlyingSymbol", ""
                                    ),
                                    "option_type": (
                                        "CALL"
                                        if position.get("putCall") == "C"
                                        else "PUT"
                                    ),
                                    "strike_price": float(position.get("strike", 0)),
                                    "expiry_date": self._parse_flexquery_date(
                                        position.get("expiry")
                                    ),
                                    "multiplier": float(
                                        position.get("multiplier", 100)
                                    ),
                                }
                            )

                        instruments[symbol] = instrument_data

                # 2. Parse from Trades (historical instruments)
                trades = statement.find("Trades")
                if trades is not None:
                    for trade in trades:
                        symbol = trade.get("symbol", "")
                        if not symbol:
                            continue

                        asset_category = trade.get("assetCategory", "STK")

                        # Only add if not already exists or enhance existing
                        if symbol not in instruments:
                            instrument_data = {
                                "symbol": symbol,
                                "name": trade.get("description", symbol),
                                "asset_category": asset_category,
                                "currency": trade.get("currency", "USD"),
                                "exchange": trade.get("exchange", "UNKNOWN"),
                                "data_source": "ibkr_flexquery_trades",
                            }

                            # Option-specific data from trades
                            if asset_category == "OPT":
                                instrument_data.update(
                                    {
                                        "underlying_symbol": trade.get(
                                            "underlyingSymbol", ""
                                        ),
                                        "option_type": (
                                            "CALL"
                                            if trade.get("putCall") == "C"
                                            else "PUT"
                                        ),
                                        "strike_price": float(trade.get("strike", 0)),
                                        "expiry_date": self._parse_flexquery_date(
                                            trade.get("expiry")
                                        ),
                                        "multiplier": float(
                                            trade.get("multiplier", 100)
                                        ),
                                    }
                                )

                            instruments[symbol] = instrument_data
                        else:
                            # Enhance existing with trade data
                            existing = instruments[symbol]
                            if existing.get("name") == existing.get("symbol"):
                                existing["name"] = trade.get(
                                    "description", existing["name"]
                                )
                            if existing.get("exchange") == "UNKNOWN":
                                existing["exchange"] = trade.get("exchange", "UNKNOWN")

                # 3. Parse from OptionEAE (option exercises for option instruments)
                option_eae = statement.find("OptionEAE")
                if option_eae is not None:
                    for exercise in option_eae:
                        symbol = exercise.get("symbol", "")
                        if not symbol:
                            continue

                        if symbol not in instruments:
                            instrument_data = {
                                "symbol": symbol,
                                "name": symbol,  # Usually no description in OptionEAE
                                "asset_category": "OPT",
                                "currency": exercise.get("currency", "USD"),
                                "exchange": "CBOE",  # Default for options
                                "underlying_symbol": exercise.get(
                                    "underlyingSymbol", ""
                                ),
                                "option_type": (
                                    "CALL" if exercise.get("putCall") == "C" else "PUT"
                                ),
                                "strike_price": float(exercise.get("strike", 0)),
                                "expiry_date": self._parse_flexquery_date(
                                    exercise.get("expiry")
                                ),
                                "multiplier": float(exercise.get("multiplier", 100)),
                                "data_source": "ibkr_flexquery_exercises",
                            }

                            instruments[symbol] = instrument_data

                # 4. Parse from CashTransactions (dividend-paying instruments)
                cash_transactions = statement.find("CashTransactions")
                if cash_transactions is not None:
                    for transaction in cash_transactions:
                        symbol = transaction.get("symbol", "")
                        tx_type = transaction.get("type", "")

                        if symbol and tx_type in [
                            "Dividends",
                            "Payment In Lieu Of Dividend",
                        ]:
                            if symbol not in instruments:
                                instrument_data = {
                                    "symbol": symbol,
                                    "name": transaction.get("description", symbol),
                                    "asset_category": "STK",  # Dividend-paying stocks
                                    "currency": transaction.get("currency", "USD"),
                                    "exchange": "UNKNOWN",
                                    "data_source": "ibkr_flexquery_dividends",
                                    "pays_dividends": True,
                                }

                                instruments[symbol] = instrument_data
                            else:
                                # Mark existing as dividend-paying
                                instruments[symbol]["pays_dividends"] = True

            # Convert to list and add enhanced data
            result = []
            for symbol, data in instruments.items():
                # Skip invalid symbols (dividend descriptions, cash transactions, etc.)
                if not symbol or len(symbol) > 20:
                    continue
                if "DIVIDEND" in symbol.upper() or "CASH" in symbol.upper():
                    continue
                if symbol.startswith("(") or symbol.endswith(")"):
                    continue

                # Determine instrument type
                asset_cat = data.get("asset_category", "STK")
                if asset_cat == "OPT":
                    instrument_type = "OPTION"
                elif asset_cat == "STK":
                    instrument_type = "STOCK"
                elif asset_cat == "BOND":
                    instrument_type = "BOND"
                elif asset_cat == "FUT":
                    instrument_type = "FUTURE"
                elif asset_cat == "CASH":
                    instrument_type = "CASH"
                else:
                    instrument_type = "OTHER"

                # Map exchange names to valid enum values (NASDAQ, NYSE, CBOE only)
                exchange = data.get("exchange", "UNKNOWN")
                if exchange in ["NASDAQ"]:
                    mapped_exchange = "NASDAQ"
                elif exchange in ["NYSE", "AMEX", "ARCA"]:
                    mapped_exchange = "NYSE"  # Map ARCA and AMEX to NYSE
                elif exchange in ["CBOE", "PHLX", "ISE", "BOX"]:
                    mapped_exchange = "CBOE"  # Options exchanges
                else:
                    mapped_exchange = "NASDAQ"  # Default fallback

                enhanced_instrument = {
                    "symbol": symbol[:20] if symbol else "UNKNOWN",  # Max 20 chars
                    "name": (
                        data.get("name", symbol)[:200]
                        if data.get("name")
                        else symbol[:200]
                    ),  # Max 200 chars
                    "instrument_type": instrument_type,
                    "exchange": mapped_exchange,
                    "currency": data.get("currency", "USD")[:3],  # Max 3 chars
                    "underlying_symbol": (
                        data.get("underlying_symbol", "")[:20]
                        if data.get("underlying_symbol")
                        else None
                    ),  # Max 20 chars
                    "option_type": (
                        data.get("option_type", "")[:4]
                        if data.get("option_type")
                        else None
                    ),  # Max 4 chars
                    "strike_price": data.get("strike_price"),
                    "expiry_date": data.get("expiry_date"),
                    "multiplier": data.get(
                        "multiplier", 1 if instrument_type == "STOCK" else 100
                    ),
                    "pays_dividends": data.get("pays_dividends", False),
                    "data_source": data.get("data_source", "ibkr_flexquery")[
                        :50
                    ],  # Max 50 chars
                    "is_active": True,
                    "is_tradeable": True,
                }

                result.append(enhanced_instrument)

            logger.info(f"✅ Parsed {len(result)} enhanced instruments from FlexQuery")
            return result

        except Exception as e:
            logger.error(f"❌ Error parsing enhanced instruments: {e}")
            import traceback

            traceback.print_exc()
            return []

    def get_setup_instructions(self) -> Dict[str, str]:
        """Get setup instructions for FlexQuery configuration."""
        return {
            "step_1": "Go to IBKR Client Portal > Reports > Flex Queries",
            "step_2": "Create new Activity Flex Query with these sections: Open Positions, Account Information",
            "step_3": "Set Format=XML, Period=Today, Include all fields",
            "step_4": "Go to Flex Web Service Configuration and enable it",
            "step_5": "Generate token (valid 6hrs-1year) and note Query ID",
            "step_6": "Set env vars IBKR_FLEX_TOKEN and IBKR_FLEX_QUERY_ID (or provide per-user via UI)",
            "note": "FlexQuery provides OFFICIAL IBKR tax lot data used in Tax Optimizer",
        }

    def _parse_trades_from_xml(self, xml_data: str, account_id: str) -> List[Dict]:
        """Parse historical trades from FlexQuery XML for trade records."""
        try:
            root = ET.fromstring(xml_data)
            trades = []

            # Find Trades section
            trades_section = root.find(".//Trades")
            if trades_section is None:
                logger.warning("No Trades section found in FlexQuery XML")
                return []

            for trade in trades_section:
                try:
                    symbol = trade.get("symbol", "")
                    if not symbol:
                        continue

                    # Parse trade data
                    trade_data = {
                        "symbol": symbol,
                        "side": "BUY" if trade.get("buySell") == "BUY" else "SELL",
                        "quantity": abs(float(trade.get("quantity", 0))),
                        "price": float(trade.get("tradePrice", 0)),
                        "total_value": abs(float(trade.get("proceeds", 0))),
                        "commission": abs(float(trade.get("ibCommission", 0))),
                        "execution_id": trade.get("tradeID"),
                        "execution_time": self._parse_flexquery_date(
                            trade.get("tradeDate")
                        ),
                        "currency": trade.get("currency", "USD"),
                        "exchange": trade.get("exchange", ""),
                        "contract_type": trade.get("assetCategory", "STK"),
                    }

                    trades.append(trade_data)

                except (ValueError, TypeError) as e:
                    logger.error(f"Error parsing trade: {e}")
                    continue

            logger.info(f"✅ Parsed {len(trades)} historical trades from FlexQuery")
            return trades

        except ET.ParseError as e:
            logger.error(f"XML parsing error in trades: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing trades from XML: {e}")
            return []

    def _parse_flexquery_date(self, date_str: str) -> Optional[datetime]:
        """Parse FlexQuery date string to datetime object."""
        if not date_str:
            return None

        # Handle special IBKR values
        if date_str == "MULTI":
            # IBKR uses "MULTI" for aggregated positions with multiple acquisition dates
            return None

        try:
            # FlexQuery dates are typically in format: YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, or YYYYMMDD
            if len(date_str) == 8:  # YYYYMMDD (common in FlexQuery)
                return datetime.strptime(date_str, "%Y%m%d")
            elif len(date_str) == 10:  # YYYY-MM-DD
                return datetime.strptime(date_str, "%Y-%m-%d")
            elif len(date_str) == 19:  # YYYY-MM-DD HH:MM:SS
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            else:
                logger.warning(f"Unknown date format: {date_str}")
                return None  # Return None instead of current time for unknown formats
        except ValueError as e:
            logger.error(f"Error parsing date '{date_str}': {e}")
            return None  # Return None instead of current time for errors

    def _parse_cash_transactions(self, xml_data: str, account_id: str) -> List[Dict]:
        """Parse cash transactions including dividends from FlexQuery CashTransactions section."""
        try:
            root = ET.fromstring(xml_data)
            cash_transactions = []

            logger.info(
                "📊 Parsing cash transactions from FlexQuery CashTransactions section"
            )

            flex_statements = root.find(".//FlexStatements")
            if flex_statements is None:
                logger.warning("No FlexStatements found")
                return []

            for statement in flex_statements:
                statement_account = statement.get("accountId", "")
                if account_id and not _is_placeholder_account(account_id) and statement_account != account_id:
                    continue

                cash_tx_section = statement.find("CashTransactions")
                if cash_tx_section is not None:
                    for tx in cash_tx_section:
                        try:
                            tx_type = tx.get("type", "")
                            symbol = tx.get("symbol", "")

                            transaction_data = {
                                "account_id": account_id,
                                "external_id": tx.get("transactionID", ""),
                                "trade_id": tx.get("tradeID", ""),
                                "order_id": tx.get("orderID", ""),
                                "execution_id": tx.get("executionID", ""),
                                "symbol": symbol,
                                "description": tx.get("description", ""),
                                "conid": tx.get("conid", ""),
                                "security_id": tx.get("securityID", ""),
                                "cusip": tx.get("cusip", ""),
                                "isin": tx.get("isin", ""),
                                "listing_exchange": tx.get("listingExchange", ""),
                                "underlying_conid": tx.get("underlyingConid", ""),
                                "underlying_symbol": tx.get("underlyingSymbol", ""),
                                "multiplier": float(tx.get("multiplier", 1)),
                                "strike_price": (
                                    float(tx.get("strike", 0))
                                    if tx.get("strike")
                                    else None
                                ),
                                "expiry_date": (
                                    self._parse_flexquery_date(tx.get("expiry"))
                                    if tx.get("expiry")
                                    else None
                                ),
                                "option_type": (
                                    "CALL"
                                    if tx.get("putCall") == "C"
                                    else "PUT" if tx.get("putCall") == "P" else None
                                ),
                                "transaction_type": tx_type,
                                "action": tx.get("buySell", ""),
                                "quantity": float(tx.get("quantity", 0)),
                                "trade_price": (
                                    float(tx.get("tradePrice", 0))
                                    if tx.get("tradePrice")
                                    else None
                                ),
                                "amount": float(tx.get("amount", 0)),
                                "proceeds": (
                                    float(tx.get("proceeds", 0))
                                    if tx.get("proceeds")
                                    else None
                                ),
                                "commission": float(tx.get("commission", 0)),
                                "brokerage_commission": (
                                    float(tx.get("brokerageCommission", 0))
                                    if tx.get("brokerageCommission")
                                    else None
                                ),
                                "clearing_commission": (
                                    float(tx.get("clearingCommission", 0))
                                    if tx.get("clearingCommission")
                                    else None
                                ),
                                "third_party_commission": (
                                    float(tx.get("thirdPartyCommission", 0))
                                    if tx.get("thirdPartyCommission")
                                    else None
                                ),
                                "other_fees": (
                                    float(tx.get("otherFees", 0))
                                    if tx.get("otherFees")
                                    else None
                                ),
                                "net_amount": float(tx.get("netCash", 0)),
                                "currency": tx.get("currency", "USD"),
                                "fx_rate_to_base": float(tx.get("fxRateToBase", 1)),
                                "asset_category": tx.get("assetCategory", ""),
                                "sub_category": tx.get("subCategory", ""),
                                "transaction_date": self._parse_flexquery_date(
                                    tx.get("dateTime")
                                ),
                                "trade_date": self._parse_flexquery_date(
                                    tx.get("tradeDate")
                                ),
                                "settlement_date_target": self._parse_flexquery_date(
                                    tx.get("settleDateTarget")
                                ),
                                "settlement_date": self._parse_flexquery_date(
                                    tx.get("settleDate")
                                ),
                                "taxes": (
                                    float(tx.get("taxes", 0))
                                    if tx.get("taxes")
                                    else None
                                ),
                                "taxable_amount": (
                                    float(tx.get("taxableAmount", 0))
                                    if tx.get("taxableAmount")
                                    else None
                                ),
                                "taxable_amount_base": (
                                    float(tx.get("taxableAmountInBase", 0))
                                    if tx.get("taxableAmountInBase")
                                    else None
                                ),
                                "corporate_action_flag": tx.get(
                                    "corporateActionFlag", ""
                                ),
                                "corporate_action_id": tx.get("corporateActionID", ""),
                                "source": "ibkr_flexquery_cash",
                                "data_source": "ibkr_flexquery",
                            }

                            cash_transactions.append(transaction_data)

                        except Exception as e:
                            logger.error(f"Error parsing cash transaction: {e}")
                            continue

            logger.info(
                f"✅ Parsed {len(cash_transactions)} cash transactions from FlexQuery"
            )
            return cash_transactions

        except Exception as e:
            logger.error(f"❌ Error parsing cash transactions: {e}")
            import traceback

            traceback.print_exc()
            return []

    def _parse_account_information(self, xml_data: str, account_id: str) -> List[Dict]:
        """Parse account balances from FlexQuery AccountInformation section."""
        try:
            root = ET.fromstring(xml_data)
            account_balances = []

            logger.info(
                "📊 Parsing account information from FlexQuery AccountInformation section"
            )

            flex_statements = root.find(".//FlexStatements")
            if flex_statements is None:
                logger.warning("No FlexStatements found")
                return []

            for statement in flex_statements:
                statement_account = statement.get("accountId", "")
                if account_id and not _is_placeholder_account(account_id) and statement_account != account_id:
                    continue

                # Get account info from statement attributes
                from_date = statement.get("fromDate", "")
                to_date = statement.get("toDate", "")

                account_info_section = statement.find("AccountInformation")
                if account_info_section is not None:
                    for info in account_info_section:
                        try:
                            balance_data = {
                                "broker_account_id": None,  # Will be set by sync service
                                "balance_date": (
                                    self._parse_flexquery_date(to_date)
                                    if to_date
                                    else datetime.now().date()
                                ),
                                "balance_type": "DAILY_SNAPSHOT",
                                "base_currency": info.get("baseCurrency", "USD"),
                                "total_cash_value": float(
                                    info.get("totalCashValue", 0)
                                ),
                                "settled_cash": (
                                    float(info.get("settledCash", 0))
                                    if info.get("settledCash")
                                    else None
                                ),
                                "available_funds": (
                                    float(info.get("availableFunds", 0))
                                    if info.get("availableFunds")
                                    else None
                                ),
                                "cash_balance": (
                                    float(info.get("cashBalance", 0))
                                    if info.get("cashBalance")
                                    else None
                                ),
                                "net_liquidation": (
                                    float(info.get("netLiquidation", 0))
                                    if info.get("netLiquidation")
                                    else None
                                ),
                                "gross_position_value": (
                                    float(info.get("grossPositionValue", 0))
                                    if info.get("grossPositionValue")
                                    else None
                                ),
                                "equity": (
                                    float(info.get("equity", 0))
                                    if info.get("equity")
                                    else None
                                ),
                                "previous_day_equity": (
                                    float(info.get("previousDayEquity", 0))
                                    if info.get("previousDayEquity")
                                    else None
                                ),
                                "buying_power": (
                                    float(info.get("buyingPower", 0))
                                    if info.get("buyingPower")
                                    else None
                                ),
                                "initial_margin_req": (
                                    float(info.get("initialMarginReq", 0))
                                    if info.get("initialMarginReq")
                                    else None
                                ),
                                "maintenance_margin_req": (
                                    float(info.get("maintMarginReq", 0))
                                    if info.get("maintMarginReq")
                                    else None
                                ),
                                "reg_t_equity": (
                                    float(info.get("regTEquity", 0))
                                    if info.get("regTEquity")
                                    else None
                                ),
                                "sma": (
                                    float(info.get("sma", 0))
                                    if info.get("sma")
                                    else None
                                ),
                                "unrealized_pnl": (
                                    float(info.get("unrealizedPnl", 0))
                                    if info.get("unrealizedPnl")
                                    else None
                                ),
                                "realized_pnl": (
                                    float(info.get("realizedPnl", 0))
                                    if info.get("realizedPnl")
                                    else None
                                ),
                                "daily_pnl": (
                                    float(info.get("dailyPnl", 0))
                                    if info.get("dailyPnl")
                                    else None
                                ),
                                "cushion": (
                                    float(info.get("cushion", 0))
                                    if info.get("cushion")
                                    else None
                                ),
                                "leverage": (
                                    float(info.get("leverage", 0))
                                    if info.get("leverage")
                                    else None
                                ),
                                "lookahead_next_change": (
                                    float(info.get("lookAheadNextChange", 0))
                                    if info.get("lookAheadNextChange")
                                    else None
                                ),
                                "lookahead_available_funds": (
                                    float(info.get("lookAheadAvailableFunds", 0))
                                    if info.get("lookAheadAvailableFunds")
                                    else None
                                ),
                                "lookahead_excess_liquidity": (
                                    float(info.get("lookAheadExcessLiquidity", 0))
                                    if info.get("lookAheadExcessLiquidity")
                                    else None
                                ),
                                "lookahead_init_margin": (
                                    float(info.get("lookAheadInitMargin", 0))
                                    if info.get("lookAheadInitMargin")
                                    else None
                                ),
                                "lookahead_maint_margin": (
                                    float(info.get("lookAheadMaintMargin", 0))
                                    if info.get("lookAheadMaintMargin")
                                    else None
                                ),
                                "accrued_cash": (
                                    float(info.get("accruedCash", 0))
                                    if info.get("accruedCash")
                                    else None
                                ),
                                "accrued_dividend": (
                                    float(info.get("accruedDividend", 0))
                                    if info.get("accruedDividend")
                                    else None
                                ),
                                "accrued_interest": (
                                    float(info.get("accruedInterest", 0))
                                    if info.get("accruedInterest")
                                    else None
                                ),
                                "exchange_rate": float(info.get("exchangeRate", 1)),
                                "data_source": "OFFICIAL_STATEMENT",
                                "account_alias": info.get("accountAlias", ""),
                                "customer_type": info.get("customerType", ""),
                                "account_code": info.get("accountCode", ""),
                                "account_id": account_id,
                            }

                            account_balances.append(balance_data)

                        except Exception as e:
                            logger.error(f"Error parsing account information: {e}")
                            continue

            logger.info(
                f"✅ Parsed {len(account_balances)} account balance records from FlexQuery"
            )
            return account_balances

        except Exception as e:
            logger.error(f"❌ Error parsing account information: {e}")
            import traceback

            traceback.print_exc()
            return []

    def _parse_interest_accruals(self, xml_data: str, account_id: str) -> List[Dict]:
        """Parse margin interest from FlexQuery InterestAccruals section."""
        try:
            root = ET.fromstring(xml_data)
            interest_accruals = []

            logger.info(
                "📊 Parsing interest accruals from FlexQuery InterestAccruals section"
            )

            flex_statements = root.find(".//FlexStatements")
            if flex_statements is None:
                logger.warning("No FlexStatements found")
                return []

            for statement in flex_statements:
                statement_account = statement.get("accountId", "")
                if account_id and not _is_placeholder_account(account_id) and statement_account != account_id:
                    continue

                interest_section = statement.find("InterestAccruals")
                if interest_section is not None:
                    for interest in interest_section:
                        try:
                            interest_data = {
                                "broker_account_id": None,  # Will be set by sync service
                                "account_alias": interest.get("accountAlias", ""),
                                "from_date": self._parse_flexquery_date(
                                    interest.get("fromDate")
                                ),
                                "to_date": self._parse_flexquery_date(
                                    interest.get("toDate")
                                ),
                                "starting_balance": float(
                                    interest.get("startingAccrualBalance", 0)
                                ),
                                "interest_accrued": float(
                                    interest.get("interestAccrued", 0)
                                ),
                                "accrual_reversal": (
                                    float(interest.get("accrualReversal", 0))
                                    if interest.get("accrualReversal")
                                    else None
                                ),
                                "ending_balance": float(
                                    interest.get("endingAccrualBalance", 0)
                                ),
                                "interest_rate": (
                                    float(interest.get("rate", 0))
                                    if interest.get("rate")
                                    else None
                                ),
                                "daily_rate": (
                                    float(interest.get("dailyRate", 0))
                                    if interest.get("dailyRate")
                                    else None
                                ),
                                "currency": interest.get("currency", "USD"),
                                "fx_rate_to_base": float(
                                    interest.get("fxRateToBase", 1)
                                ),
                                "interest_type": interest.get("type", "MARGIN"),
                                "description": interest.get("description", ""),
                                "data_source": "ibkr_flexquery_interest",
                                "account_id": account_id,
                            }

                            interest_accruals.append(interest_data)

                        except Exception as e:
                            logger.error(f"Error parsing interest accrual: {e}")
                            continue

            logger.info(
                f"✅ Parsed {len(interest_accruals)} interest accrual records from FlexQuery"
            )
            return interest_accruals

        except Exception as e:
            logger.error(f"❌ Error parsing interest accruals: {e}")
            import traceback

            traceback.print_exc()
            return []

    def _parse_transfers(self, xml_data: str, account_id: str) -> List[Dict]:
        """Parse transfers from FlexQuery Transfers section."""
        try:
            root = ET.fromstring(xml_data)
            transfers = []

            logger.info("📊 Parsing transfers from FlexQuery Transfers section")

            flex_statements = root.find(".//FlexStatements")
            if flex_statements is None:
                logger.warning("No FlexStatements found")
                return []

            for statement in flex_statements:
                statement_account = statement.get("accountId", "")
                if account_id and not _is_placeholder_account(account_id) and statement_account != account_id:
                    continue

                transfers_section = statement.find("Transfers")
                if transfers_section is not None:
                    for transfer in transfers_section:
                        try:
                            transfer_data = {
                                "broker_account_id": None,  # Will be set by sync service
                                "transaction_id": transfer.get("transactionID", ""),
                                "client_reference": transfer.get("clientReference", ""),
                                "transfer_date": self._parse_flexquery_date(
                                    transfer.get("date")
                                ),
                                "settle_date": self._parse_flexquery_date(
                                    transfer.get("settleDate")
                                ),
                                "transfer_type": transfer.get("type", ""),
                                "direction": transfer.get("direction", ""),
                                "symbol": transfer.get("symbol", ""),
                                "description": transfer.get("description", ""),
                                "contract_id": transfer.get("conid", ""),
                                "security_id": transfer.get("securityID", ""),
                                "security_id_type": transfer.get("securityIDType", ""),
                                "quantity": (
                                    float(transfer.get("quantity", 0))
                                    if transfer.get("quantity")
                                    else None
                                ),
                                "trade_price": (
                                    float(transfer.get("tradePrice", 0))
                                    if transfer.get("tradePrice")
                                    else None
                                ),
                                "transfer_price": (
                                    float(transfer.get("transferPrice", 0))
                                    if transfer.get("transferPrice")
                                    else None
                                ),
                                "amount": float(transfer.get("amount", 0)),
                                "cash_amount": (
                                    float(transfer.get("cashAmount", 0))
                                    if transfer.get("cashAmount")
                                    else None
                                ),
                                "net_cash": (
                                    float(transfer.get("netCash", 0))
                                    if transfer.get("netCash")
                                    else None
                                ),
                                "commission": (
                                    float(transfer.get("commission", 0))
                                    if transfer.get("commission")
                                    else None
                                ),
                                "currency": transfer.get("currency", "USD"),
                                "fx_rate_to_base": float(
                                    transfer.get("fxRateToBase", 1)
                                ),
                                "delivery_type": transfer.get("deliveryType", ""),
                                "account_alias": transfer.get("accountAlias", ""),
                                "model": transfer.get("model", ""),
                                "notes": transfer.get("notes", ""),
                                "external_reference": transfer.get(
                                    "externalReference", ""
                                ),
                                "data_source": "ibkr_flexquery_transfers",
                                "account_id": account_id,
                            }

                            transfers.append(transfer_data)

                        except Exception as e:
                            logger.error(f"Error parsing transfer: {e}")
                            continue

            logger.info(f"✅ Parsed {len(transfers)} transfer records from FlexQuery")
            return transfers

        except Exception as e:
            logger.error(f"❌ Error parsing transfers: {e}")
            import traceback

            traceback.print_exc()
            return []

    async def get_cash_transactions(self, account_id: str) -> List[Dict]:
        """Get cash transactions including dividends from FlexQuery."""
        try:
            raw_xml = await self.get_full_report(account_id)
            if not raw_xml:
                return []

            return self._parse_cash_transactions(raw_xml, account_id)

        except Exception as e:
            logger.error(f"❌ Error getting cash transactions: {e}")
            return []

    async def get_account_balances(self, account_id: str) -> List[Dict]:
        """Get account balance information from FlexQuery."""
        try:
            raw_xml = await self.get_full_report(account_id)
            if not raw_xml:
                return []

            return self._parse_account_information(raw_xml, account_id)

        except Exception as e:
            logger.error(f"❌ Error getting account balances: {e}")
            return []

    async def get_margin_interest(self, account_id: str) -> List[Dict]:
        """Get margin interest accruals from FlexQuery."""
        try:
            raw_xml = await self.get_full_report(account_id)
            if not raw_xml:
                return []

            return self._parse_interest_accruals(raw_xml, account_id)

        except Exception as e:
            logger.error(f"❌ Error getting margin interest: {e}")
            return []

    async def get_transfers(self, account_id: str) -> List[Dict]:
        """Get transfer records from FlexQuery."""
        try:
            raw_xml = await self.get_full_report(account_id)
            if not raw_xml:
                return []

            return self._parse_transfers(raw_xml, account_id)

        except Exception as e:
            logger.error(f"❌ Error getting transfers: {e}")
            return []


# Global instance
flexquery_client = IBKRFlexQueryClient()
