"""Position, tax lot, instrument, and option sync steps for IBKR pipeline.

medallion: bronze
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import BrokerAccount, PortfolioSnapshot, TaxLot, PriceData
from app.models.instrument import Exchange, Instrument, InstrumentType
from app.models.options import Option
from app.models.portfolio import PositionCategory
from app.models.position import Position, PositionStatus, PositionType
from app.models.tax_lot import TaxLotSource
from app.services.clients.ibkr_flexquery_client import IBKRFlexQueryClient
# medallion: allow cross-layer import (bronze -> silver); resolves when app.services.silver.portfolio.day_pnl_service moves during Phase 0.C
from app.services.silver.portfolio.day_pnl_service import recompute_day_pnl_for_rows

from .helpers import coerce_date, safe_float, DEFAULT_CURRENCY, DEFAULT_ASSET_CATEGORY

logger = logging.getLogger(__name__)

_OCC_RE = re.compile(
    r"^(?P<underlying>[A-Z]{1,6})\s*"
    r"(?P<year>\d{2})(?P<month>\d{2})(?P<day>\d{2})"
    r"(?P<cp>[CP])"
    r"(?P<strike>\d{8})$"
)


def _parse_occ_symbol(symbol: str) -> dict | None:
    """Parse OCC-format option symbol (e.g. 'AAPL  260320C00150000').

    Returns dict with underlying, expiry (date), option_type, strike, or None.
    """
    cleaned = symbol.strip().replace(" ", "")
    m = _OCC_RE.match(cleaned)
    if not m:
        return None
    from datetime import date
    try:
        expiry = date(
            2000 + int(m.group("year")),
            int(m.group("month")),
            int(m.group("day")),
        )
    except ValueError:
        return None
    return {
        "underlying": m.group("underlying"),
        "expiry": expiry,
        "option_type": "CALL" if m.group("cp") == "C" else "PUT",
        "strike": int(m.group("strike")) / 1000,
    }


_INSTRUMENT_TYPE_MAP = {
    "STK": InstrumentType.STOCK,
    "OPT": InstrumentType.OPTION,
    "ETF": InstrumentType.ETF,
    "STOCK": InstrumentType.STOCK,
    "OPTION": InstrumentType.OPTION,
}

_EXCHANGE_ALIASES = {
    "nasdaq": Exchange.NASDAQ,
    "nyse": Exchange.NYSE,
    "cboe": Exchange.CBOE,
}


def _to_instrument_type(value: str) -> InstrumentType:
    if not value:
        return InstrumentType.STOCK
    return _INSTRUMENT_TYPE_MAP.get(str(value).upper(), InstrumentType.STOCK)


def _to_exchange(value: str) -> Exchange:
    if not value:
        return Exchange.NASDAQ
    v = str(value).lower()
    try:
        return Exchange[v.upper()]
    except KeyError:
        return _EXCHANGE_ALIASES.get(v, Exchange.NASDAQ)


async def sync_instruments(
    db: Session,
    account_number: str,
    report_xml: str | None,
    fc: IBKRFlexQueryClient,
) -> Dict:
    """Sync instrument master data from FlexQuery sections."""
    try:
        logger.info("Syncing instruments for %s", account_number)

        instruments_data = []
        lots = (
            fc._parse_tax_lots(report_xml, account_number)
            if report_xml
            else await fc.get_official_tax_lots(account_number)
        )
        if lots:
            stock_symbols = sorted(
                {
                    lot.get("symbol")
                    for lot in lots
                    if lot.get("symbol")
                    and str(lot.get("asset_category", "STK")).upper() in {"STK", "ETF"}
                }
            )
            instruments_data = [
                {
                    "symbol": s[:100],
                    "name": s,
                    "instrument_type": "STOCK",
                    "exchange": "NASDAQ",
                    "currency": DEFAULT_CURRENCY,
                    "data_source": "ibkr_taxlots_fallback",
                }
                for s in stock_symbols
            ]
        else:
            try:
                raw_xml = report_xml or await fc.get_full_report(account_number)
                if raw_xml:
                    instruments_data = fc._parse_enhanced_instruments(raw_xml, account_number) or []
            except Exception as exc:
                logger.warning("Enhanced instruments parse failed: %s", exc)

        if not instruments_data:
            logger.warning("No instrument data found for %s", account_number)
            return {"synced": 0, "updated": 0}

        synced_count = 0
        updated_count = 0

        for inst_data in instruments_data:
            try:
                symbol = (inst_data.get("symbol") or "").strip().upper()
                if not symbol or len(symbol) > 100:
                    continue

                existing = db.query(Instrument).filter(Instrument.symbol == symbol).first()

                if existing:
                    if inst_data.get("name"):
                        if not existing.name or existing.name.strip().upper() == existing.symbol.strip().upper():
                            existing.name = inst_data["name"]
                    if inst_data.get("exchange") and inst_data["exchange"] != "UNKNOWN":
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
                    existing.last_updated = datetime.now(timezone.utc)
                    updated_count += 1
                else:
                    instrument = Instrument(
                        symbol=symbol,
                        name=inst_data.get("name", symbol),
                        instrument_type=_to_instrument_type(inst_data.get("instrument_type")),
                        exchange=_to_exchange(inst_data.get("exchange")),
                        currency=inst_data.get("currency", DEFAULT_CURRENCY),
                        underlying_symbol=inst_data.get("underlying_symbol"),
                        option_type=inst_data.get("option_type"),
                        strike_price=inst_data.get("strike_price"),
                        expiration_date=inst_data.get("expiry_date"),
                        multiplier=inst_data.get("multiplier", 1),
                        is_tradeable=inst_data.get("is_tradeable", True),
                        is_active=inst_data.get("is_active", True),
                        data_source=inst_data.get("data_source", "ibkr_flexquery_enhanced"),
                        last_updated=datetime.now(timezone.utc),
                    )
                    db.add(instrument)
                    synced_count += 1
            except Exception as exc:
                logger.error("Error processing instrument %s: %s", inst_data.get("symbol", "?"), exc)
                continue

        db.flush()
        logger.info("Instruments: %d new, %d updated", synced_count, updated_count)
        return {
            "synced": synced_count,
            "updated": updated_count,
            "total_processed": len(instruments_data),
            "total_symbols": len(instruments_data),
        }
    except Exception as exc:
        logger.error("Error syncing instruments: %s", exc)
        return {"error": str(exc)}


async def sync_tax_lots(
    db: Session,
    broker_account: BrokerAccount,
    account_number: str,
    report_xml: str | None,
    fc: IBKRFlexQueryClient,
) -> Dict:
    """Sync tax lots using three-tier priority: LOT-level -> trade FIFO -> SUMMARY."""
    try:
        synced_count = 0
        total_cost = 0.0
        total_value = 0.0
        source_label = "none"

        # Tier 1: LOT-level OpenPositions
        if report_xml:
            lot_rows = fc._parse_tax_lots_from_lot_rows(report_xml, account_number)
            if lot_rows:
                logger.info("Tier 1: %d LOT-level rows for %s", len(lot_rows), account_number)
                db.query(TaxLot).filter(TaxLot.account_id == broker_account.id).delete()
                for ld in lot_rows:
                    try:
                        symbol = ld.get("symbol", "")
                        if not symbol or len(symbol) > 20:
                            continue
                        cost = safe_float(ld.get("cost_basis"))
                        mkt = safe_float(ld.get("market_value"))
                        db.add(TaxLot(
                            user_id=broker_account.user_id,
                            account_id=broker_account.id,
                            lot_id=f"IBKR_LOT_{symbol}_{synced_count}",
                            symbol=symbol,
                            quantity=safe_float(ld.get("quantity")),
                            cost_per_share=safe_float(ld.get("cost_per_share")),
                            cost_basis=cost,
                            acquisition_date=coerce_date(ld.get("acquisition_date")),
                            current_price=safe_float(ld.get("current_price")),
                            market_value=mkt,
                            unrealized_pnl=safe_float(ld.get("unrealized_pnl")),
                            unrealized_pnl_pct=safe_float(ld.get("unrealized_pnl_pct")),
                            currency=ld.get("currency", DEFAULT_CURRENCY),
                            asset_category=ld.get("asset_category", DEFAULT_ASSET_CATEGORY),
                            contract_id=ld.get("contract_id") or None,
                            trade_id=ld.get("trade_id") or None,
                            order_id=ld.get("order_id") or None,
                            exchange=ld.get("exchange") or None,
                            fx_rate=safe_float(ld.get("fx_rate", 1)),
                            source=TaxLotSource.OFFICIAL_STATEMENT,
                        ))
                        synced_count += 1
                        total_cost += cost
                        total_value += mkt
                    except Exception as exc:
                        logger.error("Error creating LOT-level tax lot: %s", exc)
                        continue
                source_label = "lot_level_official"

        # Tier 2: Trade-based FIFO reconstruction
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
                        cost = safe_float(ld.get("cost_basis"))
                        mkt = safe_float(ld.get("market_value", ld.get("current_value", 0)) or 0)
                        db.add(TaxLot(
                            user_id=broker_account.user_id,
                            account_id=broker_account.id,
                            lot_id=f"IBKR_{symbol}_{synced_count}",
                            symbol=symbol,
                            quantity=safe_float(ld.get("quantity")),
                            cost_per_share=safe_float(ld.get("cost_per_share")),
                            cost_basis=cost,
                            acquisition_date=coerce_date(ld.get("acquisition_date")),
                            current_price=safe_float(ld.get("current_price")),
                            market_value=mkt,
                            unrealized_pnl=safe_float(ld.get("unrealized_pnl")),
                            unrealized_pnl_pct=safe_float(ld.get("unrealized_pnl_pct")),
                            currency=ld.get("currency", DEFAULT_CURRENCY),
                            asset_category=ld.get("asset_category", ld.get("contract_type", DEFAULT_ASSET_CATEGORY)),
                            trade_id=ld.get("trade_id"),
                            exchange=ld.get("exchange"),
                            source=TaxLotSource.CALCULATED,
                        ))
                        synced_count += 1
                        total_cost += cost
                        total_value += mkt
                    except Exception as exc:
                        logger.error("Error creating trade-reconstructed tax lot: %s", exc)
                        continue
                source_label = "trades_fifo"

        # Tier 3: SUMMARY-level OpenPositions fallback
        if synced_count == 0 and report_xml:
            logger.info("Tiers 1-2 yielded 0 lots; falling back to SUMMARY for %s", account_number)
            stock_positions = fc._parse_stock_positions(report_xml, account_number)
            if stock_positions:
                db.query(TaxLot).filter(TaxLot.account_id == broker_account.id).delete()
                for sp in stock_positions:
                    try:
                        qty = safe_float(sp.get("quantity"))
                        if qty == 0:
                            continue
                        cost = safe_float(sp.get("cost_basis_money"))
                        mkt_val = safe_float(sp.get("market_value"))
                        pnl = safe_float(sp.get("unrealized_pnl"))
                        pnl_pct = (pnl / cost * 100) if cost else 0.0
                        db.add(TaxLot(
                            user_id=broker_account.user_id,
                            account_id=broker_account.id,
                            lot_id=f"IBKR_SUM_{sp['symbol']}_{synced_count}",
                            symbol=sp["symbol"],
                            quantity=qty,
                            cost_per_share=safe_float(sp.get("cost_basis_price")),
                            cost_basis=cost,
                            current_price=safe_float(sp.get("mark_price")),
                            market_value=mkt_val,
                            unrealized_pnl=pnl,
                            unrealized_pnl_pct=pnl_pct,
                            currency=sp.get("currency", DEFAULT_CURRENCY),
                            asset_category=sp.get("asset_category", DEFAULT_ASSET_CATEGORY),
                            source=TaxLotSource.CALCULATED,
                        ))
                        synced_count += 1
                        total_cost += cost
                        total_value += mkt_val
                    except Exception as exc:
                        logger.error("Error creating SUMMARY fallback tax lot: %s", exc)
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
    except Exception as exc:
        logger.error("Error syncing tax lots: %s", exc)
        return {"error": str(exc)}


def _clear_positions(db: Session, broker_account: BrokerAccount) -> None:
    """Delete existing positions and FK dependents for a broker account."""
    existing_pos_ids = [
        r[0]
        for r in db.query(Position.id).filter(Position.account_id == broker_account.id).all()
    ]
    if existing_pos_ids:
        db.query(PositionCategory).filter(
            PositionCategory.position_id.in_(existing_pos_ids)
        ).delete(synchronize_session="fetch")
        db.query(Position).filter(
            Position.id.in_(existing_pos_ids)
        ).delete(synchronize_session="fetch")


async def sync_positions_from_tax_lots(
    db: Session, broker_account: BrokerAccount
) -> Dict:
    """Aggregate tax lots by symbol into Position rows."""
    try:
        tax_lots = db.query(TaxLot).filter(TaxLot.account_id == broker_account.id).all()

        position_data: dict[str, dict] = {}
        for lot in tax_lots:
            symbol = lot.symbol
            if symbol not in position_data:
                position_data[symbol] = {
                    "quantity": 0,
                    "total_cost": 0,
                    "total_value": 0,
                    "current_price": safe_float(lot.current_price),
                    "currency": lot.currency,
                    "contract_type": lot.asset_category,
                }
            position_data[symbol]["quantity"] += safe_float(lot.quantity)
            position_data[symbol]["total_cost"] += safe_float(lot.cost_basis)
            position_data[symbol]["total_value"] += safe_float(lot.market_value)

        _clear_positions(db, broker_account)

        synced_count = 0
        touched_rows: list[Position] = []
        for symbol, data in position_data.items():
            if data["quantity"] == 0:
                continue
            avg_cost = data["total_cost"] / data["quantity"] if data["quantity"] != 0 else 0
            unrealized_pnl = data["total_value"] - data["total_cost"]
            unrealized_pnl_pct = (unrealized_pnl / data["total_cost"] * 100) if data["total_cost"] != 0 else 0

            new_pos = Position(
                user_id=broker_account.user_id,
                account_id=broker_account.id,
                symbol=symbol,
                instrument_type="STOCK",
                position_type=PositionType.LONG if data["quantity"] > 0 else PositionType.SHORT,
                quantity=Decimal(str(data["quantity"])),
                status=PositionStatus.OPEN,
                average_cost=Decimal(str(avg_cost)),
                total_cost_basis=Decimal(str(data["total_cost"])),
                current_price=Decimal(str(data["current_price"])),
                market_value=Decimal(str(data["total_value"])),
                unrealized_pnl=Decimal(str(unrealized_pnl)),
                unrealized_pnl_pct=Decimal(str(unrealized_pnl_pct)),
                position_updated_at=datetime.now(timezone.utc),
            )
            db.add(new_pos)
            touched_rows.append(new_pos)
            synced_count += 1

        db.flush()
        # Server-side day P&L recompute (D141) — IBKR FlexQuery does not
        # carry day P&L; this is the canonical place for day_pnl to land.
        day_pnl_stats = recompute_day_pnl_for_rows(db, touched_rows, "ibkr_taxlots")
        return {"synced": synced_count, **day_pnl_stats}
    except Exception as exc:
        logger.error("Error syncing positions from tax lots: %s", exc)
        # Do not rollback: runs inside multi-step IBKR sync; rollback would discard
        # uncommitted work from earlier steps. Pipeline orchestrator rolls back on failure.
        return {"error": str(exc)}


async def sync_positions_from_open_positions(
    db: Session,
    broker_account: BrokerAccount,
    account_number: str,
    report_xml: str | None,
    fc: IBKRFlexQueryClient,
) -> Dict:
    """Fallback: sync positions from FlexQuery OpenPositions SUMMARY rows."""
    try:
        raw_xml = report_xml or await fc.get_full_report(account_number)
        if not raw_xml:
            return {"synced": 0}

        stock_positions = fc._parse_stock_positions(raw_xml, account_number)
        if not stock_positions:
            return {"synced": 0}

        _clear_positions(db, broker_account)

        synced_count = 0
        touched_rows: list[Position] = []
        for sp in stock_positions:
            try:
                qty = Decimal(str(sp["quantity"]))
                cost_basis = Decimal(str(sp["cost_basis_money"]))
                mkt_val = Decimal(str(sp["market_value"]))
                avg_cost = Decimal(str(sp["cost_basis_price"]))
                pnl = Decimal(str(sp["unrealized_pnl"]))
                pnl_pct = (pnl / cost_basis * 100) if cost_basis else Decimal("0")

                new_pos = Position(
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
                    position_updated_at=datetime.now(timezone.utc),
                )
                db.add(new_pos)
                touched_rows.append(new_pos)
                synced_count += 1
            except Exception as e:
                logger.warning(
                    "Skipping OpenPositions row for account %s symbol %s: %s",
                    account_number,
                    sp.get("symbol", "?"),
                    e,
                )
                continue

        db.flush()
        logger.info("Synced %d positions from OpenPositions for %s", synced_count, account_number)
        day_pnl_stats = recompute_day_pnl_for_rows(db, touched_rows, "ibkr_openpositions")
        return {"synced": synced_count, **day_pnl_stats}
    except Exception as exc:
        logger.error("Error syncing positions from OpenPositions: %s", exc)
        # Do not rollback: runs inside multi-step IBKR sync; rollback would discard
        # uncommitted work from earlier steps. Pipeline orchestrator rolls back on failure.
        return {"error": str(exc)}


async def sync_option_positions(
    db: Session,
    broker_account: BrokerAccount,
    account_number: str,
    report_xml: str | None,
    fc: IBKRFlexQueryClient,
) -> Dict:
    """Sync option positions from FlexQuery OpenPositions section."""
    try:
        logger.info("Syncing option positions for %s", account_number)

        option_positions_data = (
            fc._parse_option_positions(report_xml, account_number)
            if report_xml
            else await fc.get_option_positions(account_number)
        )

        dropped_unparseable = 0
        if not option_positions_data:
            try:
                from app.services.clients.ibkr_client import ibkr_client as _ib
                rt_positions = await _ib.get_positions(account_number)
                opt_positions = [
                    p for p in rt_positions
                    if str(p.get("contract_type", "")).upper() in {"OPT", "OPTION"}
                ]
                option_positions_data = []
                for p in opt_positions:
                    qty = safe_float(p.get("position"))
                    if qty == 0:
                        continue
                    parsed = _parse_occ_symbol(p.get("symbol", ""))
                    if not parsed:
                        dropped_unparseable += 1
                        logger.warning(
                            "Skipping live option position with unparseable symbol: %s",
                            p.get("symbol", ""),
                        )
                        continue
                    option_positions_data.append({
                        "symbol": p.get("symbol", ""),
                        "underlying_symbol": parsed["underlying"],
                        "strike_price": parsed["strike"],
                        "expiry_date": parsed["expiry"],
                        "option_type": parsed["option_type"],
                        "multiplier": 100,
                        "open_quantity": qty,
                        "current_price": 0.0,
                        "market_value": safe_float(p.get("market_value")),
                        "unrealized_pnl": safe_float(p.get("unrealized_pnl")),
                        "currency": p.get("currency", DEFAULT_CURRENCY),
                        "data_source": "ibkr_realtime",
                    })
            except Exception:
                option_positions_data = []

        option_exercises_data = (
            fc._parse_option_exercises(report_xml, account_number)
            if report_xml
            else await fc.get_historical_option_exercises(account_number)
        )

        option_incoming = len(option_positions_data) + len(option_exercises_data)
        db.query(Option).filter_by(account_id=broker_account.id).delete()

        synced_count = 0
        skipped_count = 0
        exercises_count = 0
        dropped_no_underlying = 0
        dropped_no_expiry = 0

        def _opt_row_preview(od: Dict[str, Any]) -> Dict[str, Any]:
            return {k: od.get(k) for k in ("symbol", "underlying_symbol", "expiry_date", "strike_price", "open_quantity")}

        for option_data in option_positions_data:
            if not option_data.get("underlying_symbol"):
                dropped_no_underlying += 1
                logger.warning(
                    "IBKR sync: dropping option row for account %s: reason=%s keys=%s raw=%s",
                    broker_account.id,
                    "no_underlying",
                    list(option_data.keys()),
                    _opt_row_preview(option_data),
                )
                continue
            if not option_data.get("expiry_date"):
                dropped_no_expiry += 1
                logger.warning(
                    "IBKR sync: dropping option row for account %s: reason=%s keys=%s raw=%s",
                    broker_account.id,
                    "no_expiry",
                    list(option_data.keys()),
                    _opt_row_preview(option_data),
                )
                continue
            try:
                db.add(Option(
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
                ))
                synced_count += 1
            except Exception as exc:
                logger.error("Error creating option position for %s: %s", option_data.get("symbol", "?"), exc)
                skipped_count += 1
                continue

        for exercise_data in option_exercises_data:
            try:
                db.add(Option(
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
                    open_quantity=0,
                    exercise_date=exercise_data.get("exercise_date"),
                    exercise_price=exercise_data.get("exercise_price"),
                    assignment_date=exercise_data.get("assignment_date"),
                    realized_pnl=exercise_data.get("realized_pnl"),
                    total_cost=exercise_data.get("proceeds", 0) - exercise_data.get("commission", 0),
                    commission=exercise_data.get("commission"),
                    currency=exercise_data["currency"],
                    data_source=exercise_data["data_source"],
                ))
                exercises_count += 1
            except Exception as exc:
                logger.error("Error creating option exercise for %s: %s", exercise_data.get("symbol", "?"), exc)
                skipped_count += 1
                continue

        total_synced = synced_count + exercises_count
        if total_synced > 0 and not broker_account.options_enabled:
            broker_account.options_enabled = True

        db.flush()
        logger.info(
            "Options: %d current + %d exercises = %d total, %d skipped",
            synced_count, exercises_count, total_synced, skipped_count,
        )
        out: Dict[str, Any] = {
            "synced": total_synced,
            "current_positions": synced_count,
            "historical_exercises": exercises_count,
            "skipped": skipped_count,
            "options_dropped_unparseable": dropped_unparseable,
            "options_dropped_no_underlying": dropped_no_underlying,
            "options_dropped_no_expiry": dropped_no_expiry,
            "options_dropped_write_error": skipped_count,
        }
        if option_incoming > 0 and total_synced == 0:
            logger.error(
                "IBKR sync: account %s had %d option/exercise rows from API but wrote 0 to DB. "
                "unparseable=%d d_no_und=%d d_no_exp=%d d_write=%d. "
                "This is a silent-fallback violation.",
                broker_account.id,
                option_incoming,
                dropped_unparseable,
                dropped_no_underlying,
                dropped_no_expiry,
                skipped_count,
            )
            out["options_silent_drop"] = True
        return out
    except Exception as exc:
        logger.error("Error syncing option positions: %s", exc)
        return {"error": str(exc)}


async def refresh_prices(db: Session, broker_account: BrokerAccount) -> Dict:
    """Refresh current prices for positions and tax lots."""
    # medallion: allow cross-layer import (bronze -> silver); resolves when app.services.silver.market.market_data_service moves during Phase 0.C
    from app.services.silver.market.market_data_service import quote

    positions = db.query(Position).filter(Position.account_id == broker_account.id).all()
    positions = [p for p in positions if p.quantity != 0 and p.symbol]
    if not positions:
        return {"updated_positions": 0, "updated_tax_lots": 0, "symbols": []}

    unique_symbols = sorted({p.symbol for p in positions if p.symbol})
    price_tasks = [quote.get_current_price(sym) for sym in unique_symbols]
    prices = await asyncio.gather(*price_tasks, return_exceptions=True)

    symbol_to_price = {}
    for sym, price in zip(unique_symbols, prices):
        if isinstance(price, (int, float)) and price > 0:
            symbol_to_price[sym] = float(price)

    updated_positions = 0
    touched_rows: list[Position] = []
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
            touched_rows.append(p)
        except Exception as e:
            logger.warning(
                "refresh_prices: failed updating position metrics for symbol %s: %s",
                getattr(p, "symbol", "?"),
                e,
            )
            continue
    # Server-side day P&L recompute (D141).
    recompute_day_pnl_for_rows(db, touched_rows, "ibkr_refresh_prices")

    lots = db.query(TaxLot).filter(TaxLot.account_id == broker_account.id).all()
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
        except Exception as e:
            logger.warning(
                "refresh_prices: failed updating tax lot metrics for symbol %s: %s",
                getattr(lot, "symbol", "?"),
                e,
            )
            continue

    db.flush()
    return {
        "updated_positions": updated_positions,
        "updated_tax_lots": updated_lots,
        "symbols": list(symbol_to_price.keys()),
    }


async def create_portfolio_snapshot(db: Session, broker_account: BrokerAccount) -> Dict:
    """Create daily portfolio snapshot for tracking."""
    try:
        today = datetime.now(timezone.utc).date()
        existing = (
            db.query(PortfolioSnapshot)
            .filter(
                PortfolioSnapshot.account_id == broker_account.id,
                PortfolioSnapshot.snapshot_date >= datetime.combine(today, datetime.min.time()),
            )
            .first()
        )
        if existing:
            return {"created": False, "reason": "Snapshot already exists for today"}

        positions = db.query(Position).filter(Position.account_id == broker_account.id).all()
        total_value = sum(h.market_value for h in positions)
        unrealized_pnl = sum(h.unrealized_pnl for h in positions)

        options = db.query(Option).filter(
            Option.account_id == broker_account.id,
            Option.open_quantity != 0,
        ).all()
        for opt in options:
            mv = float(opt.current_price or 0) * abs(opt.open_quantity or 0) * (opt.multiplier or 100)
            total_value += mv
            unrealized_pnl += float(opt.unrealized_pnl or 0)

        def _to_float(value):
            if isinstance(value, Decimal):
                return float(value)
            return value

        snapshot = PortfolioSnapshot(
            account_id=broker_account.id,
            snapshot_date=datetime.now(timezone.utc),
            total_value=total_value,
            total_cash=0,
            total_equity_value=total_value,
            unrealized_pnl=unrealized_pnl,
            positions_snapshot=json.dumps([
                {
                    "symbol": h.symbol,
                    "quantity": _to_float(h.quantity),
                    "value": _to_float(h.market_value),
                    "pnl": _to_float(h.unrealized_pnl),
                }
                for h in positions
            ]),
        )
        db.add(snapshot)
        db.flush()
        return {"created": True, "total_value": f"${total_value:,.2f}"}
    except Exception as exc:
        logger.error("Error creating snapshot: %s", exc)
        return {"error": str(exc)}
