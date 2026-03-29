"""Cash transaction, dividend, and trade sync steps for IBKR pipeline."""

import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from statistics import median
from typing import Dict

from sqlalchemy.orm import Session

from backend.models import BrokerAccount, Trade, Transaction
from backend.models.position import Position
from backend.models.transaction import Dividend, TransactionSyncStatus, TransactionType
from backend.services.clients.ibkr_flexquery_client import IBKRFlexQueryClient

from .helpers import logger, safe_float, serialize_for_json

IBKR_TO_TX_TYPE = {
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


async def sync_trades(
    db: Session,
    broker_account: BrokerAccount,
    account_number: str,
    report_xml: str | None,
    fc: IBKRFlexQueryClient,
) -> Dict:
    """Sync historical trades from FlexQuery Trades section."""
    try:
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

        def _store_trade(td: dict, status: str) -> None:
            nonlocal synced_count
            exec_id = str(td.get("execution_id") or "").strip() or None
            db.add(Trade(
                account_id=broker_account.id,
                symbol=td.get("symbol"),
                side=td.get("side", "BUY"),
                quantity=Decimal(str(td.get("quantity", 0))),
                price=Decimal(str(td.get("price", 0))),
                total_value=Decimal(str(td.get("total_value", 0))),
                commission=Decimal(str(td.get("commission", 0))),
                fees=Decimal(str(td.get("fees", 0))),
                execution_time=td.get("execution_time") or datetime.utcnow(),
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
            ))
            synced_count += 1

        for td in trades_data:
            try:
                _store_trade(td, "FILLED")
            except Exception as exc:
                logger.error("Error creating trade: %s", exc)

        for td in closed_lots_data:
            try:
                _store_trade(td, "CLOSED_LOT")
            except Exception as exc:
                logger.error("Error creating closed lot: %s", exc)

        for td in wash_sales_data:
            try:
                _store_trade(td, "WASH_SALE")
            except Exception as exc:
                logger.error("Error creating wash sale: %s", exc)

        db.flush()
        logger.info(
            "Trades: %d executions, %d closed lots, %d wash sales",
            len(trades_data), len(closed_lots_data), len(wash_sales_data),
        )
        return {
            "synced": len(trades_data),
            "closed_lots": len(closed_lots_data),
            "wash_sales": len(wash_sales_data),
        }
    except Exception as exc:
        logger.error("Error syncing trades: %s", exc)
        return {"error": str(exc)}


async def sync_cash_transactions(
    db: Session,
    broker_account: BrokerAccount,
    account_number: str,
    report_xml: str | None,
    fc: IBKRFlexQueryClient,
) -> Dict:
    """Sync cash transactions including dividends from FlexQuery."""
    try:
        logger.info("Syncing cash transactions for %s", account_number)

        transactions_data = (
            fc._parse_cash_transactions(report_xml, account_number)
            if report_xml
            else await fc.get_cash_transactions(account_number)
        )

        if not transactions_data:
            logger.warning(
                "No cash transactions for %s — verify FlexQuery includes CashTransactions section.",
                account_number,
            )
            return {"synced": 0, "dividends": 0, "note": "FlexQuery returned no CashTransactions section"}

        synced_count = 0
        dividend_count = 0

        for tx_data in transactions_data:
            try:
                tx_type = tx_data.get("transaction_type", "")

                # Handle dividends
                if tx_type in ("Dividends", "Payment In Lieu Of Dividend"):
                    existing_dividend = (
                        db.query(Dividend)
                        .filter(
                            Dividend.account_id == broker_account.id,
                            Dividend.external_id == tx_data.get("external_id", ""),
                        )
                        .first()
                    )
                    if not existing_dividend:
                        ex_date = (
                            tx_data.get("transaction_date")
                            or tx_data.get("settlement_date")
                            or tx_data.get("report_date")
                            or datetime.utcnow().date()
                        )
                        pay_date = (
                            tx_data.get("settlement_date")
                            or tx_data.get("transaction_date")
                            or tx_data.get("report_date")
                        )
                        db.add(Dividend(
                            account_id=broker_account.id,
                            external_id=tx_data.get("external_id", ""),
                            symbol=tx_data.get("symbol", ""),
                            ex_date=ex_date,
                            pay_date=pay_date,
                            dividend_per_share=abs(tx_data.get("amount", 0)) / max(tx_data.get("quantity", 1), 1),
                            shares_held=tx_data.get("quantity", 0),
                            total_dividend=abs(tx_data.get("amount", 0)),
                            tax_withheld=tx_data.get("taxes", 0) or 0,
                            net_dividend=abs(tx_data.get("net_amount", 0)),
                            currency=tx_data.get("currency", "USD"),
                            frequency="UNKNOWN",
                            dividend_type="ORDINARY" if "Dividend" in tx_type else "SPECIAL",
                            source="ibkr_flexquery",
                        ))
                        dividend_count += 1

                mapped_tx_type = IBKR_TO_TX_TYPE.get(tx_type, "OTHER")
                ext_id = tx_data.get("external_id", "")

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

                db.add(Transaction(
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
                        TransactionType[mapped_tx_type]
                        if mapped_tx_type in TransactionType.__members__
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
                    transaction_date=tx_data.get("transaction_date") or tx_data.get("settlement_date"),
                    trade_date=tx_data.get("trade_date"),
                    settlement_date_target=tx_data.get("settlement_date_target"),
                    settlement_date=tx_data.get("settlement_date"),
                    taxes=tx_data.get("taxes"),
                    taxable_amount=tx_data.get("taxable_amount"),
                    taxable_amount_base=tx_data.get("taxable_amount_base"),
                    corporate_action_flag=tx_data.get("corporate_action_flag") or None,
                    corporate_action_id=tx_data.get("corporate_action_id") or None,
                    source="ibkr_flexquery",
                ))
                synced_count += 1
            except Exception as exc:
                logger.error("Error processing cash transaction %s: %s", tx_data.get("external_id", "?"), exc)
                continue

        _enrich_dividend_frequency(db, broker_account)

        try:
            db.add(TransactionSyncStatus(
                account_id=broker_account.id,
                last_sync_date=datetime.utcnow(),
                last_successful_sync=datetime.utcnow(),
                sync_status="completed",
                total_transactions=synced_count,
                total_dividends=dividend_count,
            ))
        except Exception:
            pass

        db.flush()
        logger.info("Cash transactions: %d transactions, %d dividends", synced_count, dividend_count)
        return {
            "synced": synced_count,
            "dividends": dividend_count,
            "total_processed": len(transactions_data),
        }
    except Exception as exc:
        logger.error("Error syncing cash transactions: %s", exc)
        return {"error": str(exc)}


def _enrich_dividend_frequency(db: Session, broker_account: BrokerAccount) -> None:
    """Post-process dividends to infer frequency and fix shares_held."""
    divs_by_symbol: defaultdict[str, list[Dividend]] = defaultdict(list)
    for d in db.query(Dividend).filter(Dividend.account_id == broker_account.id).all():
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
            if (not d.shares_held or d.shares_held <= 1) or (d.dividend_per_share == d.total_dividend):
                p = (
                    db.query(Position)
                    .filter(Position.account_id == broker_account.id, Position.symbol == d.symbol)
                    .first()
                )
                if p and p.quantity:
                    d.shares_held = float(p.quantity)
                    d.dividend_per_share = abs(d.total_dividend) / d.shares_held if d.shares_held else d.dividend_per_share
                    d.net_dividend = d.total_dividend - (d.tax_withheld or 0)
