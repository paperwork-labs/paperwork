"""
IBKR Portfolio Sync Service
==========================

IBKR-specific sync service that syncs real IBKR data from both real-time API and FlexQuery 
to populate all database models with broker-agnostic data structures.

This service is IBKR-specific and handles:
- IBKR FlexQuery XML parsing
- IBKR real-time API data
- IBKR-specific data transformations

The data is transformed into broker-agnostic models that work with any broker.
"""

import logging
from typing import Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func as sa_func
from decimal import Decimal
import json

from backend.database import SessionLocal
from backend.models import Base
from backend.models import (
    # Portfolio models
    PortfolioSnapshot,
    # Trade & Tax models
    TaxLot,
    Trade,
    Transaction,
    # Market data models
    PriceData,
    # User model
    BrokerAccount,
)

# Import specific enums and models from their modules
from backend.models.position import Position, PositionType, PositionStatus
from backend.models.instrument import Instrument, InstrumentType, Exchange
from backend.models.tax_lot import TaxLotSource
from backend.models.options import Option
from backend.models.portfolio import PositionCategory

# Import the services we need
from backend.services.clients.ibkr_flexquery_client import IBKRFlexQueryClient
from backend.services.portfolio.account_credentials_service import (
    account_credentials_service,
    CredentialsNotFoundError,
)

logger = logging.getLogger(__name__)


