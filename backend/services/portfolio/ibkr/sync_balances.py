"""Account balance, margin interest, and transfer sync steps for IBKR pipeline."""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy.orm import Session

from backend.models import BrokerAccount
from backend.models.account_balance import AccountBalance
from backend.models.margin_interest import MarginInterest
from backend.models.transfer import Transfer
from backend.services.clients.ibkr_flexquery_client import IBKRFlexQueryClient

from .helpers import logger

_IBKR_TRANSFER_TYPE_MAP = {
    "ACATS": "POSITION",
    "DEP": "CASH",
    "WDA": "CASH",
    "Wire": "CASH",
    "Journal": "POSITION",
    "Internal": "POSITION",
    "DTC": "POSITION",
    "FOP": "POSITION",
    "Dividend": "DIVIDEND",
    "Interest": "INTEREST",
    "Fee": "FEE",
    "Exercise": "OPTION_EXERCISE",
    "Assignment": "OPTION_ASSIGNMENT",
    "Split": "SPLIT",
    "Merger": "MERGER",
    "Spinoff": "SPINOFF",
}


def _map_ibkr_transfer_type(raw_type: str) -> str:
    """Map raw IBKR transfer type to TransferType enum value."""
    return _IBKR_TRANSFER_TYPE_MAP.get(raw_type, "OTHER")


async def sync_account_balances(
    db: Session,
    broker_account: BrokerAccount,
    account_number: str,
    report_xml: str | None,
    fc: IBKRFlexQueryClient,
) -> Dict[str, Any]:
    """Sync account balances from FlexQuery AccountInformation section."""
    try:
        logger.info("Syncing account balances for %s", account_number)

        balances_data = (
            fc._parse_account_information(report_xml, account_number)
            if report_xml
            else await fc.get_account_balances(account_number)
        )

        if not balances_data:
            logger.info("No account balance data found for %s", account_number)
            return {"synced": 0}

        synced_count = 0

        for balance_data in balances_data:
            try:
                existing_balance = (
                    db.query(AccountBalance)
                    .filter(
                        AccountBalance.broker_account_id == broker_account.id,
                        AccountBalance.balance_date == balance_data.get("balance_date"),
                    )
                    .first()
                )

                if not existing_balance:
                    db.add(AccountBalance(
                        user_id=broker_account.user_id,
                        broker_account_id=broker_account.id,
                        balance_date=balance_data.get("balance_date"),
                        balance_type=balance_data.get("balance_type", "DAILY_SNAPSHOT"),
                        base_currency=balance_data.get("base_currency", "USD"),
                        total_cash_value=balance_data.get("total_cash_value", 0),
                        settled_cash=balance_data.get("settled_cash"),
                        available_funds=balance_data.get("available_funds"),
                        cash_balance=balance_data.get("cash_balance"),
                        net_liquidation=balance_data.get("net_liquidation"),
                        gross_position_value=balance_data.get("gross_position_value"),
                        equity=balance_data.get("equity"),
                        previous_day_equity=balance_data.get("previous_day_equity"),
                        buying_power=balance_data.get("buying_power"),
                        initial_margin_req=balance_data.get("initial_margin_req"),
                        maintenance_margin_req=balance_data.get("maintenance_margin_req"),
                        reg_t_equity=balance_data.get("reg_t_equity"),
                        sma=balance_data.get("sma"),
                        unrealized_pnl=balance_data.get("unrealized_pnl"),
                        realized_pnl=balance_data.get("realized_pnl"),
                        daily_pnl=balance_data.get("daily_pnl"),
                        cushion=balance_data.get("cushion"),
                        leverage=balance_data.get("leverage"),
                        lookahead_next_change=balance_data.get("lookahead_next_change"),
                        lookahead_available_funds=balance_data.get("lookahead_available_funds"),
                        lookahead_excess_liquidity=balance_data.get("lookahead_excess_liquidity"),
                        lookahead_init_margin=balance_data.get("lookahead_init_margin"),
                        lookahead_maint_margin=balance_data.get("lookahead_maint_margin"),
                        accrued_cash=balance_data.get("accrued_cash"),
                        accrued_dividend=balance_data.get("accrued_dividend"),
                        accrued_interest=balance_data.get("accrued_interest"),
                        exchange_rate=balance_data.get("exchange_rate", 1),
                        data_source=balance_data.get("data_source", "OFFICIAL_STATEMENT"),
                        account_alias=balance_data.get("account_alias", ""),
                        customer_type=balance_data.get("customer_type", ""),
                        account_code=balance_data.get("account_code", ""),
                    ))
                    synced_count += 1
                nlv = balance_data.get("net_liquidation")
                if nlv is not None:
                    broker_account.total_value = Decimal(str(nlv))
                cb = balance_data.get("cash_balance")
                if cb is not None:
                    broker_account.cash_balance = Decimal(str(cb))
            except Exception as exc:
                logger.error("Error processing account balance: %s", exc)
                continue

        db.flush()
        logger.info("Account balances: %d records", synced_count)
        return {"synced": synced_count, "total_processed": len(balances_data)}
    except Exception as exc:
        logger.error("Error syncing account balances: %s", exc)
        return {"error": str(exc)}


