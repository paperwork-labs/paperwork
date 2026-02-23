"""add activity materialized views

Revision ID: 9b2a1a7a3a3f
Revises: c0b73efcdaeb
Create Date: 2025-11-16
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "9b2a1a7a3a3f"
down_revision = "3e9ac1f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Unified activity MV (with COALESCE fallbacks and transfers).
    # Table/column names are fixed; do not interpolate user-controlled values into this SQL.
    try:
        op.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS portfolio_activity_mv AS
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
            NULL::text AS side,
            xf.quantity::numeric AS quantity,
            NULL::numeric AS price,
            xf.amount::numeric AS amount,
            xf.net_cash::numeric AS net_amount,
            0::numeric AS commission,
            'transfers'::text AS src,
            xf.external_reference AS external_id
        FROM transfers xf;
            """
        )
        # Helpful indexes
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_day ON portfolio_activity_mv (day);"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_ts ON portfolio_activity_mv (ts DESC);"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_account ON portfolio_activity_mv (account_id);"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_symbol ON portfolio_activity_mv (symbol);"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_category ON portfolio_activity_mv (category);"
        )
    except Exception:
        # Underlying tables may not exist yet in a fresh environment; skip view creation.
        return

    # Daily summary MV
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS portfolio_activity_daily_mv AS
        WITH a AS (
            SELECT * FROM portfolio_activity_mv
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
        FROM a
        GROUP BY day, account_id;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_activity_daily_day ON portfolio_activity_daily_mv (day DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_activity_daily_account ON portfolio_activity_daily_mv (account_id);")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS portfolio_activity_daily_mv;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS portfolio_activity_mv;")