def serialize_for_json(data):
    """Convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(data, dict):
        return {k: serialize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_for_json(item) for item in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    else:
        return data


class IBKRSyncService:
    """IBKR-specific service to sync all IBKR data to broker-agnostic database models."""

    def __init__(self):
        self._default_client = IBKRFlexQueryClient()
        # Backward compat: tests patch flexquery_client
        self.flexquery_client = self._default_client
        # NOTE: IBKRClient may need singleton pattern - will handle connection carefully
        # Account mapping removed - now retrieved dynamically from database/config

    def _get_flexquery_client(
        self, broker_account: BrokerAccount, db: Session
    ) -> IBKRFlexQueryClient:
        """Get FlexQuery client with per-account credentials or env fallback."""
        try:
            creds = account_credentials_service.get_ibkr_credentials(
                broker_account.id, db
            )
            return IBKRFlexQueryClient(
                token=creds["flex_token"],
                query_id=creds["query_id"],
            )
        except CredentialsNotFoundError:
            return self._default_client

    async def sync_comprehensive_portfolio(
        self, account_number: str = "U19491234", db_session: Session | None = None
    ) -> Dict:
        """
        MAIN METHOD: Comprehensive sync of all portfolio data.

        This populates ALL database models with real IBKR data:
        1. Instruments (securities master data)
        2. position (current positions aggregated by symbol)
        3. TaxLots (individual tax lots with REAL cost basis from trades)
        4. Trades (historical trade records from FlexQuery)
        5. PriceData (current market prices)
        6. Positions (detailed position data)
        7. PortfolioSnapshot (daily portfolio snapshot)
        """
        db = db_session or SessionLocal()
        results = {}

        try:
            logger.info(
                f"🚀 Starting comprehensive portfolio sync for {account_number}"
            )

            # Get broker account from database (using broker-agnostic model)
            try:
                broker_account = (
                    db.query(BrokerAccount)
                    .filter(BrokerAccount.account_number == account_number)
                    .first()
                )
            except Exception:
                return {"status": "error", "error": "Broker account not found in database"}
            if not broker_account:
                return {"status": "error", "error": "Broker account not found in database"}

            # Get FlexQuery client (per-account creds or env fallback)
            flexquery_client = self._get_flexquery_client(broker_account, db)

            # Fetch single FlexQuery report once to avoid IN_PROGRESS collisions
            report_xml = await flexquery_client.get_full_report(account_number)
            if not report_xml:
                logger.error("❌ FlexQuery report not ready")
                return {"status": "error", "error": "FlexQuery report not available — token or query ID may be invalid."}

            logger.debug(
                "FlexQuery report length=%d, preview (first 500 chars): %s",
                len(report_xml),
                report_xml[:500],
            )

            # Log all XML sections present in the report for debugging
            try:
                import xml.etree.ElementTree as _ET
                _root = _ET.fromstring(report_xml)
                for _stmt in _root.iter("FlexStatement"):
                    _sections = [child.tag for child in _stmt]
                    logger.info("FlexQuery sections for %s: %s", account_number, _sections)
            except Exception:
                pass

            # Step 1: Sync Instruments (securities master data)
            instruments_result = await self._sync_instruments(
                db, account_number, report_xml, flexquery_client
            )
            results["instruments"] = instruments_result

            # Step 2: Sync TaxLots with REAL cost basis from FlexQuery.
            # Prefer the client's canonical tax-lots endpoint over parsing the full report XML,
            # since report formats can vary and the client normalizes the structure.
            tax_lots_result = await self._sync_tax_lots_from_flexquery(
                db, broker_account, account_number, report_xml, flexquery_client
            )
            results["tax_lots"] = tax_lots_result
            logger.info(
                "Tax lots sync result for %s: %s",
                account_number,
                tax_lots_result,
            )

            # Step 3: Sync Option Positions from FlexQuery OpenPositions
            options_result = await self._sync_option_positions_from_flexquery(
                db, broker_account, account_number, report_xml, flexquery_client
            )
            results["option_positions"] = options_result

            # Step 4: Sync historical Trades from FlexQuery
            trades_result = await self._sync_trades_from_flexquery(
                db, broker_account, account_number, report_xml, flexquery_client
            )
            results["trades"] = trades_result
            # Step 5: Sync current Positions
            # Prefer tax-lot-derived positions; fall back to OpenPositions when
            # the Trades section is too sparse for full reconstruction.
            positions_result = await self._sync_position_from_tax_lots(
                db, broker_account
            )
            if isinstance(positions_result, dict) and positions_result.get("synced", 0) == 0:
                positions_result = await self._sync_positions_from_open_positions(
                    db, broker_account, account_number, report_xml, flexquery_client
                )
            results["positions"] = positions_result

            # Step 5.1: Refresh prices for positions and tax lots to populate market values
            try:
                price_refresh = await self._refresh_prices_for_account(db, broker_account)
                results["price_refresh"] = price_refresh
            except Exception as e:
                logger.warning(f"Price refresh skipped: {e}")

            # Step 6: Update Portfolio snapshots
            snapshot_result = await self._create_portfolio_snapshot(db, broker_account)
            results["snapshot"] = snapshot_result

            # Step 7: Sync detailed Positions (uses Broker Account)
            detailed_positions_result = await self._sync_positions_from_position(
                db, broker_account
            )
            results["detailed_positions"] = detailed_positions_result

            # Step 8: Sync cash transactions including dividends
            cash_transactions_result = await self._sync_cash_transactions(
                db, broker_account, account_number, report_xml, flexquery_client
            )
            results["cash_transactions"] = cash_transactions_result

            # Step 9: Sync account balances
            account_balances_result = await self._sync_account_balances(
                db, broker_account, account_number, report_xml, flexquery_client
            )
            results["account_balances"] = account_balances_result

            # Step 10: Sync margin interest
            margin_interest_result = await self._sync_margin_interest(
                db, broker_account, account_number, report_xml, flexquery_client
            )
            results["margin_interest"] = margin_interest_result

            # Step 11: Sync transfers
            transfers_result = await self._sync_transfers(
                db, broker_account, account_number, report_xml, flexquery_client
            )
            results["transfers"] = transfers_result

            # Step 12: Enrich option positions with live Greeks from IB Gateway
            greeks_result = await self._sync_option_greeks_from_gateway(
                db, broker_account
            )
            results["greeks_enrichment"] = greeks_result

            # Commit all changes
            db.commit()

            # Refresh activity materialized views so new data appears immediately
            try:
                from backend.services.portfolio.activity_aggregator import activity_aggregator
                activity_aggregator.refresh_materialized_views(db)
            except Exception as e:
                logger.warning("Activity MV refresh skipped: %s", e)

            # Detect empty FlexQuery report (all sections yielded 0 data)
            _data_keys = ["tax_lots", "trades", "positions", "cash_transactions", "account_balances"]
            _total_synced = sum(
                (r.get("synced", 0) if isinstance(r, dict) else 0)
                for k in _data_keys
                if (r := results.get(k)) is not None
            )
            if _total_synced == 0:
                error_msg = (
                    "FlexQuery report returned no data. "
                    "Verify your FlexQuery includes: Open Positions, Trades, "
                    "Cash Transactions, and Account Information sections. "
                    "Also confirm your Flex Web Service token has not expired."
                )
                logger.error("❌ %s (account %s)", error_msg, account_number)
                return {"status": "error", "error": error_msg, **results}

            # Calculate summary from tax lots; fall back to positions table
            total_cost = sum(
                float(lot.cost_basis or 0)
                for lot in db.query(TaxLot)
                .filter(TaxLot.account_id == broker_account.id)
                .all()
            )
            total_value = sum(
                float(lot.market_value or 0)
                for lot in db.query(TaxLot)
                .filter(TaxLot.account_id == broker_account.id)
                .all()
            )
            if total_cost == 0 and total_value == 0:
                total_cost = float(
                    db.query(
                        sa_func.coalesce(sa_func.sum(Position.total_cost_basis), 0)
                    )
                    .filter(Position.account_id == broker_account.id)
                    .scalar()
                    or 0
                )
                total_value = float(
                    db.query(
                        sa_func.coalesce(sa_func.sum(Position.market_value), 0)
                    )
                    .filter(Position.account_id == broker_account.id)
                    .scalar()
                    or 0
                )
            total_pnl = total_value - total_cost
            return_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

            results["summary"] = {
                "total_cost_basis": f"${total_cost:,.2f}",
                "total_market_value": f"${total_value:,.2f}",
                "unrealized_pnl": f"${total_pnl:,.2f}",
                "return_pct": f"{return_pct:.2f}%",
                "sync_timestamp": datetime.now().isoformat(),
            }

            logger.info("✅ Comprehensive portfolio sync completed successfully")
            return results

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Error in comprehensive sync: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            if db_session is None:
                db.close()

    async def sync_account_comprehensive(
        self, account_number: str, db_session=None
    ) -> Dict:
        """Adapter to align with broker-agnostic sync interface."""
        return await self.sync_comprehensive_portfolio(account_number, db_session=db_session)

    async def _sync_option_greeks_from_gateway(
        self, db: Session, broker_account
    ) -> Dict[str, int]:
        """Enrich open option positions with live Greeks from IB Gateway.
        Gracefully skips if Gateway is unreachable."""
        try:
            from backend.services.clients.ibkr_client import ibkr_client, IBKR_AVAILABLE
            if not IBKR_AVAILABLE or not ibkr_client.is_connected():
                logger.info("IB Gateway not connected — skipping Greeks enrichment")
                return {"greeks_enriched": 0, "status": "gateway_offline"}
        except Exception:
            return {"greeks_enriched": 0, "status": "import_error"}

        try:
            from ib_insync import Option as IBOption

            options = (
                db.query(Option)
                .filter(
                    Option.account_id == broker_account.id,
                    Option.open_quantity != 0,
                )
                .all()
            )

            if not options:
                return {"greeks_enriched": 0}

            contracts = []
            option_map = {}
            for opt in options:
                exp_str = opt.expiry_date.strftime("%Y%m%d") if opt.expiry_date else ""
                right = "C" if (opt.option_type or "").upper() in ("CALL", "C") else "P"
                sym = opt.underlying_symbol or opt.symbol
                contract = IBOption(sym, exp_str, float(opt.strike_price), right, "SMART")
                contracts.append(contract)
                option_map[f"{sym}_{exp_str}_{opt.strike_price}_{right}"] = opt

            greeks_data = await ibkr_client.get_option_greeks(contracts)

            enriched = 0
            for gd in greeks_data:
                key = f"{gd['symbol']}_{gd['expiry']}_{gd['strike']}_{gd['right']}"
                opt = option_map.get(key)
                if not opt:
                    continue
                if gd.get("delta") is not None:
                    opt.delta = gd["delta"]
                if gd.get("gamma") is not None:
                    opt.gamma = gd["gamma"]
                if gd.get("theta") is not None:
                    opt.theta = gd["theta"]
                if gd.get("vega") is not None:
                    opt.vega = gd["vega"]
                if gd.get("implied_volatility") is not None:
                    opt.implied_volatility = gd["implied_volatility"]
                if gd.get("last_price") is not None:
                    opt.current_price = gd["last_price"]
                enriched += 1

            db.flush()
            logger.info("Enriched %d/%d options with live Greeks", enriched, len(options))
            return {"greeks_enriched": enriched, "total_options": len(options)}

        except Exception as e:
            logger.warning("Greeks enrichment failed: %s", e)
            return {"greeks_enriched": 0, "error": str(e)}

    async def _sync_instruments(
        self,
        db: Session,
        account_number: str,
        report_xml: str | None = None,
        flexquery_client: IBKRFlexQueryClient | None = None,
    ) -> Dict:
        """Sync comprehensive instruments from all FlexQuery sections."""
        try:
            # Ensure tables exist during tests
            try:
                import os

                if (
                    os.environ.get("PYTEST_CURRENT_TEST")
                    or os.environ.get("AXIOMFOLIO_TESTING") == "1"
                ):
                    Base.metadata.create_all(bind=db.bind)
            except Exception:
                pass

            logger.info(f"📊 Syncing enhanced instruments for {account_number}")

            # Helper mappers for enums
            def _to_instrument_type(value: str) -> InstrumentType:
                mapping = {
                    "STK": InstrumentType.STOCK,
                    "OPT": InstrumentType.OPTION,
                    "ETF": InstrumentType.ETF,
                    "STOCK": InstrumentType.STOCK,
                    "OPTION": InstrumentType.OPTION,
                }
                if not value:
                    return InstrumentType.STOCK
                return mapping.get(str(value).upper(), InstrumentType.STOCK)

            def _to_exchange(value: str) -> Exchange | None:
                if not value:
                    return Exchange.NASDAQ
                v = str(value).lower()
                try:
                    return Exchange[v.upper()]  # e.g., NASDAQ
                except Exception:
                    # Common strings mapping
                    if v in ("nasdaq",):
                        return Exchange.NASDAQ
                    if v in ("nyse",):
                        return Exchange.NYSE
                    if v in ("cboe",):
                        return Exchange.CBOE
                    return Exchange.NASDAQ

            # Prefer tax lot symbols during tests (when patched) to keep deterministic
            fc = flexquery_client or self._default_client
            instruments_data = []
            lots = (
                await fc.get_official_tax_lots(account_number)
                if not report_xml
                else fc._parse_tax_lots(report_xml, account_number)
            )
            if lots:
                # Only create base instruments from STOCK/ETF tax lots; skip options/futures/etc.
                stock_symbols = sorted(
                    {
                        l.get("symbol")
                        for l in (lots or [])
                        if l.get("symbol")
                        and str(l.get("asset_category", "STK")).upper()
                        in {"STK", "ETF"}
                    }
                )
                instruments_data = [
                    {
                        "symbol": s[:100],
                        "name": s,
                        "instrument_type": "STOCK",
                        "exchange": "NASDAQ",
                        "currency": "USD",
                        "data_source": "ibkr_taxlots_fallback",
                    }
                    for s in stock_symbols
                ]
            else:
                # Fall back to FlexQuery enhanced parse
                try:
                    raw_xml = report_xml or await fc.get_full_report(account_number)
                    if raw_xml:
                        instruments_data = (
                            fc._parse_enhanced_instruments(raw_xml, account_number)
                            or []
                        )
                except Exception:
                    instruments_data = []

            if not instruments_data:
                logger.warning(f"No instrument data found for {account_number}")
                return {"synced": 0, "updated": 0}

            synced_count = 0
            updated_count = 0

            for inst_data in instruments_data:
                try:
                    symbol = (inst_data.get("symbol") or "").strip().upper()
                    if not symbol or len(symbol) > 100:  # Symbol length limit
                        continue

                    # Check if instrument already exists
                    existing = (
                        db.query(Instrument).filter(Instrument.symbol == symbol).first()
                    )

                    if existing:
                        # Update existing instrument with enhanced data
                        if inst_data.get("name"):
                            if not existing.name or existing.name.strip().upper() == existing.symbol.strip().upper():
                                existing.name = inst_data["name"]

                        if (
                            inst_data.get("exchange")
                            and inst_data["exchange"] != "UNKNOWN"
                        ):
                            existing.exchange = _to_exchange(inst_data["exchange"])

                        if inst_data.get("underlying_symbol"):
                            existing.underlying_symbol = inst_data["underlying_symbol"]

                        if inst_data.get("option_type"):
                            existing.option_type = inst_data["option_type"]

                        if inst_data.get("strike_price"):
                            existing.strike_price = inst_data["strike_price"]

                        if inst_data.get("expiry_date"):
                            existing.expiration_date = inst_data["expiry_date"]

                        if inst_data.get("multiplier"):
                            existing.multiplier = inst_data["multiplier"]

                        existing.last_updated = datetime.now()
                        updated_count += 1

                    else:
                        # Create new enhanced instrument
                        instrument = Instrument(
                            symbol=symbol,
                            name=inst_data.get("name", symbol),
                            instrument_type=_to_instrument_type(
                                inst_data.get("instrument_type")
                            ),
                            exchange=_to_exchange(inst_data.get("exchange")),
                            currency=inst_data.get("currency", "USD"),
                            underlying_symbol=inst_data.get("underlying_symbol"),
                            option_type=inst_data.get("option_type"),
                            strike_price=inst_data.get("strike_price"),
                            expiration_date=inst_data.get("expiry_date"),
                            multiplier=inst_data.get("multiplier", 1),
                            is_tradeable=inst_data.get("is_tradeable", True),
                            is_active=inst_data.get("is_active", True),
                            data_source=inst_data.get(
                                "data_source", "ibkr_flexquery_enhanced"
                            ),
                            last_updated=datetime.now(),
                        )

                        db.add(instrument)
                        synced_count += 1

                except Exception as e:
                    logger.error(
                        f"Error processing instrument {inst_data.get('symbol', 'UNKNOWN')}: {e}"
                    )
                    continue

            db.flush()

            logger.info(
                f"✅ Enhanced instruments: {synced_count} new, {updated_count} updated"
            )
            return {
                "synced": synced_count,
                "updated": updated_count,
                "total_processed": len(instruments_data),
                # Back-compat with tests
                "total_symbols": len(instruments_data),
            }

        except Exception as e:
            logger.error(f"❌ Error syncing enhanced instruments: {e}")
            import traceback

            traceback.print_exc()
            return {"error": str(e)}

    async def _sync_tax_lots_from_flexquery(
        self,
        db: Session,
        broker_account: BrokerAccount,
        account_number: str,
        report_xml: str | None = None,
        flexquery_client: IBKRFlexQueryClient | None = None,
    ) -> Dict:
        """Sync tax lots using a three-tier priority chain:

        1. LOT-level OpenPositions rows (official IBKR per-lot data)
        2. Trade-based FIFO reconstruction from Trades XML
        3. SUMMARY-level OpenPositions (one lot per position approximation)
        """
        try:
            fc = flexquery_client or self._default_client

            from datetime import date as _date, datetime as _datetime

            def _coerce_date(value):
                if value is None:
                    return None
                try:
                    if isinstance(value, _datetime):
                        return value.date()
                    if isinstance(value, _date):
                        return value
                    s = str(value).strip()
                    if not s:
                        return None
                    for fmt in ("%Y%m%d", "%Y-%m-%d"):
                        try:
                            return _datetime.strptime(s[:10], fmt).date()
                        except Exception:
                            continue
                    return _datetime.fromisoformat(s).date()
                except Exception:
                    return None

            synced_count = 0
            total_cost = 0.0
            total_value = 0.0
            source_label = "none"

            # ── Tier 1: LOT-level OpenPositions (best source) ──
            if report_xml:
                lot_rows = fc._parse_tax_lots_from_lot_rows(report_xml, account_number)
                if lot_rows:
                    logger.info(
                        "Tier 1: found %d LOT-level rows for %s",
                        len(lot_rows), account_number,
                    )
                    db.query(TaxLot).filter(TaxLot.account_id == broker_account.id).delete()
                    for ld in lot_rows:
                        try:
                            symbol = ld.get("symbol", "")
                            if not symbol or len(symbol) > 20:
                                continue
                            cost = float(ld.get("cost_basis", 0))
                            mkt = float(ld.get("market_value", 0))
                            db.add(TaxLot(
                                user_id=broker_account.user_id,
                                account_id=broker_account.id,
                                lot_id=f"IBKR_LOT_{symbol}_{synced_count}",
                                symbol=symbol,
                                quantity=float(ld.get("quantity", 0)),
                                cost_per_share=float(ld.get("cost_per_share", 0)),
                                cost_basis=cost,
                                acquisition_date=_coerce_date(ld.get("acquisition_date")),
                                current_price=float(ld.get("current_price", 0)),
                                market_value=mkt,
                                unrealized_pnl=float(ld.get("unrealized_pnl", 0)),
                                unrealized_pnl_pct=float(ld.get("unrealized_pnl_pct", 0)),
                                currency=ld.get("currency", "USD"),
                                asset_category=ld.get("asset_category", "STK"),
                                contract_id=ld.get("contract_id") or None,
                                trade_id=ld.get("trade_id") or None,
                                order_id=ld.get("order_id") or None,
                                exchange=ld.get("exchange") or None,
                                fx_rate=float(ld.get("fx_rate", 1)),
                                source=TaxLotSource.OFFICIAL_STATEMENT,
                            ))
                            synced_count += 1
                            total_cost += cost
                            total_value += mkt
                        except Exception as e:
                            logger.error("Error creating LOT-level tax lot: %s", e)
                            continue
                    source_label = "lot_level_official"

            # ── Tier 2: Trade-based FIFO reconstruction ──
            if synced_count == 0:
                tax_lots_data = (
                    fc._parse_tax_lots(report_xml, account_number)
                    if report_xml
                    else await fc.get_official_tax_lots(account_number)
                )
                if tax_lots_data:
                    db.query(TaxLot).filter(TaxLot.account_id == broker_account.id).delete()
                    for ld in tax_lots_data:
                        try:
                            symbol = ld.get("symbol", "")
                            if not symbol or len(symbol) > 20:
                                continue
                            cost = float(ld.get("cost_basis", 0))
                            mkt = float(ld.get("market_value", ld.get("current_value", 0)) or 0)
                            db.add(TaxLot(
                                user_id=broker_account.user_id,
                                account_id=broker_account.id,
                                lot_id=f"IBKR_{symbol}_{synced_count}",
                                symbol=symbol,
                                quantity=float(ld.get("quantity", 0)),
                                cost_per_share=float(ld.get("cost_per_share", 0)),
                                cost_basis=cost,
                                acquisition_date=_coerce_date(ld.get("acquisition_date")),
                                current_price=float(ld.get("current_price", 0)),
                                market_value=mkt,
                                unrealized_pnl=float(ld.get("unrealized_pnl", 0)),
                                unrealized_pnl_pct=float(ld.get("unrealized_pnl_pct", 0)),
                                currency=ld.get("currency", "USD"),
                                asset_category=ld.get("asset_category", ld.get("contract_type", "STK")),
                                trade_id=ld.get("trade_id"),
                                exchange=ld.get("exchange"),
                                source=TaxLotSource.CALCULATED,
                            ))
                            synced_count += 1
                            total_cost += cost
                            total_value += mkt
                        except Exception as e:
                            logger.error("Error creating trade-reconstructed tax lot: %s", e)
                            continue
                    source_label = "trades_fifo"

            # ── Tier 3: SUMMARY-level OpenPositions fallback ──
            if synced_count == 0 and report_xml:
                logger.info(
                    "Tiers 1-2 yielded 0 lots; falling back to SUMMARY for %s",
                    account_number,
                )
                stock_positions = fc._parse_stock_positions(report_xml, account_number)
                if stock_positions:
                    db.query(TaxLot).filter(TaxLot.account_id == broker_account.id).delete()
                    for sp in stock_positions:
                        try:
                            qty = float(sp.get("quantity", 0))
                            if qty == 0:
                                continue
                            cps = float(sp.get("cost_basis_price", 0))
                            cost = float(sp.get("cost_basis_money", 0))
                            mark = float(sp.get("mark_price", 0))
                            mkt_val = float(sp.get("market_value", 0))
                            pnl = float(sp.get("unrealized_pnl", 0))
                            pnl_pct = (pnl / cost * 100) if cost else 0.0
                            db.add(TaxLot(
                                user_id=broker_account.user_id,
                                account_id=broker_account.id,
                                lot_id=f"IBKR_SUM_{sp['symbol']}_{synced_count}",
                                symbol=sp["symbol"],
                                quantity=qty,
                                cost_per_share=cps,
                                cost_basis=cost,
                                current_price=mark,
                                market_value=mkt_val,
                                unrealized_pnl=pnl,
                                unrealized_pnl_pct=pnl_pct,
                                currency=sp.get("currency", "USD"),
                                asset_category=sp.get("asset_category", "STK"),
                                source=TaxLotSource.CALCULATED,
                            ))
                            synced_count += 1
                            total_cost += cost
                            total_value += mkt_val
                        except Exception as e:
                            logger.error("Error creating SUMMARY fallback tax lot: %s", e)
                            continue
                    source_label = "summary_fallback"

            db.flush()
            total_pnl = total_value - total_cost

            return {
                "synced": synced_count,
                "source": source_label,
                "total_cost_basis": f"${total_cost:,.2f}",
                "total_market_value": f"${total_value:,.2f}",
                "unrealized_pnl": f"${total_pnl:,.2f}",
            }

        except Exception as e:
            logger.error(f"Error syncing tax lots: {e}")
            return {"error": str(e)}

    async def _sync_trades_from_flexquery(
        self,
        db: Session,
        broker_account: BrokerAccount,
        account_number: str,
        report_xml: str | None = None,
        flexquery_client: IBKRFlexQueryClient | None = None,
    ) -> Dict:
        """Sync historical trades from FlexQuery Trades section."""
        try:
            fc = flexquery_client or self._default_client
            # Get raw FlexQuery XML and parse trades section (with polling)
            raw_xml = report_xml or await fc.get_full_report(account_number)
            if not raw_xml:
                return {"error": "FlexQuery report not ready"}

            parsed = fc._parse_trades_from_xml(raw_xml, account_number)

            if isinstance(parsed, list):
                trades_data = parsed
                closed_lots_data: list = []
                wash_sales_data: list = []
            else:
                trades_data = parsed.get("trades", [])
                closed_lots_data = parsed.get("closed_lots", [])
                wash_sales_data = parsed.get("wash_sales", [])

            db.query(Trade).filter(Trade.account_id == broker_account.id).delete(
                synchronize_session="fetch"
            )

            synced_count = 0

            def _store_trade(td: dict, status: str) -> bool:
                nonlocal synced_count
                exec_id = str(td.get("execution_id") or "").strip() or None
                trade = Trade(
                    account_id=broker_account.id,
                    symbol=td.get("symbol"),
                    side=td.get("side", "BUY"),
                    quantity=Decimal(str(td.get("quantity", 0))),
                    price=Decimal(str(td.get("price", 0))),
                    total_value=Decimal(str(td.get("total_value", 0))),
                    commission=Decimal(str(td.get("commission", 0))),
                    fees=Decimal(str(td.get("fees", 0))),
                    execution_time=td.get("execution_time") or datetime.now(),
                    order_time=td.get("order_time"),
                    execution_id=exec_id,
                    order_id=str(td.get("order_id") or "") or None,
                    settlement_date=td.get("settlement_date"),
                    realized_pnl=Decimal(str(td.get("realized_pnl", 0))),
                    is_opening=td.get("is_opening", True),
                    notes=td.get("notes") or None,
                    status=status,
                    is_paper_trade=False,
                    trade_metadata=serialize_for_json(td),
                )
                db.add(trade)
                synced_count += 1
                return True

            for td in trades_data:
                try:
                    _store_trade(td, "FILLED")
                except Exception as e:
                    logger.error(f"Error creating trade: {e}")

            for td in closed_lots_data:
                try:
                    _store_trade(td, "CLOSED_LOT")
                except Exception as e:
                    logger.error(f"Error creating closed lot: {e}")

            for td in wash_sales_data:
                try:
                    _store_trade(td, "WASH_SALE")
                except Exception as e:
                    logger.error(f"Error creating wash sale: {e}")

            db.flush()
            logger.info(
                f"✅ Synced {len(trades_data)} trades, "
                f"{len(closed_lots_data)} closed lots, "
                f"{len(wash_sales_data)} wash sales"
            )
            return {
                "synced": len(trades_data),
                "closed_lots": len(closed_lots_data),
                "wash_sales": len(wash_sales_data),
            }

        except Exception as e:
            logger.error(f"Error syncing trades: {e}")
            return {"error": str(e)}

    async def _sync_position_from_tax_lots(
        self, db: Session, broker_account: BrokerAccount
    ) -> Dict:
        """Sync position by aggregating tax lots by symbol."""
        try:
            # Get all tax lots for this account using broker account ID
            tax_lots = (
                db.query(TaxLot).filter(TaxLot.account_id == broker_account.id).all()
            )

            # Aggregate by symbol
            position_data = {}
            for lot in tax_lots:
                symbol = lot.symbol
                if symbol not in position_data:
                    position_data[symbol] = {
                        "quantity": 0,
                        "total_cost": 0,
                        "total_value": 0,
                        "current_price": float(lot.current_price or 0),
                        "currency": lot.currency,
                        "contract_type": lot.asset_category,  # Fixed: Use asset_category not contract_type
                    }

                position_data[symbol]["quantity"] += float(
                    lot.quantity or 0
                )  # Fixed: Use quantity not original_quantity
                position_data[symbol]["total_cost"] += float(lot.cost_basis or 0)
                position_data[symbol]["total_value"] += float(
                    lot.market_value or 0
                )  # Fixed: Use market_value not current_value

            # Clear existing positions (must remove FK dependents first)
            existing_pos_ids = [
                r[0] for r in db.query(Position.id).filter(
                    Position.account_id == broker_account.id
                ).all()
            ]
            if existing_pos_ids:
                db.query(PositionCategory).filter(
                    PositionCategory.position_id.in_(existing_pos_ids)
                ).delete(synchronize_session="fetch")
                db.query(Position).filter(
                    Position.id.in_(existing_pos_ids)
                ).delete(synchronize_session="fetch")

            # Create position
            synced_count = 0
            for symbol, data in position_data.items():
                if data["quantity"] != 0:  # Only active positions
                    avg_cost = (
                        data["total_cost"] / data["quantity"]
                        if data["quantity"] != 0
                        else 0
                    )
                    unrealized_pnl = data["total_value"] - data["total_cost"]
                    unrealized_pnl_pct = (
                        (unrealized_pnl / data["total_cost"] * 100)
                        if data["total_cost"] != 0
                        else 0
                    )

                    position = Position(
                        user_id=broker_account.user_id,
                        account_id=broker_account.id,
                        symbol=symbol,
                        instrument_type="STOCK",
                        position_type=(
                            PositionType.LONG
                            if data["quantity"] > 0
                            else PositionType.SHORT
                        ),
                        quantity=Decimal(str(data["quantity"])),
                        status=PositionStatus.OPEN,
                        average_cost=Decimal(str(avg_cost)),
                        total_cost_basis=Decimal(str(data["total_cost"])),
                        current_price=Decimal(str(data["current_price"])),
                        market_value=Decimal(str(data["total_value"])),
                        unrealized_pnl=Decimal(str(unrealized_pnl)),
                        unrealized_pnl_pct=Decimal(str(unrealized_pnl_pct)),
                        position_updated_at=datetime.now(),
                    )

                    db.add(position)
                    synced_count += 1

            db.flush()
            return {"synced": synced_count}

        except Exception as e:
            logger.error(f"Error syncing position: {e}")
            try:
                db.rollback()
            except Exception:
                pass
            return {"error": str(e)}

    async def _sync_positions_from_open_positions(
        self,
        db: Session,
        broker_account: BrokerAccount,
        account_number: str,
        report_xml: str | None = None,
        flexquery_client: IBKRFlexQueryClient | None = None,
    ) -> Dict:
        """Sync positions directly from FlexQuery OpenPositions SUMMARY rows.

        Used as a fallback when tax-lot reconstruction yields 0 positions
        (e.g. the Trades section in the API response is too sparse).
        """
        try:
            fc = flexquery_client or self._default_client
            raw_xml = report_xml or await fc.get_full_report(account_number)
            if not raw_xml:
                return {"synced": 0}

            stock_positions = fc._parse_stock_positions(raw_xml, account_number)
            if not stock_positions:
                return {"synced": 0}

            existing_pos_ids = [
                r[0] for r in db.query(Position.id).filter(
                    Position.account_id == broker_account.id
                ).all()
            ]
            if existing_pos_ids:
                db.query(PositionCategory).filter(
                    PositionCategory.position_id.in_(existing_pos_ids)
                ).delete(synchronize_session="fetch")
                db.query(Position).filter(
                    Position.id.in_(existing_pos_ids)
                ).delete(synchronize_session="fetch")

            synced_count = 0
            for sp in stock_positions:
                try:
                    qty = Decimal(str(sp["quantity"]))
                    cost_basis = Decimal(str(sp["cost_basis_money"]))
                    mkt_val = Decimal(str(sp["market_value"]))
                    avg_cost = Decimal(str(sp["cost_basis_price"]))
                    pnl = Decimal(str(sp["unrealized_pnl"]))
                    pnl_pct = (pnl / cost_basis * 100) if cost_basis else Decimal("0")

                    position = Position(
                        user_id=broker_account.user_id,
                        account_id=broker_account.id,
                        symbol=sp["symbol"],
                        instrument_type="STOCK",
                        position_type=PositionType.LONG if qty > 0 else PositionType.SHORT,
                        quantity=qty,
                        status=PositionStatus.OPEN,
                        average_cost=avg_cost,
                        total_cost_basis=cost_basis,
                        current_price=Decimal(str(sp["mark_price"])),
                        market_value=mkt_val,
                        unrealized_pnl=pnl,
                        unrealized_pnl_pct=pnl_pct,
                        position_updated_at=datetime.now(),
                    )
                    db.add(position)
                    synced_count += 1
                except Exception:
                    continue

            db.flush()
            logger.info("Synced %d positions from OpenPositions for %s", synced_count, account_number)
            return {"synced": synced_count}
        except Exception as e:
            logger.error("Error syncing positions from OpenPositions: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
            return {"error": str(e)}

    async def _sync_current_prices(self, db: Session, account_number: str) -> Dict:
        """Sync current market prices for all symbols."""
        try:
            # Get unique symbols from tax lots using account_number
            tax_lots = (
                db.query(TaxLot)
                .filter(TaxLot.account_id == account_number)
                .distinct(TaxLot.symbol)
                .all()
            )
            symbols = [lot.symbol for lot in tax_lots]

            synced_count = 0
            for symbol in symbols:
                # Get current price from tax lot data (already has latest prices)
                latest_lot = db.query(TaxLot).filter(TaxLot.symbol == symbol).first()
                if latest_lot and latest_lot.current_price:
                    # Create or update price data
                    existing_price = (
                        db.query(PriceData)
                        .filter(
                            and_(
                                PriceData.symbol == symbol,
                                PriceData.date == datetime.now().date(),
                            )
                        )
                        .first()
                    )

                    if not existing_price:
                        price_data = PriceData(
                            symbol=symbol,
                            date=datetime.now().date(),
                            close_price=latest_lot.current_price,
                            data_source="ibkr_flexquery",
                            interval="1d",
                        )
                        db.add(price_data)
                        synced_count += 1

            db.flush()
            return {"synced": synced_count}

        except Exception as e:
            logger.error(f"Error syncing prices: {e}")
            return {"error": str(e)}

    async def _sync_positions_from_position(
        self, db: Session, broker_account: BrokerAccount
    ) -> Dict:
        """Sync detailed positions from position."""
        try:
            position = (
                db.query(Position)
                .filter(Position.account_id == broker_account.id)
                .all()
            )

            # Clear existing positions (must remove FK dependents first)
            existing_pos_ids = [p.id for p in position]
            if existing_pos_ids:
                db.query(PositionCategory).filter(
                    PositionCategory.position_id.in_(existing_pos_ids)
                ).delete(synchronize_session="fetch")
                db.query(Position).filter(
                    Position.id.in_(existing_pos_ids)
                ).delete(synchronize_session="fetch")

            synced_count = 0
            for holding in position:
                if holding.quantity != 0:  # Only active positions
                    position = Position(
                        user_id=broker_account.user_id,
                        account_id=broker_account.id,  # Use broker_account.id for Position FK constraint
                        symbol=holding.symbol,
                        instrument_type="STOCK",
                        position_type=(
                            PositionType.LONG
                            if holding.quantity > 0
                            else PositionType.SHORT
                        ),
                        quantity=Decimal(str(holding.quantity)),
                        status=PositionStatus.OPEN,
                        average_cost=Decimal(str(holding.average_cost)),
                        total_cost_basis=Decimal(
                            str(holding.average_cost * holding.quantity)
                        ),
                        current_price=Decimal(str(holding.current_price)),
                        market_value=Decimal(str(holding.market_value)),
                        unrealized_pnl=Decimal(str(holding.unrealized_pnl)),
                        unrealized_pnl_pct=Decimal(str(holding.unrealized_pnl_pct)),
                        sector=holding.sector,
                        position_updated_at=datetime.now(),
                    )

                    db.add(position)
                    synced_count += 1

            db.flush()
            return {"synced": synced_count}

        except Exception as e:
            logger.error(f"Error syncing positions: {e}")
            try:
                db.rollback()
            except Exception:
                pass
            return {"error": str(e)}

    # ---- Test Back-Compat Aliases ----
    async def _sync_holdings_from_tax_lots(
        self, db: Session, broker_account: BrokerAccount
    ) -> Dict:
        """Alias kept for tests: holdings == aggregated positions from tax lots."""
        return await self._sync_position_from_tax_lots(db, broker_account)

    async def _sync_positions(self, db: Session, broker_account: BrokerAccount) -> Dict:
        """Alias kept for tests: positions derived from existing holdings/positions table."""
        return await self._sync_positions_from_position(db, broker_account)

    async def _create_portfolio_snapshot(
        self, db: Session, broker_account: BrokerAccount
    ) -> Dict:
        """Create daily portfolio snapshot for tracking."""
        try:
            today = datetime.now().date()

            # Check if snapshot already exists
            existing = (
                db.query(PortfolioSnapshot)
                .filter(
                    PortfolioSnapshot.account_id == broker_account.id,
                    PortfolioSnapshot.snapshot_date
                    >= datetime.combine(today, datetime.min.time()),
                )
                .first()
            )

            if existing:
                return {"created": False, "reason": "Snapshot already exists for today"}

            # Calculate totals from position
            position = (
                db.query(Position)
                .filter(Position.account_id == broker_account.id)
                .all()
            )
            total_value = sum(h.market_value for h in position)
            unrealized_pnl = sum(h.unrealized_pnl for h in position)

            # Ensure JSON-serializable payload (e.g., Decimals → float)
            def _to_float(value):
                try:
                    if isinstance(value, Decimal):
                        return float(value)
                except Exception:
                    pass
                return value

            snapshot = PortfolioSnapshot(
                account_id=broker_account.id,  # PortfolioSnapshot uses integer account ID
                snapshot_date=datetime.now(),
                total_value=total_value,
                total_cash=0,  # Will be enhanced later
                total_equity_value=total_value,
                unrealized_pnl=unrealized_pnl,
                positions_snapshot=json.dumps(
                    [
                        {
                            "symbol": h.symbol,
                            "quantity": _to_float(h.quantity),
                            "value": _to_float(h.market_value),
                            "pnl": _to_float(h.unrealized_pnl),
                        }
                        for h in position
                    ]
                ),
            )

            db.add(snapshot)
            db.flush()

            return {"created": True, "total_value": f"${total_value:,.2f}"}

        except Exception as e:
            logger.error(f"Error creating snapshot: {e}")
            return {"error": str(e)}

    async def _sync_option_positions_from_flexquery(
        self,
        db: Session,
        broker_account: BrokerAccount,
        account_number: str,
        report_xml: str | None = None,
        flexquery_client: IBKRFlexQueryClient | None = None,
    ) -> Dict:
        """Sync option positions from IBKR FlexQuery OpenPositions section."""
        try:
            logger.info(f"📊 Syncing option positions for {account_number}")

            fc = flexquery_client or self._default_client
            # Get option positions from FlexQuery first
            option_positions_data = (
                fc._parse_option_positions(report_xml, account_number)
                if report_xml
                else await fc.get_option_positions(account_number)
            )

            # If FlexQuery returns no open option positions, attempt real-time fallback via ib_insync
            if not option_positions_data:
                try:
                    from backend.services.clients.ibkr_client import ibkr_client as _ib
                    rt_positions = await _ib.get_positions(account_number)
                    opt_positions = [p for p in rt_positions if str(p.get("contract_type", "")).upper() in {"OPT", "OPTION"}]
                    option_positions_data = []
                    for p in opt_positions:
                        qty = float(p.get("position", 0))
                        if qty == 0:
                            continue
                        # Basic mapping; further enrichment can be added later
                        option_positions_data.append(
                            {
                                "symbol": p.get("symbol", ""),
                                "underlying_symbol": p.get("symbol", "").split(" ")[0] if " " in p.get("symbol", "") else "",
                                "strike_price": None,
                                "expiry_date": None,
                                "option_type": None,
                                "multiplier": 100,
                                "open_quantity": qty,
                                "current_price": 0.0,
                                "market_value": float(p.get("market_value", 0.0)),
                                "unrealized_pnl": float(p.get("unrealized_pnl", 0.0)),
                                "currency": p.get("currency", "USD"),
                                "data_source": "ibkr_realtime",
                            }
                        )
                except Exception:
                    option_positions_data = []

            # Get historical option exercises from OptionEAE section
            option_exercises_data = (
                fc._parse_option_exercises(report_xml, account_number)
                if report_xml
                else await fc.get_historical_option_exercises(account_number)
            )

            # Clear existing option positions for this account
            db.query(Option).filter_by(account_id=broker_account.id).delete()

            synced_count = 0
            skipped_count = 0
            exercises_count = 0

            # Sync current option positions (if any)
            for option_data in option_positions_data:
                try:
                    option_position = Option(
                        user_id=broker_account.user_id,
                        account_id=broker_account.id,
                        symbol=option_data["symbol"],
                        underlying_symbol=option_data["underlying_symbol"],
                        strike_price=option_data["strike_price"],
                        expiry_date=option_data["expiry_date"],
                        option_type=option_data["option_type"],
                        multiplier=option_data["multiplier"],
                        open_quantity=option_data["open_quantity"],
                        current_price=option_data["current_price"],
                        total_cost=option_data.get("cost_basis_money") or None,
                        unrealized_pnl=option_data["unrealized_pnl"],
                        realized_pnl=option_data.get("realized_pnl") or None,
                        currency=option_data["currency"],
                        data_source=option_data["data_source"],
                    )

                    db.add(option_position)
                    synced_count += 1

                except Exception as e:
                    logger.error(
                        f"Error creating option position for {option_data.get('symbol', 'UNKNOWN')}: {e}"
                    )
                    skipped_count += 1
                    continue

            # Sync historical option exercises (OptionEAE)
            for exercise_data in option_exercises_data:
                try:
                    # Create Option record for historical exercise/assignment
                    option_exercise = Option(
                        user_id=broker_account.user_id,
                        account_id=broker_account.id,
                        symbol=exercise_data["symbol"],
                        underlying_symbol=exercise_data["underlying_symbol"],
                        strike_price=exercise_data["strike_price"],
                        expiry_date=exercise_data["expiry_date"],
                        option_type=exercise_data["option_type"],
                        multiplier=exercise_data["multiplier"],
                        exercised_quantity=exercise_data.get("exercised_quantity", 0),
                        assigned_quantity=exercise_data.get("assigned_quantity", 0),
                        open_quantity=0,  # Historical exercises are closed
                        exercise_date=exercise_data.get("exercise_date"),
                        exercise_price=exercise_data.get("exercise_price"),
                        assignment_date=exercise_data.get("assignment_date"),
                        realized_pnl=exercise_data.get("realized_pnl"),
                        total_cost=exercise_data.get("proceeds", 0)
                        - exercise_data.get("commission", 0),
                        commission=exercise_data.get("commission"),
                        currency=exercise_data["currency"],
                        data_source=exercise_data["data_source"],
                    )

                    db.add(option_exercise)
                    exercises_count += 1

                except Exception as e:
                    logger.error(
                        f"Error creating option exercise for {exercise_data.get('symbol', 'UNKNOWN')}: {e}"
                    )
                    skipped_count += 1
                    continue

            db.flush()

            total_synced = synced_count + exercises_count
            logger.info(
                f"✅ Synced {synced_count} current options + {exercises_count} historical exercises = {total_synced} total, skipped {skipped_count}"
            )

            return {
                "synced": total_synced,
                "current_positions": synced_count,
                "historical_exercises": exercises_count,
                "skipped": skipped_count,
            }

        except Exception as e:
            logger.error(f"❌ Error syncing option positions: {e}")
            import traceback

            traceback.print_exc()
            return {"error": str(e)}

    async def _sync_cash_transactions(
        self,
        db: Session,
        broker_account: BrokerAccount,
        account_number: str,
        report_xml: str | None = None,
        flexquery_client: IBKRFlexQueryClient | None = None,
    ) -> Dict:
        """Sync cash transactions including dividends from FlexQuery."""
        try:
            logger.info(f"📊 Syncing cash transactions for {account_number}")

            fc = flexquery_client or self._default_client
            # Get cash transaction data from FlexQuery
            transactions_data = (
                fc._parse_cash_transactions(report_xml, account_number)
                if report_xml
                else await fc.get_cash_transactions(account_number)
            )

            if not transactions_data:
                logger.warning(
                    "No cash transactions returned for %s. "
                    "The IBKR FlexQuery API often omits the CashTransactions section. "
                    "Verify your FlexQuery includes: Cash Transactions, Dividends.",
                    account_number,
                )
                return {"synced": 0, "dividends": 0, "note": "FlexQuery returned no CashTransactions section"}

            synced_count = 0
            dividend_count = 0

            from backend.models.transaction import TransactionSyncStatus

            for tx_data in transactions_data:
                try:
                    tx_type = tx_data.get("transaction_type", "")

                    # Handle dividends separately
                    if tx_type in ["Dividends", "Payment In Lieu Of Dividend"]:
                        # Create dividend record
                        from backend.models.transaction import Dividend

                        existing_dividend = (
                            db.query(Dividend)
                            .filter(
                                Dividend.account_id == broker_account.id,
                                Dividend.external_id == tx_data.get("external_id", ""),
                            )
                            .first()
                        )

                        if not existing_dividend:
                            # Use pay_date as ex_date if ex_date is not available from FlexQuery
                            ex_date = tx_data.get("transaction_date") or tx_data.get(
                                "settlement_date"
                            )
                            pay_date = tx_data.get("settlement_date") or tx_data.get(
                                "transaction_date"
                            )

                            dividend = Dividend(
                                account_id=broker_account.id,
                                external_id=tx_data.get("external_id", ""),
                                symbol=tx_data.get("symbol", ""),
                                ex_date=ex_date,  # Use transaction date as ex_date
                                pay_date=pay_date,
                                dividend_per_share=abs(tx_data.get("amount", 0))
                                / max(tx_data.get("quantity", 1), 1),
                                shares_held=tx_data.get("quantity", 0),
                                total_dividend=abs(tx_data.get("amount", 0)),
                                tax_withheld=tx_data.get("taxes", 0) or 0,
                                net_dividend=abs(tx_data.get("net_amount", 0)),
                                currency=tx_data.get("currency", "USD"),
                                frequency="UNKNOWN",
                                dividend_type=(
                                    "ORDINARY" if "Dividend" in tx_type else "SPECIAL"
                                ),
                                source="ibkr_flexquery",
                            )
                            db.add(dividend)
                            dividend_count += 1

                    # Map IBKR FlexQuery transaction types to our enum values
                    ibkr_to_enum_mapping = {
                        "Dividends": "DIVIDEND",
                        "Payment In Lieu Of Dividend": "PAYMENT_IN_LIEU",
                        "Withholding Tax": "WITHHOLDING_TAX",
                        "Commission Adjustments": "COMMISSION",
                        "Broker Interest Paid": "BROKER_INTEREST_PAID",
                        "Broker Interest Received": "BROKER_INTEREST_RECEIVED",
                        "Deposits & Withdrawals": "DEPOSIT",
                        "Deposits/Withdrawals": "DEPOSIT",
                        "Electronic Fund Transfers": "TRANSFER",
                        "Other Fees": "OTHER_FEE",
                        "Tax Refund": "TAX_REFUND",
                        "Corporate Actions": "OTHER",
                        "Refund": "TAX_REFUND",
                    }

                    # Map the transaction type
                    mapped_transaction_type = ibkr_to_enum_mapping.get(tx_type, "OTHER")

                    from backend.models.transaction import TransactionType
                    ext_id = tx_data.get("external_id", "")
                    # De-duplicate: skip if a transaction with same external_id already exists for this account
                    if ext_id:
                        existing_tx = (
                            db.query(Transaction)
                            .filter(
                                Transaction.account_id == broker_account.id,
                                Transaction.external_id == ext_id,
                            )
                            .first()
                        )
                        if existing_tx:
                            continue

                    transaction = Transaction(
                        account_id=broker_account.id,
                        external_id=ext_id,
                        trade_id=tx_data.get("trade_id") or None,
                        order_id=tx_data.get("order_id") or None,
                        execution_id=tx_data.get("execution_id") or None,
                        symbol=tx_data.get("symbol", ""),
                        description=tx_data.get("description", ""),
                        conid=tx_data.get("conid") or None,
                        security_id=tx_data.get("security_id") or None,
                        cusip=tx_data.get("cusip") or None,
                        isin=tx_data.get("isin") or None,
                        listing_exchange=tx_data.get("listing_exchange") or None,
                        underlying_conid=tx_data.get("underlying_conid") or None,
                        underlying_symbol=tx_data.get("underlying_symbol") or None,
                        multiplier=tx_data.get("multiplier"),
                        strike_price=tx_data.get("strike_price"),
                        expiry_date=tx_data.get("expiry_date"),
                        option_type=tx_data.get("option_type"),
                        transaction_type=(
                            TransactionType[mapped_transaction_type]
                            if mapped_transaction_type in TransactionType.__members__
                            else TransactionType.OTHER
                        ),
                        action=tx_data.get("action") or None,
                        quantity=tx_data.get("quantity"),
                        trade_price=tx_data.get("trade_price"),
                        amount=tx_data.get("amount", 0.0),
                        proceeds=tx_data.get("proceeds"),
                        commission=tx_data.get("commission"),
                        brokerage_commission=tx_data.get("brokerage_commission"),
                        clearing_commission=tx_data.get("clearing_commission"),
                        third_party_commission=tx_data.get("third_party_commission"),
                        other_fees=tx_data.get("other_fees"),
                        net_amount=tx_data.get("net_amount", tx_data.get("amount", 0.0)),
                        currency=tx_data.get("currency", "USD"),
                        fx_rate_to_base=tx_data.get("fx_rate_to_base"),
                        asset_category=tx_data.get("asset_category") or None,
                        sub_category=tx_data.get("sub_category") or None,
                        transaction_date=tx_data.get("transaction_date")
                        or tx_data.get("settlement_date"),
                        trade_date=tx_data.get("trade_date"),
                        settlement_date_target=tx_data.get("settlement_date_target"),
                        settlement_date=tx_data.get("settlement_date"),
                        taxes=tx_data.get("taxes"),
                        taxable_amount=tx_data.get("taxable_amount"),
                        taxable_amount_base=tx_data.get("taxable_amount_base"),
                        corporate_action_flag=tx_data.get("corporate_action_flag") or None,
                        corporate_action_id=tx_data.get("corporate_action_id") or None,
                        source="ibkr_flexquery",
                    )

                    db.add(transaction)
                    synced_count += 1

                except Exception as e:
                    logger.error(
                        f"Error processing cash transaction {tx_data.get('external_id', 'UNKNOWN')}: {e}"
                    )
                    continue

                    # ------------------------------------------------------------------
            # Post-process dividends to enrich frequency & shares_held metrics
            # ------------------------------------------------------------------
            from collections import defaultdict
            from statistics import median
            from backend.models.transaction import Dividend as _Div

            divs_by_symbol: defaultdict[str, list[_Div]] = defaultdict(list)
            for d in db.query(_Div).filter(_Div.account_id == broker_account.id).all():
                divs_by_symbol[d.symbol].append(d)

            for sym, divs in divs_by_symbol.items():
                if len(divs) < 2:
                    continue
                divs.sort(key=lambda d: d.ex_date)
                day_diffs = [
                    (divs[i].ex_date - divs[i - 1].ex_date).days
                    for i in range(1, len(divs))
                ]
                if not day_diffs:
                    continue
                avg_gap = median(day_diffs)
                freq = "annual"
                if avg_gap <= 45:
                    freq = "monthly"
                elif avg_gap <= 135:
                    freq = "quarterly"
                for d in divs:
                    d.frequency = freq
                    # fill shares_held if zero
                    # If shares_held missing or 1 (leading to per_share == total)
                    if (not d.shares_held or d.shares_held <= 1) or (
                        d.dividend_per_share == d.total_dividend
                    ):
                        # Approximate using current position quantity
                        p = (
                            db.query(Position)
                            .filter(
                                Position.account_id == broker_account.id,
                                Position.symbol == d.symbol,
                            )
                            .first()
                        )
                        if p and p.quantity:
                            d.shares_held = float(p.quantity)
                            d.dividend_per_share = (
                                abs(d.total_dividend) / d.shares_held
                                if d.shares_held
                                else d.dividend_per_share
                            )
                            d.net_dividend = d.total_dividend - (d.tax_withheld or 0)
            # Record sync status (write or update a simple status row)
            try:
                from backend.models.transaction import TransactionSyncStatus

                status = TransactionSyncStatus(
                    account_id=broker_account.id,
                    last_sync_date=datetime.now(),
                    last_successful_sync=datetime.now(),
                    sync_status="completed",
                    total_transactions=synced_count,
                    total_dividends=dividend_count,
                )
                db.add(status)
            except Exception:
                pass

            db.flush()

            logger.info(
                f"✅ Cash transactions: {synced_count} transactions, {dividend_count} dividends enriched"
            )
            return {
                "synced": synced_count,
                "dividends": dividend_count,
                "total_processed": len(transactions_data),
            }

        except Exception as e:
            logger.error(f"❌ Error syncing cash transactions: {e}")
            import traceback

            traceback.print_exc()
            return {"error": str(e)}

    async def _sync_account_balances(
        self,
        db: Session,
        broker_account: BrokerAccount,
        account_number: str,
        report_xml: str | None = None,
        flexquery_client: IBKRFlexQueryClient | None = None,
    ) -> Dict:
        """Sync account balances from FlexQuery."""
        try:
            logger.info(f"📊 Syncing account balances for {account_number}")

            fc = flexquery_client or self._default_client
            # Get account balance data from FlexQuery
            balances_data = (
                fc._parse_account_information(report_xml, account_number)
                if report_xml
                else await fc.get_account_balances(account_number)
            )

            if not balances_data:
                logger.info(f"No account balance data found for {account_number}")
                return {"synced": 0}

            synced_count = 0

            for balance_data in balances_data:
                try:
                    from backend.models.account_balance import AccountBalance

                    # Check if balance already exists for this date
                    existing_balance = (
                        db.query(AccountBalance)
                        .filter(
                            AccountBalance.broker_account_id == broker_account.id,
                            AccountBalance.balance_date
                            == balance_data.get("balance_date"),
                        )
                        .first()
                    )

                    if not existing_balance:
                        account_balance = AccountBalance(
                            user_id=broker_account.user_id,
                            broker_account_id=broker_account.id,
                            balance_date=balance_data.get("balance_date"),
                            balance_type=balance_data.get(
                                "balance_type", "DAILY_SNAPSHOT"
                            ),
                            base_currency=balance_data.get("base_currency", "USD"),
                            total_cash_value=balance_data.get("total_cash_value", 0),
                            settled_cash=balance_data.get("settled_cash"),
                            available_funds=balance_data.get("available_funds"),
                            cash_balance=balance_data.get("cash_balance"),
                            net_liquidation=balance_data.get("net_liquidation"),
                            gross_position_value=balance_data.get(
                                "gross_position_value"
                            ),
                            equity=balance_data.get("equity"),
                            previous_day_equity=balance_data.get("previous_day_equity"),
                            buying_power=balance_data.get("buying_power"),
                            initial_margin_req=balance_data.get("initial_margin_req"),
                            maintenance_margin_req=balance_data.get(
                                "maintenance_margin_req"
                            ),
                            reg_t_equity=balance_data.get("reg_t_equity"),
                            sma=balance_data.get("sma"),
                            unrealized_pnl=balance_data.get("unrealized_pnl"),
                            realized_pnl=balance_data.get("realized_pnl"),
                            daily_pnl=balance_data.get("daily_pnl"),
                            cushion=balance_data.get("cushion"),
                            leverage=balance_data.get("leverage"),
                            lookahead_next_change=balance_data.get(
                                "lookahead_next_change"
                            ),
                            lookahead_available_funds=balance_data.get(
                                "lookahead_available_funds"
                            ),
                            lookahead_excess_liquidity=balance_data.get(
                                "lookahead_excess_liquidity"
                            ),
                            lookahead_init_margin=balance_data.get(
                                "lookahead_init_margin"
                            ),
                            lookahead_maint_margin=balance_data.get(
                                "lookahead_maint_margin"
                            ),
                            accrued_cash=balance_data.get("accrued_cash"),
                            accrued_dividend=balance_data.get("accrued_dividend"),
                            accrued_interest=balance_data.get("accrued_interest"),
                            exchange_rate=balance_data.get("exchange_rate", 1),
                            data_source=balance_data.get(
                                "data_source", "OFFICIAL_STATEMENT"
                            ),
                            account_alias=balance_data.get("account_alias", ""),
                            customer_type=balance_data.get("customer_type", ""),
                            account_code=balance_data.get("account_code", ""),
                        )
                        db.add(account_balance)
                        synced_count += 1

                except Exception as e:
                    logger.error(f"Error processing account balance: {e}")
                    continue

            db.flush()

            logger.info(f"✅ Account balances: {synced_count} records")
            return {"synced": synced_count, "total_processed": len(balances_data)}

        except Exception as e:
            logger.error(f"❌ Error syncing account balances: {e}")
            import traceback

            traceback.print_exc()
            return {"error": str(e)}

    async def _sync_margin_interest(
        self,
        db: Session,
        broker_account: BrokerAccount,
        account_number: str,
        report_xml: str | None = None,
        flexquery_client: IBKRFlexQueryClient | None = None,
    ) -> Dict:
        """Sync margin interest from FlexQuery."""
        try:
            logger.info(f"📊 Syncing margin interest for {account_number}")

            fc = flexquery_client or self._default_client
            # Get margin interest data from FlexQuery
            interest_data = (
                fc._parse_interest_accruals(report_xml, account_number)
                if report_xml
                else await fc.get_margin_interest(account_number)
            )

            if not interest_data:
                logger.info(f"No margin interest data found for {account_number}")
                return {"synced": 0}

            synced_count = 0

            for interest_record in interest_data:
                try:
                    from backend.models.margin_interest import MarginInterest

                    # Check if interest record already exists
                    existing_interest = (
                        db.query(MarginInterest)
                        .filter(
                            MarginInterest.broker_account_id == broker_account.id,
                            MarginInterest.from_date
                            == interest_record.get("from_date"),
                            MarginInterest.to_date == interest_record.get("to_date"),
                        )
                        .first()
                    )

                    if not existing_interest:
                        margin_interest = MarginInterest(
                            user_id=broker_account.user_id,
                            broker_account_id=broker_account.id,
                            account_alias=interest_record.get("account_alias", ""),
                            from_date=interest_record.get("from_date"),
                            to_date=interest_record.get("to_date"),
                            starting_balance=interest_record.get(
                                "starting_balance", 0.0
                            ),
                            interest_accrued=interest_record.get(
                                "interest_accrued", 0.0
                            ),
                            accrual_reversal=interest_record.get(
                                "accrual_reversal", 0.0
                            ),
                            ending_balance=interest_record.get("ending_balance", 0.0),
                            interest_rate=interest_record.get("interest_rate"),
                            daily_rate=interest_record.get("daily_rate"),
                            # Truncate currency to fit VARCHAR(10) limit
                            currency=str(interest_record.get("currency", "USD"))[:10],
                            fx_rate_to_base=interest_record.get("fx_rate_to_base", 1.0),
                            interest_type=interest_record.get(
                                "interest_type", "MARGIN"
                            ),
                            description=interest_record.get("description", ""),
                            # Truncate data_source to fit VARCHAR(20) limit
                            data_source="ibkr_flexquery",  # Truncated from 'ibkr_flexquery_interest'
                        )
                        db.add(margin_interest)
                        synced_count += 1

                except Exception as e:
                    logger.error(f"Error processing margin interest record: {e}")
                    continue

            db.flush()

            logger.info(f"✅ Margin interest: {synced_count} records")
            return {"synced": synced_count, "total_processed": len(interest_data)}

        except Exception as e:
            logger.error(f"❌ Error syncing margin interest: {e}")
            import traceback

            traceback.print_exc()
            return {"error": str(e)}

    async def _refresh_prices_for_account(self, db: Session, broker_account: BrokerAccount) -> Dict:
        """Refresh current prices for positions and tax lots of a broker account."""
        from backend.services.market.market_data_service import MarketDataService
        from backend.models.tax_lot import TaxLot
        from backend.models.position import Position

        market_service = MarketDataService()

        # Load target positions
        positions = (
            db.query(Position)
            .filter(Position.account_id == broker_account.id)
            .all()
        )
        positions = [p for p in positions if p.quantity != 0 and p.symbol]
        if not positions:
            return {"updated_positions": 0, "updated_tax_lots": 0, "symbols": []}

        unique_symbols = sorted({p.symbol for p in positions if p.symbol})

        # Fetch prices concurrently
        import asyncio as _asyncio

        price_tasks = [market_service.get_current_price(sym) for sym in unique_symbols]
        prices = await _asyncio.gather(*price_tasks, return_exceptions=True)
        symbol_to_price = {}
        for sym, price in zip(unique_symbols, prices):
            try:
                if isinstance(price, (int, float)) and price > 0:
                    symbol_to_price[sym] = float(price)
            except Exception:
                continue

        # Update positions
        updated_positions = 0
        for p in positions:
            price = symbol_to_price.get(p.symbol)
            if price is None:
                continue
            try:
                quantity_abs = float(abs(p.quantity or 0))
                total_cost = float(p.total_cost_basis or 0)
                market_value = quantity_abs * price
                unrealized = market_value - total_cost
                unrealized_pct = ((unrealized / total_cost) * 100) if total_cost > 0 else 0.0
                p.current_price = price
                p.market_value = market_value
                p.unrealized_pnl = unrealized
                p.unrealized_pnl_pct = unrealized_pct
                updated_positions += 1
            except Exception:
                continue

        # Update tax lots for same scope
        lots = (
            db.query(TaxLot)
            .filter(TaxLot.account_id == broker_account.id)
            .all()
        )
        updated_lots = 0
        for lot in lots:
            price = symbol_to_price.get(lot.symbol)
            if price is None:
                continue
            try:
                qty_abs = float(abs(lot.quantity or 0))
                cost_basis = float(lot.cost_basis or 0)
                market_value = qty_abs * price
                unrealized = market_value - cost_basis
                unrealized_pct = ((unrealized / cost_basis) * 100) if cost_basis and abs(cost_basis) > 1e-9 else 0.0
                lot.current_price = price
                lot.market_value = market_value
                lot.unrealized_pnl = unrealized
                lot.unrealized_pnl_pct = unrealized_pct
                updated_lots += 1
            except Exception:
                continue

        db.flush()
        return {
            "updated_positions": updated_positions,
            "updated_tax_lots": updated_lots,
            "symbols": list(symbol_to_price.keys()),
        }

    async def _sync_transfers(
        self,
        db: Session,
        broker_account: BrokerAccount,
        account_number: str,
        report_xml: str | None = None,
        flexquery_client: IBKRFlexQueryClient | None = None,
    ) -> Dict:
        """Sync transfers from FlexQuery."""
        try:
            logger.info(f"📊 Syncing transfers for {account_number}")

            fc = flexquery_client or self._default_client
            # Get transfer data from FlexQuery
            transfers_data = (
                fc._parse_transfers(report_xml, account_number)
                if report_xml
                else await fc.get_transfers(account_number)
            )

            if not transfers_data:
                logger.info(f"No transfer data found for {account_number}")
                return {"synced": 0}

            synced_count = 0

            for transfer_data in transfers_data:
                try:
                    from backend.models.transfer import Transfer

                    # Check if transfer already exists
                    existing_transfer = (
                        db.query(Transfer)
                        .filter(
                            Transfer.broker_account_id == broker_account.id,
                            Transfer.transaction_id
                            == transfer_data.get("transaction_id", ""),
                        )
                        .first()
                    )

                    if not existing_transfer:
                        transfer = Transfer(
                            user_id=broker_account.user_id,
                            broker_account_id=broker_account.id,
                            transaction_id=transfer_data.get("transaction_id", ""),
                            client_reference=transfer_data.get("client_reference", ""),
                            transfer_date=transfer_data.get("transfer_date"),
                            settle_date=transfer_data.get("settle_date"),
                            # Map ACATS to POSITION since they're essentially the same
                            transfer_type=(
                                "POSITION"
                                if transfer_data.get("transfer_type") == "ACATS"
                                else transfer_data.get("transfer_type", "OTHER")
                            ),
                            direction=transfer_data.get("direction", "IN"),
                            symbol=transfer_data.get("symbol", ""),
                            description=transfer_data.get("description", ""),
                            contract_id=transfer_data.get("contract_id", ""),
                            security_id=transfer_data.get("security_id", ""),
                            security_id_type=transfer_data.get("security_id_type", ""),
                            quantity=transfer_data.get("quantity", 0.0),
                            trade_price=transfer_data.get("trade_price"),
                            transfer_price=transfer_data.get("transfer_price", 0.0),
                            amount=transfer_data.get("amount", 0.0),
                            cash_amount=transfer_data.get("cash_amount"),
                            net_cash=transfer_data.get("net_cash"),
                            commission=transfer_data.get("commission"),
                            currency=transfer_data.get("currency", "USD"),
                            fx_rate_to_base=transfer_data.get("fx_rate_to_base", 1.0),
                            delivery_type=transfer_data.get("delivery_type", ""),
                            transfer_type_code=transfer_data.get("transfer_type_code"),
                            account_alias=transfer_data.get("account_alias", ""),
                            model=transfer_data.get("model", ""),
                            notes=transfer_data.get("notes", ""),
                            external_reference=transfer_data.get(
                                "external_reference", ""
                            ),
                            data_source="ibkr_flexquery",  # Truncated from 'ibkr_flexquery_transfers'
                        )
                        db.add(transfer)
                        synced_count += 1

                except Exception as e:
                    logger.error(f"Error processing transfer record: {e}")
                    continue

            db.flush()

            logger.info(f"✅ Transfers: {synced_count} records")
            return {"synced": synced_count, "total_processed": len(transfers_data)}

        except Exception as e:
            logger.error(f"❌ Error syncing transfers: {e}")
            import traceback

            traceback.print_exc()
            return {"error": str(e)}

    def normalize_instruments_from_activity(self, db: Session) -> Dict:
        """
        Normalize instruments on startup:
        - Uppercase symbols
        - Backfill missing names from Transfers/Transactions descriptions
        """
        updated = 0
        try:
            from backend.models.transfer import Transfer
            from backend.models.transaction import Transaction as _Tx

            instruments = db.query(Instrument).all()
            # Build a quick map of symbol -> candidate name (prefer Transfers)
            sym_to_name: dict[str, str] = {}
            for t in db.query(Transfer).filter(Transfer.symbol.isnot(None)).all():
                sym = (t.symbol or "").strip().upper()
                desc = (t.description or "").strip()
                if sym and desc and len(desc) >= 3:
                    sym_to_name.setdefault(sym, desc)
            for tx in db.query(_Tx).filter(_Tx.symbol.isnot(None)).all():
                sym = (tx.symbol or "").strip().upper()
                desc = (tx.description or "").strip()
                if sym and desc and len(desc) >= 3:
                    sym_to_name.setdefault(sym, desc)

            for inst in instruments:
                normalized_symbol = (inst.symbol or "").strip().upper()
                if inst.symbol != normalized_symbol:
                    inst.symbol = normalized_symbol
                if not inst.name or inst.name.strip().upper() == normalized_symbol:
                    candidate = sym_to_name.get(normalized_symbol)
                    if candidate:
                        inst.name = candidate
                        updated += 1
            db.flush()
            logger.info(f"🧹 Instruments normalized: {updated} updated")
            return {"normalized": updated, "total": len(instruments)}
        except Exception as e:
            logger.warning(f"Instruments normalization skipped: {e}")
            return {"normalized": updated, "error": str(e)}


# Global instance
portfolio_sync_service = IBKRSyncService()