async def sync_margin_interest(
    db: Session,
    broker_account: BrokerAccount,
    account_number: str,
    report_xml: str | None,
    fc: IBKRFlexQueryClient,
) -> Dict:
    """Sync margin interest from FlexQuery InterestAccruals section."""
    try:
        logger.info("Syncing margin interest for %s", account_number)

        interest_data = (
            fc._parse_interest_accruals(report_xml, account_number)
            if report_xml
            else await fc.get_margin_interest(account_number)
        )

        if not interest_data:
            logger.info("No margin interest data found for %s", account_number)
            return {"synced": 0}

        synced_count = 0

        for interest_record in interest_data:
            try:
                existing = (
                    db.query(MarginInterest)
                    .filter(
                        MarginInterest.broker_account_id == broker_account.id,
                        MarginInterest.from_date == interest_record.get("from_date"),
                        MarginInterest.to_date == interest_record.get("to_date"),
                    )
                    .first()
                )

                if not existing:
                    db.add(MarginInterest(
                        user_id=broker_account.user_id,
                        broker_account_id=broker_account.id,
                        account_alias=interest_record.get("account_alias", ""),
                        from_date=interest_record.get("from_date"),
                        to_date=interest_record.get("to_date"),
                        starting_balance=interest_record.get("starting_balance", 0.0),
                        interest_accrued=interest_record.get("interest_accrued", 0.0),
                        accrual_reversal=interest_record.get("accrual_reversal", 0.0),
                        ending_balance=interest_record.get("ending_balance", 0.0),
                        interest_rate=interest_record.get("interest_rate"),
                        daily_rate=interest_record.get("daily_rate"),
                        currency=str(interest_record.get("currency", "USD"))[:10],
                        fx_rate_to_base=interest_record.get("fx_rate_to_base", 1.0),
                        interest_type=interest_record.get("interest_type", "MARGIN"),
                        description=interest_record.get("description", ""),
                        data_source="ibkr_flexquery",
                    ))
                    synced_count += 1
            except Exception as exc:
                logger.error("Error processing margin interest record: %s", exc)
                continue

        db.flush()
        logger.info("Margin interest: %d records", synced_count)
        return {"synced": synced_count, "total_processed": len(interest_data)}
    except Exception as exc:
        logger.error("Error syncing margin interest: %s", exc)
        return {"error": str(exc)}


async def sync_transfers(
    db: Session,
    broker_account: BrokerAccount,
    account_number: str,
    report_xml: str | None,
    fc: IBKRFlexQueryClient,
) -> Dict:
    """Sync transfers from FlexQuery Transfers section."""
    try:
        logger.info("Syncing transfers for %s", account_number)

        transfers_data = (
            fc._parse_transfers(report_xml, account_number)
            if report_xml
            else await fc.get_transfers(account_number)
        )

        if not transfers_data:
            logger.info("No transfer data found for %s", account_number)
            return {"synced": 0}

        synced_count = 0

        for transfer_data in transfers_data:
            try:
                raw_txn_id = transfer_data.get("transaction_id", "")
                existing = None
                if raw_txn_id:
                    existing = (
                        db.query(Transfer)
                        .filter(
                            Transfer.broker_account_id == broker_account.id,
                            Transfer.transaction_id == raw_txn_id,
                        )
                        .first()
                    )

                if not existing:
                    txn_id = raw_txn_id if raw_txn_id else None
                    db.add(Transfer(
                        user_id=broker_account.user_id,
                        broker_account_id=broker_account.id,
                        transaction_id=txn_id,
                        client_reference=transfer_data.get("client_reference", ""),
                        transfer_date=transfer_data.get("transfer_date"),
                        settle_date=transfer_data.get("settle_date"),
                        transfer_type=_map_ibkr_transfer_type(transfer_data.get("transfer_type", "")),
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
                        external_reference=transfer_data.get("external_reference", ""),
                        data_source="ibkr_flexquery",
                    ))
                    synced_count += 1
            except Exception as exc:
                logger.error("Error processing transfer record: %s", exc)
                continue

        db.flush()
        logger.info("Transfers: %d records", synced_count)
        return {"synced": synced_count, "total_processed": len(transfers_data)}
    except Exception as exc:
        logger.error("Error syncing transfers: %s", exc)
        return {"error": str(exc)}
