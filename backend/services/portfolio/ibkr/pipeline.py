"""IBKR sync pipeline orchestrator.

Replaces the monolithic ``ibkr_sync_service.py`` with a step-based pipeline that
delegates to focused sync modules while preserving the single-commit-at-end pattern.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import BrokerAccount, TaxLot
from backend.models.instrument import Instrument
from backend.models.position import Position
from backend.models.transfer import Transfer
from backend.models.transaction import Transaction as TxModel
from backend.services.clients.ibkr_flexquery_client import IBKRFlexQueryClient
from backend.services.portfolio.account_credentials_service import (
    CredentialsNotFoundError,
    account_credentials_service,
)

from .helpers import serialize_for_json
from .sync_balances import sync_account_balances, sync_margin_interest, sync_transfers
from .sync_greeks import sync_option_greeks_from_gateway
from .sync_positions import (
    create_portfolio_snapshot,
    refresh_prices,
    sync_instruments,
    sync_option_positions,
    sync_positions_from_open_positions,
    sync_positions_from_tax_lots,
    sync_tax_lots,
)
from .sync_transactions import sync_cash_transactions, sync_trades
from .sync_validator import (
    SyncCompletenessStatus,
    validate_completeness,
)

logger = logging.getLogger(__name__)

_DATA_KEYS = ("tax_lots", "trades", "positions", "cash_transactions", "account_balances")


class IBKRSyncService:
    """IBKR-specific service to sync all data to broker-agnostic database models."""

    def __init__(self) -> None:
        self._default_client = IBKRFlexQueryClient()
        self.flexquery_client = self._default_client

    def _get_flexquery_client(
        self, broker_account: BrokerAccount, db: Session
    ) -> IBKRFlexQueryClient:
        try:
            creds = account_credentials_service.get_ibkr_credentials(broker_account.id, db)
            return IBKRFlexQueryClient(token=creds["flex_token"], query_id=creds["query_id"])
        except CredentialsNotFoundError:
            return self._default_client

    # -- public entry points ---------------------------------------------------

    async def sync_comprehensive_portfolio(
        self, account_number: str, db_session: Session | None = None
    ) -> Dict:
        """Run all sync steps in order, committing once at the end."""
        db = db_session or SessionLocal()
        results: Dict = {}
        try:
            logger.info("Starting comprehensive sync for %s", account_number)

            broker_account = (
                db.query(BrokerAccount)
                .filter(BrokerAccount.account_number == account_number)
                .first()
            )
            if not broker_account:
                return {"status": "error", "error": "Broker account not found in database"}

            fc = self._get_flexquery_client(broker_account, db)

            report_xml = await fc.get_full_report(account_number)
            if not report_xml:
                return {"status": "error", "error": "FlexQuery report not available — token or query ID may be invalid."}

            self._log_xml_sections(report_xml, account_number)
            date_range = self._extract_date_range(report_xml)
            if date_range:
                results["data_range_start"] = date_range[0]
                results["data_range_end"] = date_range[1]

            # Step 1 – instruments
            results["instruments"] = await sync_instruments(db, account_number, report_xml, fc)

            # Step 2 – tax lots
            results["tax_lots"] = await sync_tax_lots(db, broker_account, account_number, report_xml, fc)
            logger.info("Tax lots sync result for %s: %s", account_number, results["tax_lots"])

            # Step 3 – option positions
            results["option_positions"] = await sync_option_positions(db, broker_account, account_number, report_xml, fc)

            # Step 4 – trades
            results["trades"] = await sync_trades(db, broker_account, account_number, report_xml, fc)

            # Step 5 – positions (prefer tax-lot-derived; fall back to OpenPositions)
            results["positions"] = await sync_positions_from_tax_lots(db, broker_account)
            if isinstance(results["positions"], dict) and results["positions"].get("synced", 0) == 0:
                results["positions"] = await sync_positions_from_open_positions(
                    db, broker_account, account_number, report_xml, fc
                )

            # Step 5.1 – refresh prices
            try:
                results["price_refresh"] = await refresh_prices(db, broker_account)
            except Exception as exc:
                logger.warning("Price refresh skipped: %s", exc)

            # Step 6 – portfolio snapshot
            results["snapshot"] = await create_portfolio_snapshot(db, broker_account)

            # Step 7 – cash transactions + dividends
            results["cash_transactions"] = await sync_cash_transactions(
                db, broker_account, account_number, report_xml, fc
            )

            # Step 8 – account balances
            results["account_balances"] = await sync_account_balances(
                db, broker_account, account_number, report_xml, fc
            )

            # Step 9 – margin interest
            results["margin_interest"] = await sync_margin_interest(
                db, broker_account, account_number, report_xml, fc
            )

            # Step 10 – transfers
            results["transfers"] = await sync_transfers(
                db, broker_account, account_number, report_xml, fc
            )

            # Step 11 – enrich Greeks
            results["greeks_enrichment"] = await sync_option_greeks_from_gateway(db, broker_account)

            # G22 — Sync completeness validation (no-silent-success).
            # Runs after every sync_* step has had its chance, so we can also
            # detect "section was present in XML but the writer errored".
            completeness = validate_completeness(report_xml, results)
            results["completeness"] = completeness.to_dict()

            # Single commit for the entire pipeline
            db.commit()

            self._refresh_activity_views(db)

            if completeness.status == SyncCompletenessStatus.ERROR:
                error_msg = (
                    "FlexQuery report incomplete: "
                    + "; ".join(
                        w["message"] for w in completeness.warnings
                        if w.get("level") == "error"
                    )
                )
                logger.error("%s (account %s)", error_msg, account_number)
                return {"status": "error", "error": error_msg, **results}

            results["summary"] = self._compute_summary(db, broker_account)

            if completeness.status == SyncCompletenessStatus.PARTIAL:
                results["status"] = "partial"
                logger.warning(
                    "Comprehensive sync PARTIAL for %s: %d required section(s) missing, "
                    "%d total warning(s) (missing_required=%s)",
                    account_number,
                    len(completeness.missing_required),
                    len(completeness.warnings),
                    completeness.missing_required,
                )
            else:
                results["status"] = "success"
                logger.info("Comprehensive sync completed successfully for %s", account_number)
            return results

        except Exception as exc:
            db.rollback()
            logger.error("Error in comprehensive sync: %s", exc)
            return {"status": "error", "error": str(exc)}
        finally:
            if db_session is None:
                db.close()

    async def sync_account_comprehensive(
        self, account_number: str, db_session=None
    ) -> Dict:
        """Adapter for broker-agnostic sync interface."""
        return await self.sync_comprehensive_portfolio(account_number, db_session=db_session)

    # Aliases preserved for tests
    async def _sync_holdings_from_tax_lots(self, db, broker_account):
        return await sync_positions_from_tax_lots(db, broker_account)

    async def _sync_positions(self, db, broker_account):
        return await sync_positions_from_tax_lots(db, broker_account)

    async def _sync_instruments(self, db, account_number):
        return await sync_instruments(db, account_number, None, self.flexquery_client)

    async def _sync_tax_lots_from_flexquery(self, db, broker_account, account_number):
        return await sync_tax_lots(db, broker_account, account_number, None, self.flexquery_client)

    async def _create_portfolio_snapshot(self, db, broker_account):
        return await create_portfolio_snapshot(db, broker_account)

    def normalize_instruments_from_activity(self, db: Session) -> Dict:
        """Uppercase symbols, backfill missing names from transfers/transactions."""
        updated = 0
        try:
            instruments = db.query(Instrument).all()
            sym_to_name: dict[str, str] = {}
            for t in db.query(Transfer).filter(Transfer.symbol.isnot(None)).all():
                sym = (t.symbol or "").strip().upper()
                desc = (t.description or "").strip()
                if sym and desc and len(desc) >= 3:
                    sym_to_name.setdefault(sym, desc)
            for tx in db.query(TxModel).filter(TxModel.symbol.isnot(None)).all():
                sym = (tx.symbol or "").strip().upper()
                desc = (tx.description or "").strip()
                if sym and desc and len(desc) >= 3:
                    sym_to_name.setdefault(sym, desc)

            for inst in instruments:
                normalized = (inst.symbol or "").strip().upper()
                if inst.symbol != normalized:
                    inst.symbol = normalized
                if not inst.name or inst.name.strip().upper() == normalized:
                    candidate = sym_to_name.get(normalized)
                    if candidate:
                        inst.name = candidate
                        updated += 1
            db.flush()
            logger.info("Instruments normalized: %d updated", updated)
            return {"normalized": updated, "total": len(instruments)}
        except Exception as exc:
            logger.warning("Instruments normalization skipped: %s", exc)
            return {"normalized": updated, "error": str(exc)}

    # -- private helpers -------------------------------------------------------

    @staticmethod
    def _extract_date_range(report_xml: str):
        """Return (from_date_str, to_date_str) from the first FlexStatement, or None."""
        try:
            root = ET.fromstring(report_xml)
            stmt = next(root.iter("FlexStatement"), None)
            if stmt is not None:
                from_date = stmt.get("fromDate", "")
                to_date = stmt.get("toDate", "")
                if from_date and to_date:
                    return (from_date, to_date)
        except ET.ParseError:
            pass
        return None

    @staticmethod
    def _log_xml_sections(report_xml: str, account_number: str) -> None:
        try:
            root = ET.fromstring(report_xml)
            for stmt in root.iter("FlexStatement"):
                from_date = stmt.get("fromDate", "?")
                to_date = stmt.get("toDate", "?")
                sections = [child.tag for child in stmt]
                logger.info(
                    "FlexQuery for %s [%s → %s]: %s",
                    account_number, from_date, to_date, sections,
                )
        except ET.ParseError:
            pass

    @staticmethod
    def _refresh_activity_views(db: Session) -> None:
        try:
            from backend.services.portfolio.activity_aggregator import activity_aggregator
            activity_aggregator.refresh_materialized_views(db)
        except Exception as exc:
            logger.warning("Activity MV refresh skipped: %s", exc)

    @staticmethod
    def _total_synced(results: dict) -> int:
        return sum(
            (r.get("synced", 0) if isinstance(r, dict) else 0)
            for k in _DATA_KEYS
            if (r := results.get(k)) is not None
        )

    @staticmethod
    def _compute_summary(db: Session, broker_account: BrokerAccount) -> dict:
        total_cost = sum(
            float(lot.cost_basis or 0)
            for lot in db.query(TaxLot).filter(TaxLot.account_id == broker_account.id).all()
        )
        total_value = sum(
            float(lot.market_value or 0)
            for lot in db.query(TaxLot).filter(TaxLot.account_id == broker_account.id).all()
        )
        if total_cost == 0 and total_value == 0:
            total_cost = float(
                db.query(sa_func.coalesce(sa_func.sum(Position.total_cost_basis), 0))
                .filter(Position.account_id == broker_account.id)
                .scalar() or 0
            )
            total_value = float(
                db.query(sa_func.coalesce(sa_func.sum(Position.market_value), 0))
                .filter(Position.account_id == broker_account.id)
                .scalar() or 0
            )
        total_pnl = total_value - total_cost
        return_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        return {
            "total_cost_basis": f"${total_cost:,.2f}",
            "total_market_value": f"${total_value:,.2f}",
            "unrealized_pnl": f"${total_pnl:,.2f}",
            "return_pct": f"{return_pct:.2f}%",
            "sync_timestamp": datetime.now().isoformat(),
        }


# Global instance — import path: backend.services.portfolio.ibkr.pipeline
ibkr_sync_service = IBKRSyncService()
portfolio_sync_service = ibkr_sync_service  # backward compat alias
