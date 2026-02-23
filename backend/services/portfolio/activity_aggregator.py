from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session


class ActivityAggregatorService:
    """
    Aggregates portfolio activity across trades, transactions, and dividends.
    Prefers materialized views when available; falls back to live UNION ALL.
    """

    def __init__(self) -> None:
        self.activity_mv = "portfolio_activity_mv"
        self.daily_mv = "portfolio_activity_daily_mv"

    def _mv_exists(self, db: Session, name: str) -> bool:
        sql = text(
            "SELECT to_regclass(:name) IS NOT NULL AS exists;"
        )
        row = db.execute(sql, {"name": name}).first()
        return bool(row and row[0])

    def refresh_materialized_views(self, db: Session) -> Dict[str, Any]:
        """Refresh activity materialized views. Safe to call periodically."""
        refreshed = []
        errors: List[str] = []
        for mv in [self.activity_mv, self.daily_mv]:
            try:
                if self._mv_exists(db, mv):
                    db.execute(text(f"REFRESH MATERIALIZED VIEW {mv};"))
                    refreshed.append(mv)
            except Exception as e:
                errors.append(f"{mv}: {e}")
        return {"refreshed": refreshed, "errors": errors}

    def get_activity(
        self,
        db: Session,
        account_id: Optional[int] = None,
        start: Optional[date] = None,
        end: Optional[date] = None,
        symbol: Optional[str] = None,
        category: Optional[str] = None,  # TRADE, DIVIDEND, COMMISSION, etc.
        side: Optional[str] = None,  # BUY / SELL
        limit: int = 200,
        offset: int = 0,
        use_mv: bool = True,
    ) -> Dict[str, Any]:
        """Return unified activity rows and total count."""
        params: Dict[str, Any] = {}
        where_clauses: List[str] = []
        order = "ORDER BY ts DESC"

        if use_mv and self._mv_exists(db, self.activity_mv):
            base = f"SELECT * FROM {self.activity_mv}"
        else:
            base = """
            SELECT * FROM (
                SELECT
                    COALESCE(t.execution_time, t.order_time, t.created_at) AS ts,
                    DATE(COALESCE(t.execution_time, t.order_time, t.created_at)) AS day,
                    t.account_id,
                    t.symbol,
                    'TRADE'::text AS category,
                    t.side AS side,
                    t.quantity::numeric AS quantity,
                    t.price::numeric AS price,
                    t.total_value::numeric AS amount,
                    NULL::numeric AS net_amount,
                    (COALESCE(t.commission,0) + COALESCE(t.fees,0))::numeric AS commission,
                    'trades'::text AS src,
                    t.execution_id AS external_id
                FROM trades t
                WHERE COALESCE(t.execution_time, t.order_time, t.created_at) IS NOT NULL
                  AND (t.status IS NULL OR t.status = 'FILLED')
                UNION ALL
                SELECT
                    COALESCE(tr.transaction_date, tr.trade_date, tr.created_at) AS ts,
                    DATE(COALESCE(tr.transaction_date, tr.trade_date, tr.created_at)) AS day,
                    tr.account_id,
                    tr.symbol,
                    tr.transaction_type::text AS category,
                    CASE WHEN tr.transaction_type::text IN ('BUY','SELL') THEN tr.action ELSE NULL END AS side,
                    tr.quantity::numeric AS quantity,
                    tr.trade_price::numeric AS price,
                    tr.amount::numeric AS amount,
                    tr.net_amount::numeric AS net_amount,
                    COALESCE(tr.commission,0)::numeric AS commission,
                    'transactions'::text AS src,
                    tr.external_id AS external_id
                FROM transactions tr
                UNION ALL
                SELECT
                    COALESCE(d.ex_date, d.pay_date) AS ts,
                    DATE(COALESCE(d.ex_date, d.pay_date)) AS day,
                    d.account_id,
                    d.symbol,
                    'DIVIDEND'::text AS category,
                    NULL::text AS side,
                    d.shares_held::numeric AS quantity,
                    d.dividend_per_share::numeric AS price,
                    d.total_dividend::numeric AS amount,
                    d.net_dividend::numeric AS net_amount,
                    COALESCE(d.tax_withheld,0)::numeric AS commission,
                    'dividends'::text AS src,
                    d.external_id AS external_id
                FROM dividends d
                UNION ALL
                SELECT
                    COALESCE(xf.transfer_date, xf.settle_date, xf.created_at) AS ts,
                    DATE(COALESCE(xf.transfer_date, xf.settle_date, xf.created_at)) AS day,
                    xf.broker_account_id AS account_id,
                    xf.symbol,
                    UPPER(COALESCE(xf.transfer_type::text, 'TRANSFER'))::text AS category,
                    xf.direction::text AS side,
                    xf.quantity::numeric AS quantity,
                    xf.transfer_price::numeric AS price,
                    xf.amount::numeric AS amount,
                    xf.net_cash::numeric AS net_amount,
                    COALESCE(xf.commission, 0)::numeric AS commission,
                    'transfers'::text AS src,
                    xf.transaction_id AS external_id
                FROM transfers xf
                UNION ALL
                SELECT
                    mi.to_date AS ts,
                    DATE(mi.to_date) AS day,
                    mi.broker_account_id AS account_id,
                    NULL AS symbol,
                    'INTEREST'::text AS category,
                    CASE WHEN mi.interest_accrued > 0 THEN 'DEBIT' ELSE 'CREDIT' END AS side,
                    NULL::numeric AS quantity,
                    mi.interest_rate::numeric AS price,
                    mi.interest_accrued::numeric AS amount,
                    mi.interest_accrued::numeric AS net_amount,
                    0::numeric AS commission,
                    'margin_interest'::text AS src,
                    CONCAT('MI-', mi.id)::text AS external_id
                FROM margin_interest mi
            ) u
            """

        if account_id is not None:
            where_clauses.append("account_id = :account_id")
            params["account_id"] = account_id
        if start is not None:
            where_clauses.append("day >= :start")
            params["start"] = start
        if end is not None:
            where_clauses.append("day <= :end")
            params["end"] = end
        if symbol:
            where_clauses.append("UPPER(symbol) = :symbol")
            params["symbol"] = symbol.upper()
        if category:
            where_clauses.append("category = :category")
            params["category"] = category
        if side:
            where_clauses.append("side = :side")
            params["side"] = side.upper()

        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        paging = "LIMIT :limit OFFSET :offset"
        params["limit"] = min(max(limit, 1), 1000)
        params["offset"] = max(offset, 0)

        count_sql = text(f"SELECT COUNT(*) AS total FROM ({base} {where}) AS _count")
        total_result = db.execute(count_sql, {k: v for k, v in params.items() if k not in ("limit", "offset")}).mappings().first()
        total = int(total_result["total"]) if total_result else 0

        sql = text(f"""
            {base}
            {where}
            {order}
            {paging}
        """)
        rows = db.execute(sql, params).mappings().all()
        return {"activity": [dict(r) for r in rows], "total": total}

    def get_daily_summary(
        self,
        db: Session,
        account_id: Optional[int] = None,
        start: Optional[date] = None,
        end: Optional[date] = None,
        symbol: Optional[str] = None,
        use_mv: bool = True,
    ) -> List[Dict[str, Any]]:
        """Return per-day aggregated counts and money in/out."""
        params: Dict[str, Any] = {}
        where_clauses: List[str] = []

        if use_mv and self._mv_exists(db, self.daily_mv):
            base = f"SELECT * FROM {self.daily_mv}"
        else:
            base = """
            SELECT * FROM (
                WITH activity AS (
                    SELECT * FROM (
                        SELECT
                            COALESCE(t.execution_time, t.order_time, t.created_at) AS ts,
                            DATE(COALESCE(t.execution_time, t.order_time, t.created_at)) AS day,
                            t.account_id,
                            t.symbol,
                            'TRADE'::text AS category,
                            t.side AS side,
                            t.quantity::numeric AS quantity,
                            t.price::numeric AS price,
                            t.total_value::numeric AS amount,
                            NULL::numeric AS net_amount,
                            (COALESCE(t.commission,0) + COALESCE(t.fees,0))::numeric AS commission
                        FROM trades t
                        WHERE COALESCE(t.execution_time, t.order_time, t.created_at) IS NOT NULL
                          AND (t.status IS NULL OR t.status = 'FILLED')
                        UNION ALL
                        SELECT
                            COALESCE(tr.transaction_date, tr.trade_date, tr.created_at) AS ts,
                            DATE(COALESCE(tr.transaction_date, tr.trade_date, tr.created_at)) AS day,
                            tr.account_id,
                            tr.symbol,
                            tr.transaction_type::text AS category,
                            CASE WHEN tr.transaction_type::text IN ('BUY','SELL') THEN tr.action ELSE NULL END AS side,
                            tr.quantity::numeric AS quantity,
                            tr.trade_price::numeric AS price,
                            tr.amount::numeric AS amount,
                            tr.net_amount::numeric AS net_amount,
                            COALESCE(tr.commission,0)::numeric AS commission
                        FROM transactions tr
                        UNION ALL
                        SELECT
                            COALESCE(d.ex_date, d.pay_date) AS ts,
                            DATE(COALESCE(d.ex_date, d.pay_date)) AS day,
                            d.account_id,
                            d.symbol,
                            'DIVIDEND'::text AS category,
                            NULL::text AS side,
                            d.shares_held::numeric AS quantity,
                            d.dividend_per_share::numeric AS price,
                            d.total_dividend::numeric AS amount,
                            d.net_dividend::numeric AS net_amount,
                            COALESCE(d.tax_withheld,0)::numeric AS commission
                        FROM dividends d
                        UNION ALL
                        SELECT
                            COALESCE(xf.transfer_date, xf.settle_date, xf.created_at) AS ts,
                            DATE(COALESCE(xf.transfer_date, xf.settle_date, xf.created_at)) AS day,
                            xf.broker_account_id AS account_id,
                            xf.symbol,
                            UPPER(COALESCE(xf.transfer_type::text, 'TRANSFER'))::text AS category,
                            xf.direction::text AS side,
                            xf.quantity::numeric AS quantity,
                            xf.transfer_price::numeric AS price,
                            xf.amount::numeric AS amount,
                            xf.net_cash::numeric AS net_amount,
                            COALESCE(xf.commission, 0)::numeric AS commission
                        FROM transfers xf
                        UNION ALL
                        SELECT
                            mi.to_date AS ts,
                            DATE(mi.to_date) AS day,
                            mi.broker_account_id AS account_id,
                            NULL AS symbol,
                            'INTEREST'::text AS category,
                            CASE WHEN mi.interest_accrued > 0 THEN 'DEBIT' ELSE 'CREDIT' END AS side,
                            NULL::numeric AS quantity,
                            mi.interest_rate::numeric AS price,
                            mi.interest_accrued::numeric AS amount,
                            mi.interest_accrued::numeric AS net_amount,
                            0::numeric AS commission
                        FROM margin_interest mi
                    ) u
                )
                SELECT
                    day,
                    account_id,
                    COUNT(*) FILTER (WHERE category = 'TRADE') AS trade_count,
                    COUNT(*) FILTER (WHERE category = 'TRADE' AND UPPER(COALESCE(side,'-')) = 'BUY') AS buy_count,
                    COUNT(*) FILTER (WHERE category = 'TRADE' AND UPPER(COALESCE(side,'-')) = 'SELL') AS sell_count,
                    COALESCE(SUM(quantity) FILTER (WHERE category = 'TRADE' AND UPPER(COALESCE(side,'-')) = 'BUY'), 0) AS buy_qty,
                    COALESCE(SUM(quantity) FILTER (WHERE category = 'TRADE' AND UPPER(COALESCE(side,'-')) = 'SELL'), 0) AS sell_qty,
                    COALESCE(SUM(COALESCE(net_amount, amount)) FILTER (
                        WHERE (category = 'TRADE' AND UPPER(COALESCE(side,'-')) = 'SELL')
                           OR category IN ('DIVIDEND','BROKER_INTEREST_RECEIVED','TAX_REFUND','DEPOSIT')
                    ), 0) AS money_in,
                    COALESCE(SUM(ABS(COALESCE(net_amount, amount))) FILTER (
                        WHERE (category = 'TRADE' AND UPPER(COALESCE(side,'-')) = 'BUY')
                           OR category IN ('COMMISSION','OTHER_FEE','BROKER_INTEREST_PAID','WITHDRAWAL','TRANSFER')
                    ), 0) AS money_out
                FROM activity
                GROUP BY day, account_id
            ) s
            """

        if account_id is not None:
            where_clauses.append("account_id = :account_id")
            params["account_id"] = account_id
        if start is not None:
            where_clauses.append("day >= :start")
            params["start"] = start
        if end is not None:
            where_clauses.append("day <= :end")
            params["end"] = end
        if symbol:
            where_clauses.append("UPPER(symbol) = :symbol")
            params["symbol"] = symbol.upper()

        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        order = "ORDER BY day DESC"
        # Apply WHERE to an outer SELECT when not using MVs to avoid syntax errors after GROUP BY
        if use_mv and self._mv_exists(db, self.daily_mv):
            sql = text(f"{base} {where} {order}")
        else:
            sql = text(f"{base} {where} {order}")
        rows = db.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]


activity_aggregator = ActivityAggregatorService()


