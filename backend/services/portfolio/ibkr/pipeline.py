"""IBKR sync pipeline orchestrator.

Replaces the monolithic ``ibkr_sync_service.py`` with a step-based pipeline that
delegates to focused sync modules while preserving the single-commit-at-end pattern.

Medallion layer: bronze. See docs/ARCHITECTURE.md and D127.

medallion: bronze
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func as sa_func
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import BrokerAccount, TaxLot, Trade
from backend.models.broker_account import AccountType
from backend.models.instrument import Instrument
from backend.models.option_tax_lot import OptionTaxLot
from backend.models.position import Position
from backend.models.transfer import Transfer
from backend.models.transaction import Transaction as TxModel
from backend.services.clients.ibkr_flexquery_client import IBKRFlexQueryClient
# medallion: allow cross-layer import (bronze -> silver); resolves when backend.services.portfolio.account_type_resolver moves during Phase 0.C
from backend.services.portfolio.account_type_resolver import resolve_account_type
# medallion: allow cross-layer import (bronze -> silver); resolves when backend.services.portfolio.account_credentials_service moves during Phase 0.C
from backend.services.portfolio.account_credentials_service import (
    CredentialsNotFoundError,
    account_credentials_service,
)
# medallion: allow cross-layer import (bronze -> silver); resolves when backend.services.portfolio.closing_lot_matcher moves during Phase 0.C
from backend.services.portfolio.closing_lot_matcher import (
    MatchResult,
    reconcile_closing_lots,
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
            account_discovery = self._discover_accounts_from_report(
                db, broker_account, report_xml
            )
            if account_discovery["created"]:
                logger.info(
                    "IBKR account auto-discovery created %d accounts for user=%s",
                    len(account_discovery["created"]),
                    broker_account.user_id,
                )
            if account_discovery["warnings"]:
                logger.warning(
                    "IBKR account-type resolver emitted %d warning(s): %s",
                    len(account_discovery["warnings"]),
                    account_discovery["warnings"],
                )
            results["account_discovery"] = account_discovery
            results["account_type_warnings"] = account_discovery["warnings"]
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

            # Step 12 — Closing-lot reconciliation (equity CLOSED_LOT + option
            # OptionTaxLot). FlexQuery already emits CLOSED_LOT rows for
            # equities, but option tax lots live in ``option_tax_lots`` and
            # are populated exclusively by the FIFO matcher. Running the
            # matcher broker-agnostically means IBKR option closes now
            # light up the Tax Center the same way Schwab/TT will. See D140.
            _run_closing_lot_reconciliation(db, broker_account, results)

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
    def _discover_accounts_from_report(
        db: Session, seed_account: BrokerAccount, report_xml: str
    ) -> Dict[str, List]:
        """Create/update IBKR accounts discovered across all FlexStatement blocks."""
        created: List[str] = []
        updated: List[str] = []
        warnings: List[dict] = []
        try:
            root = ET.fromstring(report_xml)
        except ET.ParseError as exc:
            logger.warning("Skipping account auto-discovery: invalid XML: %s", exc)
            return {"created": created, "updated": updated, "warnings": warnings}

        for stmt in root.iter("FlexStatement"):
            account_number = (stmt.get("accountId") or "").strip()
            if not account_number:
                continue

            account_info = stmt.find("AccountInformation/AccountInformation")
            ibkr_account_type = None
            if account_info is not None:
                ibkr_account_type = account_info.get("accountType")

            existing = (
                db.query(BrokerAccount)
                .filter(
                    BrokerAccount.user_id == seed_account.user_id,
                    BrokerAccount.broker == seed_account.broker,
                    BrokerAccount.account_number == account_number,
                )
                .first()
            )

            resolved = resolve_account_type(
                broker=seed_account.broker,
                account_number=account_number,
                ibkr_account_type_label=ibkr_account_type,
                oauth_account_type_label=None,
                fallback=AccountType.TAXABLE,
            )
            if resolved.warning:
                warnings.append(resolved.warning)

            if existing is None:
                auto_name = f"IBKR {account_number}"
                db.add(
                    BrokerAccount(
                        user_id=seed_account.user_id,
                        broker=seed_account.broker,
                        account_number=account_number,
                        account_name=auto_name,
                        account_type=resolved.account_type,
                        auto_discovered=True,
                        is_enabled=False,
                        api_credentials_stored=False,
                    )
                )
                created.append(account_number)
                continue

            # Never overwrite manual account_type overrides.
            if existing.auto_discovered and existing.account_type != resolved.account_type:
                existing.account_type = resolved.account_type
                updated.append(account_number)

        return {"created": created, "updated": updated, "warnings": warnings}

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
            # medallion: allow cross-layer import (bronze -> silver); resolves when backend.services.portfolio.activity_aggregator moves during Phase 0.C
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


def _run_closing_lot_reconciliation(
    db: Session, broker_account: BrokerAccount, results: Dict
) -> None:
    """Invoke the broker-agnostic FIFO matcher with Schwab-style savepoint handling.

    IBKR's FlexQuery populates ``Trade.realized_pnl`` for option closes
    directly. The matcher computes its own ``realized_pnl`` on each
    ``OptionTaxLot`` from the opening cost basis. When both exist and
    disagree by more than ``_PNL_DISCREPANCY_TOL`` for a given
    ``closing_trade_id``, we log and count the discrepancy rather than
    raising — per ``no-silent-fallback.mdc``: counter + log, not silent.

    The Schwab equivalent uses ``begin_nested()`` so pytest's outer
    savepoint doesn't collide. We replicate that pattern here.
    """
    try:
        match_result: MatchResult | None = None
        try:
            with db.begin_nested():
                match_result = reconcile_closing_lots(db, broker_account)
        except InvalidRequestError as nested_exc:
            err = str(nested_exc).lower()
            if "closed transaction" in err and "context manager" in err:
                if match_result is None:
                    match_result = reconcile_closing_lots(db, broker_account)
            else:
                raise
        assert match_result is not None

        results["closed_lots_created"] = match_result.created
        results["closed_lots_updated"] = match_result.updated
        results["option_tax_lots_created"] = match_result.option_lots_created
        results["option_tax_lots_updated"] = match_result.option_lots_updated
        results["closed_lots_errors"] = match_result.errors
        results["closed_lots_skipped"] = match_result.skipped
        if match_result.unmatched_quantity > 0:
            logger.warning(
                "IBKR sync: account %s had %s unmatched contract/share quantity "
                "during closing-lot reconciliation (first warning: %s)",
                broker_account.id,
                match_result.unmatched_quantity,
                match_result.warnings[0] if match_result.warnings else "n/a",
            )

        discrepancies = _audit_option_pnl_discrepancies(db, broker_account)
        results["option_pnl_discrepancies"] = discrepancies
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "reconcile_closing_lots failed for user=%s account=%s: %s",
            broker_account.user_id,
            broker_account.account_number,
            exc,
        )
        results["closed_lots_error"] = str(exc)


_PNL_DISCREPANCY_TOL = Decimal("0.01")


def _audit_option_pnl_discrepancies(
    db: Session, broker_account: BrokerAccount
) -> int:
    """Per-closing-trade audit: matcher OptionTaxLot.realized_pnl vs broker realized_pnl.

    Returns the number of closing trades where our FIFO matcher's summed
    ``realized_pnl`` differs from the broker-reported ``Trade.realized_pnl``
    by more than ``_PNL_DISCREPANCY_TOL``. Logged individually at WARN level
    so a prod scrape can reconcile (R34-style). Does not raise; does not
    mutate the matcher output — broker value is the source of truth when
    provided but we surface drift for investigation.
    """
    try:
        rows = (
            db.query(
                OptionTaxLot.closing_trade_id,
                sa_func.coalesce(sa_func.sum(OptionTaxLot.realized_pnl), 0),
            )
            .filter(
                OptionTaxLot.broker_account_id == broker_account.id,
                OptionTaxLot.closing_trade_id.isnot(None),
                OptionTaxLot.realized_pnl.isnot(None),
            )
            .group_by(OptionTaxLot.closing_trade_id)
            .all()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("option-pnl-audit: aggregate query failed: %s", exc)
        return 0

    if not rows:
        return 0

    trade_ids = [r[0] for r in rows]
    broker_pnl_by_id: Dict[int, Decimal] = {
        tid: Decimal(str(pnl or 0))
        for tid, pnl in db.query(Trade.id, Trade.realized_pnl)
        .filter(Trade.id.in_(trade_ids), Trade.realized_pnl.isnot(None))
        .all()
    }

    discrepancies = 0
    for closing_trade_id, matcher_pnl in rows:
        broker_pnl = broker_pnl_by_id.get(closing_trade_id)
        if broker_pnl is None:
            continue
        drift = abs(Decimal(str(matcher_pnl)) - broker_pnl)
        if drift > _PNL_DISCREPANCY_TOL:
            discrepancies += 1
            logger.warning(
                "option-pnl-audit: account_id=%s closing_trade_id=%s "
                "broker_pnl=%s matcher_pnl=%s drift=%s",
                broker_account.id,
                closing_trade_id,
                broker_pnl,
                matcher_pnl,
                drift,
            )
    if discrepancies:
        logger.warning(
            "option-pnl-audit: account_id=%s %d/%d closing trades drifted > %s",
            broker_account.id,
            discrepancies,
            len(rows),
            _PNL_DISCREPANCY_TOL,
        )
    return discrepancies


# Global instance — import path: backend.services.portfolio.ibkr.pipeline
ibkr_sync_service = IBKRSyncService()
portfolio_sync_service = ibkr_sync_service  # backward compat alias
