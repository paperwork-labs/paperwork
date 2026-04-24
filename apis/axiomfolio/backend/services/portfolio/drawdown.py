"""Portfolio drawdown tracking and alerts.

medallion: silver
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.portfolio import PortfolioHistory


class DrawdownAlert:
    """Represents a drawdown alert condition."""

    def __init__(
        self,
        user_id: int,
        account_id: Optional[int],
        current_drawdown_pct: float,
        drawdown_days: int,
        peak_value: Decimal,
        current_value: Decimal,
        alert_level: str,  # "warning", "critical"
    ):
        self.user_id = user_id
        self.account_id = account_id
        self.current_drawdown_pct = current_drawdown_pct
        self.drawdown_days = drawdown_days
        self.peak_value = peak_value
        self.current_value = current_value
        self.alert_level = alert_level


class DrawdownService:
    """Service for tracking portfolio drawdowns."""

    WARNING_THRESHOLD = 5.0  # 5% drawdown triggers warning
    CRITICAL_THRESHOLD = 10.0  # 10% drawdown triggers critical

    def __init__(self, db: Session):
        self.db = db

    def record_daily_snapshot(
        self,
        user_id: int,
        account_id: Optional[int],
        total_value: Decimal,
        cash_value: Decimal,
        positions_value: Decimal,
        as_of: Optional[date] = None,
    ) -> PortfolioHistory:
        """Record a daily portfolio snapshot and compute drawdown metrics."""
        as_of = as_of or date.today()

        # Get previous peak
        prev_record = (
            self.db.query(PortfolioHistory)
            .filter(
                PortfolioHistory.user_id == user_id,
                PortfolioHistory.account_id == account_id,
                PortfolioHistory.as_of_date < as_of,
            )
            .order_by(PortfolioHistory.as_of_date.desc())
            .first()
        )

        # Compute peak value
        if prev_record and prev_record.peak_value:
            peak_value = max(prev_record.peak_value, total_value)
        else:
            peak_value = total_value

        # Compute drawdown
        if peak_value > 0:
            drawdown_pct = float((peak_value - total_value) / peak_value * 100)
        else:
            drawdown_pct = 0.0

        # Compute drawdown days
        if drawdown_pct > 0 and prev_record:
            if prev_record.drawdown_pct and prev_record.drawdown_pct > 0:
                drawdown_days = (prev_record.drawdown_days or 0) + 1
            else:
                drawdown_days = 1
        else:
            drawdown_days = 0

        # Upsert the record
        existing = (
            self.db.query(PortfolioHistory)
            .filter(
                PortfolioHistory.user_id == user_id,
                PortfolioHistory.account_id == account_id,
                PortfolioHistory.as_of_date == as_of,
            )
            .first()
        )

        if existing:
            existing.total_value = total_value
            existing.cash_value = cash_value
            existing.positions_value = positions_value
            existing.peak_value = peak_value
            existing.drawdown_pct = drawdown_pct
            existing.drawdown_days = drawdown_days
            record = existing
        else:
            record = PortfolioHistory(
                user_id=user_id,
                account_id=account_id,
                as_of_date=as_of,
                total_value=total_value,
                cash_value=cash_value,
                positions_value=positions_value,
                peak_value=peak_value,
                drawdown_pct=drawdown_pct,
                drawdown_days=drawdown_days,
            )
            self.db.add(record)

        self.db.flush()
        return record

    def check_alerts(self, user_id: int) -> list[DrawdownAlert]:
        """Check for drawdown alerts for a user."""
        alerts = []

        # Latest row per account. SQL NULL = NULL is unknown, so NULL account_id
        # must be queried separately from non-NULL keys.
        latest_records: list[PortfolioHistory] = []

        subq = (
            self.db.query(
                PortfolioHistory.account_id,
                func.max(PortfolioHistory.as_of_date).label("max_date"),
            )
            .filter(
                PortfolioHistory.user_id == user_id,
                PortfolioHistory.account_id.isnot(None),
            )
            .group_by(PortfolioHistory.account_id)
            .subquery()
        )

        latest_records.extend(
            self.db.query(PortfolioHistory)
            .join(
                subq,
                (PortfolioHistory.account_id == subq.c.account_id)
                & (PortfolioHistory.as_of_date == subq.c.max_date),
            )
            .filter(PortfolioHistory.user_id == user_id)
            .all()
        )

        null_bucket_max = (
            self.db.query(func.max(PortfolioHistory.as_of_date))
            .filter(
                PortfolioHistory.user_id == user_id,
                PortfolioHistory.account_id.is_(None),
            )
            .scalar()
        )
        if null_bucket_max is not None:
            null_row = (
                self.db.query(PortfolioHistory)
                .filter(
                    PortfolioHistory.user_id == user_id,
                    PortfolioHistory.account_id.is_(None),
                    PortfolioHistory.as_of_date == null_bucket_max,
                )
                .first()
            )
            if null_row is not None:
                latest_records.append(null_row)

        for record in latest_records:
            if record.drawdown_pct is None:
                continue

            if record.drawdown_pct >= self.CRITICAL_THRESHOLD:
                alert_level = "critical"
            elif record.drawdown_pct >= self.WARNING_THRESHOLD:
                alert_level = "warning"
            else:
                continue

            alerts.append(
                DrawdownAlert(
                    user_id=user_id,
                    account_id=record.account_id,
                    current_drawdown_pct=record.drawdown_pct,
                    drawdown_days=record.drawdown_days or 0,
                    peak_value=record.peak_value or Decimal(0),
                    current_value=record.total_value,
                    alert_level=alert_level,
                )
            )

        return alerts

    def get_drawdown_history(
        self,
        user_id: int,
        account_id: Optional[int] = None,
        days: int = 90,
    ) -> list[PortfolioHistory]:
        """Get drawdown history for charting."""
        cutoff = date.today() - timedelta(days=days)

        query = self.db.query(PortfolioHistory).filter(
            PortfolioHistory.user_id == user_id,
            PortfolioHistory.as_of_date >= cutoff,
        )

        if account_id is not None:
            query = query.filter(PortfolioHistory.account_id == account_id)

        return query.order_by(PortfolioHistory.as_of_date).all()
