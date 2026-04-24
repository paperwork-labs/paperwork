"""Historical IBKR import service (Flex XML + CSV activity statements).

medallion: bronze
"""

from __future__ import annotations

import csv
import io
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from backend.models.broker_account import BrokerAccount
from backend.models.historical_import_run import (
    HistoricalImportRun,
    HistoricalImportSource,
    HistoricalImportStatus,
)
from backend.models.position import Position, PositionStatus, PositionType
from backend.models.trade import Trade
from backend.models.transaction import Transaction, TransactionType
from backend.services.clients.ibkr_flexquery_client import IBKRFlexQueryClient
from backend.services.portfolio.account_credentials_service import (
    CredentialsNotFoundError,
    account_credentials_service,
)

logger = logging.getLogger(__name__)

HISTORICAL_BACKFILL_SOURCE = "historical_backfill"


@dataclass(frozen=True)
class ParsedTradeRecord:
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    executed_at: datetime
    execution_id: str


def build_year_chunks(start: date, end: date) -> List[tuple[date, date]]:
    chunks: List[tuple[date, date]] = []
    current = start
    while current <= end:
        chunk_end = min(end, date(current.year, 12, 31))
        chunks.append((current, chunk_end))
        current = date(current.year + 1, 1, 1)
    return chunks


class HistoricalImportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_run(
        self,
        *,
        user_id: int,
        account: BrokerAccount,
        source: HistoricalImportSource,
        date_from: Optional[date],
        date_to: Optional[date],
    ) -> HistoricalImportRun:
        run = HistoricalImportRun(
            user_id=user_id,
            account_id=account.id,
            source=source,
            status=HistoricalImportStatus.QUEUED,
            date_from=date_from,
            date_to=date_to,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    async def import_flex_xml(
        self,
        *,
        run: HistoricalImportRun,
        account: BrokerAccount,
        date_from: date,
        date_to: date,
    ) -> dict:
        chunks = build_year_chunks(date_from, date_to)
        run.status = HistoricalImportStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        run.chunk_count = len(chunks)
        self.db.commit()

        try:
            client = self._build_client(account)
            raw_xml = await client.get_full_report(
                account.account_number,
                cache_ttl_seconds=0,
            )
            if not raw_xml:
                raise ValueError("FlexQuery report unavailable for historical import")
            parsed_rows = client._parse_trades_from_xml(raw_xml, account.account_number)
            parsed_records = list(self._records_from_xml_rows(parsed_rows))
            records_total = 0
            records_written = 0
            records_skipped = 0
            records_errors = 0
            chunk_summaries: List[dict] = []
            for chunk_start, chunk_end in chunks:
                filtered = self._filter_records_by_date(
                    parsed_records,
                    chunk_start,
                    chunk_end,
                )
                chunk_summary = self._write_records(account, filtered)
                records_total += chunk_summary["records_total"]
                records_written += chunk_summary["written"]
                records_skipped += chunk_summary["skipped"]
                records_errors += chunk_summary["errors"]
                chunk_summaries.append(
                    {
                        "start": chunk_start.isoformat(),
                        "end": chunk_end.isoformat(),
                        **chunk_summary,
                    }
                )

            summary = {
                "records_total": records_total,
                "written": records_written,
                "skipped": records_skipped,
                "errors": records_errors,
            }
            run.records_total = records_total
            run.records_written = records_written
            run.records_skipped = records_skipped
            run.records_errors = records_errors
            run.import_metadata = {"chunks": chunk_summaries}
            run.status = HistoricalImportStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            return summary
        except Exception as exc:
            self.db.rollback()
            run = self.db.get(HistoricalImportRun, run.id)
            if run is not None:
                run.status = HistoricalImportStatus.FAILED
                run.error_message = str(exc)[:1000]
                run.completed_at = datetime.now(timezone.utc)
                self.db.commit()
            raise

    def import_xml_content(
        self,
        *,
        run: HistoricalImportRun,
        account: BrokerAccount,
        xml_content: str,
        date_from: date,
        date_to: date,
    ) -> dict:
        run.status = HistoricalImportStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        run.chunk_count = 1
        self.db.commit()
        try:
            try:
                ET.fromstring(xml_content)
            except ET.ParseError as exc:
                raise ValueError(
                    f"malformed_xml: could not parse uploaded XML ({exc})"
                ) from exc
            client = self._build_client(account)
            parsed = client._parse_trades_from_xml(xml_content, account.account_number)
            filtered = self._filter_records_by_date(
                self._records_from_xml_rows(parsed),
                date_from,
                date_to,
            )
            summary = self._write_records(account, filtered)
            run.records_total = summary["records_total"]
            run.records_written = summary["written"]
            run.records_skipped = summary["skipped"]
            run.records_errors = summary["errors"]
            run.status = HistoricalImportStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            return summary
        except Exception as exc:
            self.db.rollback()
            run = self.db.get(HistoricalImportRun, run.id)
            if run is not None:
                run.status = HistoricalImportStatus.FAILED
                run.error_message = str(exc)[:1000]
                run.completed_at = datetime.now(timezone.utc)
                self.db.commit()
            raise

    def import_csv(
        self,
        *,
        run: HistoricalImportRun,
        account: BrokerAccount,
        csv_content: str,
    ) -> dict:
        run.status = HistoricalImportStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        self.db.commit()
        try:
            records = list(self._records_from_csv(csv_content))
            summary = self._write_records(account, records)
            run.records_total = summary["records_total"]
            run.records_written = summary["written"]
            run.records_skipped = summary["skipped"]
            run.records_errors = summary["errors"]
            run.chunk_count = 1
            run.status = HistoricalImportStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            return summary
        except Exception as exc:
            self.db.rollback()
            run = self.db.get(HistoricalImportRun, run.id)
            if run is not None:
                run.status = HistoricalImportStatus.FAILED
                run.error_message = str(exc)[:1000]
                run.completed_at = datetime.now(timezone.utc)
                self.db.commit()
            raise

    def _write_records(self, account: BrokerAccount, records: Iterable[ParsedTradeRecord]) -> dict:
        batch_flush_size = 500
        written = 0
        skipped = 0
        errors = 0
        records_list = list(records)
        existing_execution_ids = {
            execution_id
            for (execution_id,) in self.db.query(Transaction.execution_id)
            .filter(
                Transaction.account_id == account.id,
                Transaction.execution_id.isnot(None),
            )
            .all()
        }
        pending_flush_count = 0
        for record in records_list:
            try:
                if record.execution_id in existing_execution_ids:
                    skipped += 1
                    continue
                self._create_trade_and_transaction(account, record)
                self._upsert_position(account, record)
                existing_execution_ids.add(record.execution_id)
                written += 1
                pending_flush_count += 1
                if pending_flush_count >= batch_flush_size:
                    self.db.flush()
                    pending_flush_count = 0
            except Exception as exc:
                errors += 1
                logger.warning(
                    "historical_import write failed account=%s symbol=%s exec=%s err=%s",
                    account.account_number,
                    record.symbol,
                    record.execution_id,
                    exc,
                )
        if pending_flush_count > 0:
            self.db.flush()
        total = len(records_list)
        assert written + skipped + errors == total, "counter drift"
        logger.info(
            "historical_import counters account=%s total=%d written=%d skipped=%d errors=%d",
            account.account_number,
            total,
            written,
            skipped,
            errors,
        )
        self.db.commit()
        return {
            "records_total": total,
            "written": written,
            "skipped": skipped,
            "errors": errors,
        }

    def _create_trade_and_transaction(self, account: BrokerAccount, record: ParsedTradeRecord) -> None:
        trade = Trade(
            account_id=account.id,
            symbol=record.symbol,
            side=record.side,
            quantity=record.quantity,
            price=record.price,
            total_value=(record.quantity * record.price),
            commission=Decimal("0"),
            fees=Decimal("0"),
            execution_id=record.execution_id,
            execution_time=record.executed_at,
            status="filled",
            is_opening=record.side == "BUY",
            notes=f"source={HISTORICAL_BACKFILL_SOURCE}",
        )
        amount = float(record.quantity * record.price)
        transaction = Transaction(
            account_id=account.id,
            external_id=f"historical:{record.execution_id}",
            execution_id=record.execution_id,
            symbol=record.symbol,
            transaction_type=(
                TransactionType.BUY if record.side == "BUY" else TransactionType.SELL
            ),
            action="BOT" if record.side == "BUY" else "SLD",
            quantity=float(record.quantity),
            trade_price=float(record.price),
            amount=amount,
            net_amount=amount,
            transaction_date=record.executed_at,
            source=HISTORICAL_BACKFILL_SOURCE,
        )
        self.db.add(trade)
        self.db.add(transaction)

    def _upsert_position(self, account: BrokerAccount, record: ParsedTradeRecord) -> None:
        pos = (
            self.db.query(Position)
            .filter(
                Position.account_id == account.id,
                Position.user_id == account.user_id,
                Position.symbol == record.symbol,
            )
            .first()
        )
        signed_qty = record.quantity if record.side == "BUY" else (record.quantity * Decimal("-1"))
        if pos is None:
            qty = signed_qty
            pos = Position(
                user_id=account.user_id,
                account_id=account.id,
                symbol=record.symbol,
                quantity=qty,
                average_cost=record.price,
                total_cost_basis=qty * record.price,
                status=PositionStatus.CLOSED if abs(qty) == 0 else PositionStatus.OPEN,
                position_type=PositionType.SHORT if qty < 0 else PositionType.LONG,
                notes=f"source={HISTORICAL_BACKFILL_SOURCE}",
            )
            self.db.add(pos)
            return

        new_qty = Decimal(str(pos.quantity or 0)) + signed_qty
        pos.quantity = new_qty
        pos.average_cost = record.price
        pos.total_cost_basis = new_qty * record.price
        pos.status = PositionStatus.CLOSED if abs(new_qty) == 0 else PositionStatus.OPEN
        pos.position_type = PositionType.SHORT if new_qty < 0 else PositionType.LONG
        pos.notes = f"source={HISTORICAL_BACKFILL_SOURCE}"

    def _build_client(self, account: BrokerAccount) -> IBKRFlexQueryClient:
        try:
            creds = account_credentials_service.get_ibkr_credentials(account.id, self.db)
            return IBKRFlexQueryClient(
                token=creds["flex_token"],
                query_id=creds["query_id"],
            )
        except CredentialsNotFoundError:
            return IBKRFlexQueryClient()

    def _records_from_xml_rows(self, rows: Iterable[dict]) -> Iterable[ParsedTradeRecord]:
        for row in rows:
            dt = row.get("execution_time") or row.get("trade_date")
            if not isinstance(dt, datetime):
                continue
            symbol = str(row.get("symbol") or "").upper().strip()
            execution_id = str(row.get("execution_id") or row.get("trade_id") or "").strip()
            if not symbol or not execution_id:
                continue
            side = str(row.get("side") or "BUY").upper()
            qty = Decimal(str(row.get("quantity") or "0"))
            px = Decimal(str(row.get("price") or "0"))
            if qty <= 0 or px <= 0:
                continue
            yield ParsedTradeRecord(
                symbol=symbol,
                side="BUY" if side == "BUY" else "SELL",
                quantity=qty,
                price=px,
                executed_at=dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc),
                execution_id=execution_id,
            )

    def _records_from_csv(self, csv_content: str) -> Iterable[ParsedTradeRecord]:
        reader = csv.DictReader(io.StringIO(csv_content))
        for idx, row in enumerate(reader):
            symbol = str(row.get("Symbol") or row.get("symbol") or "").upper().strip()
            side = str(row.get("Buy/Sell") or row.get("Action") or row.get("action") or "").upper()
            qty_raw = row.get("Quantity") or row.get("quantity")
            price_raw = row.get("TradePrice") or row.get("Price") or row.get("price")
            date_raw = row.get("DateTime") or row.get("Date") or row.get("date")
            if not symbol or not side or not qty_raw or not price_raw or not date_raw:
                continue
            try:
                qty = Decimal(str(qty_raw).replace(",", ""))
                price = Decimal(str(price_raw).replace(",", ""))
                executed_at = datetime.fromisoformat(str(date_raw).replace("Z", "+00:00"))
            except Exception as exc:
                raise ValueError(f"Invalid CSV row {idx + 1}: {exc}") from exc
            execution_id = str(row.get("ExecID") or row.get("execution_id") or f"csv-{idx + 1}").strip()
            if qty <= 0 or price <= 0:
                continue
            yield ParsedTradeRecord(
                symbol=symbol,
                side="BUY" if side in {"BUY", "BOT"} else "SELL",
                quantity=qty,
                price=price,
                executed_at=executed_at if executed_at.tzinfo else executed_at.replace(tzinfo=timezone.utc),
                execution_id=execution_id,
            )

    @staticmethod
    def _filter_records_by_date(
        records: Iterable[ParsedTradeRecord], start: date, end: date
    ) -> List[ParsedTradeRecord]:
        return [
            rec for rec in records if start <= rec.executed_at.date() <= end
        ]
