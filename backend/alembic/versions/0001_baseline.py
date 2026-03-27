"""Frozen baseline — explicit schema as of 2026-03-24.

This migration creates all tables with explicit CREATE TABLE statements.
DO NOT MODIFY this file. New schema changes go in new migrations.

Tables created (46, dependency order):
- app_settings
- cron_schedule
- cron_schedule_audit
- historical_iv
- index_constituents
- institutional_holdings
- instruments
- job_run
- market_data_cache
- market_regime
- market_snapshot
- market_snapshot_history
- strategy_services
- trade_signals
- users
- agent_actions
- broker_accounts
- categories
- instrument_aliases
- market_tracked_plan
- price_data
- strategies
- user_invites
- watchlists
- account_balances
- account_credentials
- account_syncs
- backtest_runs
- dividends
- margin_interest
- options
- orders
- portfolio_history
- portfolio_snapshots
- strategy_executions
- strategy_performance
- strategy_runs
- tax_lots
- trades
- transaction_sync_status
- transactions
- transfers
- positions
- signals
- position_categories
- position_history

Tables NOT created (have dedicated migrations):
- execution_metrics (0004)

Columns NOT included (added by later migrations):
- market_snapshot.{keltner_upper, keltner_lower, ttm_squeeze_on, ttm_momentum, stage_4h, stage_confirmed} (0002, 0003)
- market_snapshot_history.{same columns} (0002, 0003)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('market_only_mode', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('portfolio_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('strategy_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
    )

    op.create_table(
        "cron_schedule",
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('group', sa.String(50), nullable=False),
        sa.Column('task', sa.String(300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('cron', sa.String(100), nullable=False),
        sa.Column('timezone', sa.String(50), nullable=False),
        sa.Column('args_json', sa.JSON(), nullable=True),
        sa.Column('kwargs_json', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('timeout_s', sa.Integer(), nullable=True),
        sa.Column('singleflight', sa.Boolean(), nullable=True),
        sa.Column('render_service_id', sa.String(100), nullable=True),
        sa.Column('render_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('render_sync_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(200), nullable=True),
    )

    op.create_table(
        "cron_schedule_audit",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('schedule_id', sa.String(100), nullable=False),
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('actor', sa.String(200), nullable=False),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index(op.f('idx_audit_schedule_time'), "cron_schedule_audit", ['schedule_id', 'timestamp'], unique=False)
    op.create_index(op.f('ix_cron_schedule_audit_id'), "cron_schedule_audit", ['id'], unique=False)
    op.create_index(op.f('ix_cron_schedule_audit_schedule_id'), "cron_schedule_audit", ['schedule_id'], unique=False)

    op.create_table(
        "historical_iv",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('iv_30d', sa.Float(), nullable=True),
        sa.Column('iv_60d', sa.Float(), nullable=True),
        sa.Column('iv_rank_252', sa.Float(), nullable=True),
        sa.Column('iv_high_252', sa.Float(), nullable=True),
        sa.Column('iv_low_252', sa.Float(), nullable=True),
        sa.Column('hv_20d', sa.Float(), nullable=True),
        sa.Column('hv_60d', sa.Float(), nullable=True),
        sa.Column('iv_hv_spread', sa.Float(), nullable=True),
        sa.UniqueConstraint('symbol', 'date', name='uq_historical_iv_symbol_date'),
    )
    op.create_index(op.f('ix_historical_iv_date'), "historical_iv", ['date'], unique=False)
    op.create_index(op.f('ix_historical_iv_id'), "historical_iv", ['id'], unique=False)
    op.create_index(op.f('ix_historical_iv_symbol'), "historical_iv", ['symbol'], unique=False)
    op.create_index(op.f('ix_historical_iv_symbol_date'), "historical_iv", ['symbol', 'date'], unique=False)

    op.create_table(
        "index_constituents",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('index_name', sa.String(32), nullable=False),
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('sector', sa.String(100), nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('market_cap', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('became_inactive_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.UniqueConstraint('index_name', 'symbol', name='uq_index_symbol'),
    )
    op.create_index(op.f('idx_index_active'), "index_constituents", ['index_name', 'is_active'], unique=False)
    op.create_index(op.f('ix_index_constituents_id'), "index_constituents", ['id'], unique=False)
    op.create_index(op.f('ix_index_constituents_index_name'), "index_constituents", ['index_name'], unique=False)
    op.create_index(op.f('ix_index_constituents_is_active'), "index_constituents", ['is_active'], unique=False)
    op.create_index(op.f('ix_index_constituents_symbol'), "index_constituents", ['symbol'], unique=False)

    op.create_table(
        "institutional_holdings",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('filing_date', sa.Date(), nullable=False),
        sa.Column('period_date', sa.Date(), nullable=False),
        sa.Column('institution_cik', sa.String(20), nullable=False),
        sa.Column('institution_name', sa.String(200), nullable=True),
        sa.Column('shares', sa.BigInteger(), nullable=True),
        sa.Column('value_usd', sa.BigInteger(), nullable=True),
        sa.Column('share_class', sa.String(20), nullable=True),
        sa.Column('change_shares', sa.BigInteger(), nullable=True),
        sa.Column('change_pct', sa.Float(), nullable=True),
        sa.Column('accession_number', sa.String(40), nullable=True),
        sa.UniqueConstraint('symbol', 'filing_date', 'institution_cik', name='uq_institutional_holding_symbol_date_inst'),
    )
    op.create_index(op.f('ix_institutional_holdings_cik'), "institutional_holdings", ['institution_cik'], unique=False)
    op.create_index(op.f('ix_institutional_holdings_filing_date'), "institutional_holdings", ['filing_date'], unique=False)
    op.create_index(op.f('ix_institutional_holdings_id'), "institutional_holdings", ['id'], unique=False)
    op.create_index(op.f('ix_institutional_holdings_institution_cik'), "institutional_holdings", ['institution_cik'], unique=False)
    op.create_index(op.f('ix_institutional_holdings_symbol'), "institutional_holdings", ['symbol'], unique=False)
    op.create_index(op.f('ix_institutional_holdings_symbol_period'), "institutional_holdings", ['symbol', 'period_date'], unique=False)

    op.create_table(
        "instruments",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200), nullable=True),
        sa.Column('instrument_type', postgresql.ENUM('STOCK', 'ETF', 'OPTION', 'FUTURE', 'BOND', 'FOREX', 'CRYPTO', 'INDEX', 'MUTUAL_FUND', name='instrumenttype', create_type=True), nullable=False),
        sa.Column('exchange', postgresql.ENUM('NYSE', 'NASDAQ', 'AMEX', 'CBOE', 'CME', 'ICE', 'OTC', name='exchange', create_type=True), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True),
        sa.Column('is_tradeable', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('tick_size', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('lot_size', sa.Integer(), nullable=True),
        sa.Column('sector', sa.String(50), nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('market_cap', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('underlying_symbol', sa.String(20), nullable=True),
        sa.Column('option_type', sa.String(4), nullable=True),
        sa.Column('strike_price', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('option_style', postgresql.ENUM('AMERICAN', 'EUROPEAN', name='optionstyle', create_type=True), nullable=True),
        sa.Column('multiplier', sa.Integer(), nullable=True),
        sa.Column('cusip', sa.String(9), nullable=True),
        sa.Column('isin', sa.String(12), nullable=True),
        sa.Column('figi', sa.String(12), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('additional_data', sa.JSON(), nullable=True),
        sa.Column('data_source', sa.String(50), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('idx_instruments_expiration'), "instruments", ['expiration_date'], unique=False)
    op.create_index(op.f('idx_instruments_sector'), "instruments", ['sector'], unique=False)
    op.create_index(op.f('idx_instruments_type'), "instruments", ['instrument_type'], unique=False)
    op.create_index(op.f('idx_instruments_underlying'), "instruments", ['underlying_symbol'], unique=False)
    op.create_index(op.f('ix_instruments_exchange'), "instruments", ['exchange'], unique=False)
    op.create_index(op.f('ix_instruments_instrument_type'), "instruments", ['instrument_type'], unique=False)
    op.create_index(op.f('ix_instruments_symbol'), "instruments", ['symbol'], unique=True)

    op.create_table(
        "job_run",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_name', sa.String(100), nullable=False),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('counters', sa.JSON(), nullable=True),
        sa.Column('result_meta', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index(op.f('idx_jobrun_status_time'), "job_run", ['status', 'started_at'], unique=False)
    op.create_index(op.f('idx_jobrun_task_time'), "job_run", ['task_name', 'started_at'], unique=False)
    op.create_index(op.f('ix_job_run_id'), "job_run", ['id'], unique=False)
    op.create_index(op.f('ix_job_run_status'), "job_run", ['status'], unique=False)
    op.create_index(op.f('ix_job_run_task_name'), "job_run", ['task_name'], unique=False)

    op.create_table(
        "market_data_cache",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('data_type', sa.String(50), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('api_source', sa.String(50), nullable=True),
        sa.Column('cache_hits', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
    )
    op.create_index(op.f('idx_expires_at'), "market_data_cache", ['expires_at'], unique=False)
    op.create_index(op.f('idx_symbol_type'), "market_data_cache", ['symbol', 'data_type'], unique=True)

    op.create_table(
        "market_regime",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('as_of_date', sa.DateTime(), nullable=False),
        sa.Column('vix_spot', sa.Float(), nullable=True),
        sa.Column('vix3m_vix_ratio', sa.Float(), nullable=True),
        sa.Column('vvix_vix_ratio', sa.Float(), nullable=True),
        sa.Column('nh_nl', sa.Integer(), nullable=True),
        sa.Column('pct_above_200d', sa.Float(), nullable=True),
        sa.Column('pct_above_50d', sa.Float(), nullable=True),
        sa.Column('score_vix', sa.Float(), nullable=True),
        sa.Column('score_vix3m_vix', sa.Float(), nullable=True),
        sa.Column('score_vvix_vix', sa.Float(), nullable=True),
        sa.Column('score_nh_nl', sa.Float(), nullable=True),
        sa.Column('score_above_200d', sa.Float(), nullable=True),
        sa.Column('score_above_50d', sa.Float(), nullable=True),
        sa.Column('composite_score', sa.Float(), nullable=True),
        sa.Column('regime_state', sa.String(10), nullable=False),
        sa.Column('cash_floor_pct', sa.Float(), nullable=True),
        sa.Column('max_equity_exposure_pct', sa.Float(), nullable=True),
        sa.Column('regime_multiplier', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
    )
    op.create_index(op.f('idx_regime_date'), "market_regime", ['as_of_date'], unique=False)
    op.create_index(op.f('ix_market_regime_as_of_date'), "market_regime", ['as_of_date'], unique=True)
    op.create_index(op.f('ix_market_regime_id'), "market_regime", ['id'], unique=False)

    op.create_table(
        "market_snapshot",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('name', sa.String(200), nullable=True),
        sa.Column('analysis_type', sa.String(50), nullable=False),
        sa.Column('analysis_timestamp', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('as_of_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expiry_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('sector', sa.String(100), nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('sub_industry', sa.String(100), nullable=True),
        sa.Column('atr_value', sa.Float(), nullable=True),
        sa.Column('atr_percent', sa.Float(), nullable=True),
        sa.Column('atr_distance', sa.Float(), nullable=True),
        sa.Column('rsi', sa.Float(), nullable=True),
        sa.Column('sma_5', sa.Float(), nullable=True),
        sa.Column('sma_10', sa.Float(), nullable=True),
        sa.Column('sma_14', sa.Float(), nullable=True),
        sa.Column('sma_21', sa.Float(), nullable=True),
        sa.Column('sma_50', sa.Float(), nullable=True),
        sa.Column('sma_100', sa.Float(), nullable=True),
        sa.Column('sma_150', sa.Float(), nullable=True),
        sa.Column('sma_200', sa.Float(), nullable=True),
        sa.Column('ema_10', sa.Float(), nullable=True),
        sa.Column('macd', sa.Float(), nullable=True),
        sa.Column('macd_signal', sa.Float(), nullable=True),
        sa.Column('macd_histogram', sa.Float(), nullable=True),
        sa.Column('adx', sa.Float(), nullable=True),
        sa.Column('plus_di', sa.Float(), nullable=True),
        sa.Column('minus_di', sa.Float(), nullable=True),
        sa.Column('bollinger_upper', sa.Float(), nullable=True),
        sa.Column('bollinger_lower', sa.Float(), nullable=True),
        sa.Column('bollinger_width', sa.Float(), nullable=True),
        sa.Column('high_52w', sa.Float(), nullable=True),
        sa.Column('low_52w', sa.Float(), nullable=True),
        sa.Column('stoch_rsi', sa.Float(), nullable=True),
        sa.Column('volume_avg_20d', sa.Float(), nullable=True),
        sa.Column('atr_14', sa.Float(), nullable=True),
        sa.Column('atr_30', sa.Float(), nullable=True),
        sa.Column('atrp_14', sa.Float(), nullable=True),
        sa.Column('atrp_30', sa.Float(), nullable=True),
        sa.Column('range_pos_20d', sa.Float(), nullable=True),
        sa.Column('range_pos_50d', sa.Float(), nullable=True),
        sa.Column('range_pos_52w', sa.Float(), nullable=True),
        sa.Column('atrx_sma_21', sa.Float(), nullable=True),
        sa.Column('atrx_sma_50', sa.Float(), nullable=True),
        sa.Column('atrx_sma_100', sa.Float(), nullable=True),
        sa.Column('atrx_sma_150', sa.Float(), nullable=True),
        sa.Column('rs_mansfield_pct', sa.Float(), nullable=True),
        sa.Column('perf_1d', sa.Float(), nullable=True),
        sa.Column('perf_3d', sa.Float(), nullable=True),
        sa.Column('perf_5d', sa.Float(), nullable=True),
        sa.Column('perf_20d', sa.Float(), nullable=True),
        sa.Column('perf_60d', sa.Float(), nullable=True),
        sa.Column('perf_120d', sa.Float(), nullable=True),
        sa.Column('perf_252d', sa.Float(), nullable=True),
        sa.Column('perf_mtd', sa.Float(), nullable=True),
        sa.Column('perf_qtd', sa.Float(), nullable=True),
        sa.Column('perf_ytd', sa.Float(), nullable=True),
        sa.Column('ema_8', sa.Float(), nullable=True),
        sa.Column('ema_21', sa.Float(), nullable=True),
        sa.Column('ema_200', sa.Float(), nullable=True),
        sa.Column('pct_dist_ema8', sa.Float(), nullable=True),
        sa.Column('pct_dist_ema21', sa.Float(), nullable=True),
        sa.Column('pct_dist_ema200', sa.Float(), nullable=True),
        sa.Column('atr_dist_ema8', sa.Float(), nullable=True),
        sa.Column('atr_dist_ema21', sa.Float(), nullable=True),
        sa.Column('atr_dist_ema200', sa.Float(), nullable=True),
        sa.Column('ma_bucket', sa.String(16), nullable=True),
        sa.Column('td_buy_setup', sa.Integer(), nullable=True),
        sa.Column('td_sell_setup', sa.Integer(), nullable=True),
        sa.Column('td_buy_complete', sa.Boolean(), nullable=True),
        sa.Column('td_sell_complete', sa.Boolean(), nullable=True),
        sa.Column('td_buy_countdown', sa.Integer(), nullable=True),
        sa.Column('td_sell_countdown', sa.Integer(), nullable=True),
        sa.Column('td_perfect_buy', sa.Boolean(), nullable=True),
        sa.Column('td_perfect_sell', sa.Boolean(), nullable=True),
        sa.Column('gaps_unfilled_up', sa.Integer(), nullable=True),
        sa.Column('gaps_unfilled_down', sa.Integer(), nullable=True),
        sa.Column('trend_up_count', sa.Integer(), nullable=True),
        sa.Column('trend_down_count', sa.Integer(), nullable=True),
        sa.Column('stage_label', sa.String(10), nullable=True),
        sa.Column('stage_label_5d_ago', sa.String(10), nullable=True),
        sa.Column('current_stage_days', sa.Integer(), nullable=True),
        sa.Column('previous_stage_label', sa.String(10), nullable=True),
        sa.Column('previous_stage_days', sa.Integer(), nullable=True),
        sa.Column('stage_slope_pct', sa.Float(), nullable=True),
        sa.Column('stage_dist_pct', sa.Float(), nullable=True),
        sa.Column('ext_pct', sa.Float(), nullable=True),
        sa.Column('sma150_slope', sa.Float(), nullable=True),
        sa.Column('sma50_slope', sa.Float(), nullable=True),
        sa.Column('ema10_dist_pct', sa.Float(), nullable=True),
        sa.Column('ema10_dist_n', sa.Float(), nullable=True),
        sa.Column('vol_ratio', sa.Float(), nullable=True),
        sa.Column('scan_tier', sa.String(20), nullable=True),
        sa.Column('action_label', sa.String(10), nullable=True),
        sa.Column('regime_state', sa.String(10), nullable=True),
        sa.Column('next_earnings', sa.DateTime(), nullable=True),
        sa.Column('last_earnings', sa.DateTime(), nullable=True),
        sa.Column('pe_ttm', sa.Float(), nullable=True),
        sa.Column('peg_ttm', sa.Float(), nullable=True),
        sa.Column('roe', sa.Float(), nullable=True),
        sa.Column('eps_ttm', sa.Float(), nullable=True),
        sa.Column('revenue_ttm', sa.Float(), nullable=True),
        sa.Column('eps_growth_yoy', sa.Float(), nullable=True),
        sa.Column('eps_growth_qoq', sa.Float(), nullable=True),
        sa.Column('revenue_growth_yoy', sa.Float(), nullable=True),
        sa.Column('revenue_growth_qoq', sa.Float(), nullable=True),
        sa.Column('dividend_yield', sa.Float(), nullable=True),
        sa.Column('beta', sa.Float(), nullable=True),
        sa.Column('analyst_rating', sa.String(50), nullable=True),
        sa.Column('raw_analysis', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('is_valid', sa.Boolean(), nullable=True),
    )
    op.create_index(op.f('idx_analysis_timestamp'), "market_snapshot", ['analysis_timestamp'], unique=False)
    op.create_index(op.f('idx_symbol_analysis_type'), "market_snapshot", ['symbol', 'analysis_type'], unique=False)
    op.create_index(op.f('idx_symbol_analysis_type_ts'), "market_snapshot", ['symbol', 'analysis_type', 'analysis_timestamp'], unique=False)
    op.create_index(op.f('idx_symbol_expiry'), "market_snapshot", ['symbol', 'expiry_timestamp'], unique=False)
    op.create_index(op.f('ix_market_snapshot_id'), "market_snapshot", ['id'], unique=False)
    op.create_index(op.f('ix_market_snapshot_symbol'), "market_snapshot", ['symbol'], unique=False)

    op.create_table(
        "market_snapshot_history",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('analysis_type', sa.String(50), nullable=False),
        sa.Column('as_of_date', sa.DateTime(), nullable=False),
        sa.Column('analysis_timestamp', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('rsi', sa.Float(), nullable=True),
        sa.Column('atr_value', sa.Float(), nullable=True),
        sa.Column('sma_50', sa.Float(), nullable=True),
        sa.Column('macd', sa.Float(), nullable=True),
        sa.Column('macd_signal', sa.Float(), nullable=True),
        sa.Column('macd_histogram', sa.Float(), nullable=True),
        sa.Column('adx', sa.Float(), nullable=True),
        sa.Column('plus_di', sa.Float(), nullable=True),
        sa.Column('minus_di', sa.Float(), nullable=True),
        sa.Column('bollinger_upper', sa.Float(), nullable=True),
        sa.Column('bollinger_lower', sa.Float(), nullable=True),
        sa.Column('bollinger_width', sa.Float(), nullable=True),
        sa.Column('high_52w', sa.Float(), nullable=True),
        sa.Column('low_52w', sa.Float(), nullable=True),
        sa.Column('stoch_rsi', sa.Float(), nullable=True),
        sa.Column('volume_avg_20d', sa.Float(), nullable=True),
        sa.Column('name', sa.String(200), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('sector', sa.String(100), nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('sub_industry', sa.String(100), nullable=True),
        sa.Column('sma_5', sa.Float(), nullable=True),
        sa.Column('sma_10', sa.Float(), nullable=True),
        sa.Column('sma_14', sa.Float(), nullable=True),
        sa.Column('sma_21', sa.Float(), nullable=True),
        sa.Column('sma_100', sa.Float(), nullable=True),
        sa.Column('sma_150', sa.Float(), nullable=True),
        sa.Column('sma_200', sa.Float(), nullable=True),
        sa.Column('ema_10', sa.Float(), nullable=True),
        sa.Column('ema_8', sa.Float(), nullable=True),
        sa.Column('ema_21', sa.Float(), nullable=True),
        sa.Column('ema_200', sa.Float(), nullable=True),
        sa.Column('atr_14', sa.Float(), nullable=True),
        sa.Column('atr_30', sa.Float(), nullable=True),
        sa.Column('atrp_14', sa.Float(), nullable=True),
        sa.Column('atrp_30', sa.Float(), nullable=True),
        sa.Column('atr_distance', sa.Float(), nullable=True),
        sa.Column('atr_percent', sa.Float(), nullable=True),
        sa.Column('range_pos_20d', sa.Float(), nullable=True),
        sa.Column('range_pos_50d', sa.Float(), nullable=True),
        sa.Column('range_pos_52w', sa.Float(), nullable=True),
        sa.Column('atrx_sma_21', sa.Float(), nullable=True),
        sa.Column('atrx_sma_50', sa.Float(), nullable=True),
        sa.Column('atrx_sma_100', sa.Float(), nullable=True),
        sa.Column('atrx_sma_150', sa.Float(), nullable=True),
        sa.Column('rs_mansfield_pct', sa.Float(), nullable=True),
        sa.Column('stage_label', sa.String(10), nullable=True),
        sa.Column('stage_label_5d_ago', sa.String(10), nullable=True),
        sa.Column('current_stage_days', sa.Integer(), nullable=True),
        sa.Column('previous_stage_label', sa.String(10), nullable=True),
        sa.Column('previous_stage_days', sa.Integer(), nullable=True),
        sa.Column('ext_pct', sa.Float(), nullable=True),
        sa.Column('sma150_slope', sa.Float(), nullable=True),
        sa.Column('sma50_slope', sa.Float(), nullable=True),
        sa.Column('ema10_dist_pct', sa.Float(), nullable=True),
        sa.Column('ema10_dist_n', sa.Float(), nullable=True),
        sa.Column('vol_ratio', sa.Float(), nullable=True),
        sa.Column('scan_tier', sa.String(20), nullable=True),
        sa.Column('action_label', sa.String(10), nullable=True),
        sa.Column('regime_state', sa.String(10), nullable=True),
        sa.Column('last_earnings', sa.DateTime(), nullable=True),
        sa.Column('next_earnings', sa.DateTime(), nullable=True),
        sa.Column('pe_ttm', sa.Float(), nullable=True),
        sa.Column('peg_ttm', sa.Float(), nullable=True),
        sa.Column('roe', sa.Float(), nullable=True),
        sa.Column('eps_ttm', sa.Float(), nullable=True),
        sa.Column('revenue_ttm', sa.Float(), nullable=True),
        sa.Column('eps_growth_yoy', sa.Float(), nullable=True),
        sa.Column('eps_growth_qoq', sa.Float(), nullable=True),
        sa.Column('revenue_growth_yoy', sa.Float(), nullable=True),
        sa.Column('revenue_growth_qoq', sa.Float(), nullable=True),
        sa.Column('dividend_yield', sa.Float(), nullable=True),
        sa.Column('beta', sa.Float(), nullable=True),
        sa.Column('analyst_rating', sa.String(50), nullable=True),
        sa.Column('stage_slope_pct', sa.Float(), nullable=True),
        sa.Column('stage_dist_pct', sa.Float(), nullable=True),
        sa.Column('perf_1d', sa.Float(), nullable=True),
        sa.Column('perf_3d', sa.Float(), nullable=True),
        sa.Column('perf_5d', sa.Float(), nullable=True),
        sa.Column('perf_20d', sa.Float(), nullable=True),
        sa.Column('perf_60d', sa.Float(), nullable=True),
        sa.Column('perf_120d', sa.Float(), nullable=True),
        sa.Column('perf_252d', sa.Float(), nullable=True),
        sa.Column('perf_mtd', sa.Float(), nullable=True),
        sa.Column('perf_qtd', sa.Float(), nullable=True),
        sa.Column('perf_ytd', sa.Float(), nullable=True),
        sa.Column('pct_dist_ema8', sa.Float(), nullable=True),
        sa.Column('pct_dist_ema21', sa.Float(), nullable=True),
        sa.Column('pct_dist_ema200', sa.Float(), nullable=True),
        sa.Column('atr_dist_ema8', sa.Float(), nullable=True),
        sa.Column('atr_dist_ema21', sa.Float(), nullable=True),
        sa.Column('atr_dist_ema200', sa.Float(), nullable=True),
        sa.Column('ma_bucket', sa.String(16), nullable=True),
        sa.Column('td_buy_setup', sa.Integer(), nullable=True),
        sa.Column('td_sell_setup', sa.Integer(), nullable=True),
        sa.Column('td_buy_complete', sa.Boolean(), nullable=True),
        sa.Column('td_sell_complete', sa.Boolean(), nullable=True),
        sa.Column('td_buy_countdown', sa.Integer(), nullable=True),
        sa.Column('td_sell_countdown', sa.Integer(), nullable=True),
        sa.Column('td_perfect_buy', sa.Boolean(), nullable=True),
        sa.Column('td_perfect_sell', sa.Boolean(), nullable=True),
        sa.Column('gaps_unfilled_up', sa.Integer(), nullable=True),
        sa.Column('gaps_unfilled_down', sa.Integer(), nullable=True),
        sa.Column('trend_up_count', sa.Integer(), nullable=True),
        sa.Column('trend_down_count', sa.Integer(), nullable=True),
        sa.UniqueConstraint('symbol', 'analysis_type', 'as_of_date', name='uq_symbol_type_asof'),
    )
    op.create_index(op.f('idx_hist_symbol_date'), "market_snapshot_history", ['symbol', 'as_of_date'], unique=False)
    op.create_index(op.f('ix_market_snapshot_history_as_of_date'), "market_snapshot_history", ['as_of_date'], unique=False)
    op.create_index(op.f('ix_market_snapshot_history_id'), "market_snapshot_history", ['id'], unique=False)
    op.create_index(op.f('ix_market_snapshot_history_symbol'), "market_snapshot_history", ['symbol'], unique=False)

    op.create_table(
        "strategy_services",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('service_type', sa.String(50), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('service_module', sa.String(200), nullable=False),
        sa.Column('service_class', sa.String(100), nullable=False),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('complexity', sa.String(20), nullable=False),
        sa.Column('min_capital', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('expected_return_annual', sa.String(50), nullable=True),
        sa.Column('max_drawdown', sa.String(20), nullable=True),
        sa.Column('time_horizon', sa.String(50), nullable=True),
        sa.Column('supported_parameters', sa.JSON(), nullable=True),
        sa.Column('default_parameters', sa.JSON(), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=True),
        sa.Column('requires_approval', sa.Boolean(), nullable=True),
        sa.Column('success_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('avg_return', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.UniqueConstraint('service_type'),
    )

    op.create_table(
        "trade_signals",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('strategy_name', sa.String(50), nullable=False),
        sa.Column('signal_strength', sa.Float(), nullable=True),
        sa.Column('trigger_price', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('recommended_price', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('stop_loss', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('target_price', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('atr_distance', sa.Float(), nullable=True),
        sa.Column('atr_value', sa.Float(), nullable=True),
        sa.Column('ma_alignment', sa.Boolean(), nullable=True),
        sa.Column('price_position_20d', sa.Float(), nullable=True),
        sa.Column('risk_reward_ratio', sa.Float(), nullable=True),
        sa.Column('rsi', sa.Float(), nullable=True),
        sa.Column('macd', sa.Float(), nullable=True),
        sa.Column('adx', sa.Float(), nullable=True),
        sa.Column('volume_ratio', sa.Float(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_processed', sa.Boolean(), nullable=True),
        sa.Column('is_executed', sa.Boolean(), nullable=True),
        sa.Column('execution_price', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('conditions_met', sa.JSON(), nullable=True),
        sa.Column('market_conditions', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f('ix_trade_signals_id'), "trade_signals", ['id'], unique=False)
    op.create_index(op.f('ix_trade_signals_symbol'), "trade_signals", ['symbol'], unique=False)

    op.create_table(
        "users",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('oauth_provider', sa.String(20), nullable=True),
        sa.Column('oauth_id', sa.String(255), nullable=True),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('role', postgresql.ENUM('ADMIN', 'USER', 'READONLY', 'ANALYST', name='userrole', create_type=True), nullable=False, server_default=sa.text("'USER'")),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_approved', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=True),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refresh_token_family', sa.String(36), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=True),
        sa.Column('currency_preference', sa.String(3), nullable=True),
        sa.Column('notification_preferences', sa.JSON(), nullable=True),
        sa.Column('ui_preferences', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.UniqueConstraint('oauth_provider', 'oauth_id', name='uq_user_oauth'),
    )
    op.create_index(op.f('idx_users_email_active'), "users", ['email', 'is_active'], unique=False)
    op.create_index(op.f('idx_users_last_login'), "users", ['last_login'], unique=False)
    op.create_index(op.f('ix_users_email'), "users", ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), "users", ['username'], unique=True)

    op.create_table(
        "agent_actions",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('action_name', sa.String(255), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('context_summary', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('task_id', sa.String(100), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        sa.Column('auto_approved', sa.Boolean(), nullable=True),
        sa.Column('session_id', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['approved_by_id'], ['users.id']),
    )
    op.create_index(op.f('ix_agent_actions_action_type'), "agent_actions", ['action_type'], unique=False)
    op.create_index(op.f('ix_agent_actions_id'), "agent_actions", ['id'], unique=False)
    op.create_index(op.f('ix_agent_actions_risk_level'), "agent_actions", ['risk_level'], unique=False)
    op.create_index(op.f('ix_agent_actions_session_id'), "agent_actions", ['session_id'], unique=False)
    op.create_index(op.f('ix_agent_actions_status'), "agent_actions", ['status'], unique=False)

    op.create_table(
        "broker_accounts",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('broker', postgresql.ENUM('IBKR', 'TASTYTRADE', 'SCHWAB', 'FIDELITY', 'ROBINHOOD', 'UNKNOWN_BROKER', name='brokertype', create_type=True), nullable=False),
        sa.Column('account_number', sa.String(50), nullable=False),
        sa.Column('account_name', sa.String(100), nullable=True),
        sa.Column('account_type', postgresql.ENUM('TAXABLE', 'IRA', 'ROTH_IRA', 'HSA', 'TRUST', 'BUSINESS', name='accounttype', create_type=True), nullable=False),
        sa.Column('status', postgresql.ENUM('ACTIVE', 'INACTIVE', 'CLOSED', 'SUSPENDED', name='accountstatus', create_type=True), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=True),
        sa.Column('api_credentials_stored', sa.Boolean(), nullable=True),
        sa.Column('last_connection_test', sa.DateTime(), nullable=True),
        sa.Column('connection_status', sa.String(50), nullable=True),
        sa.Column('sync_status', postgresql.ENUM('NEVER_SYNCED', 'QUEUED', 'RUNNING', 'COMPLETED', 'SUCCESS', 'FAILED', 'PARTIAL', 'ERROR', name='syncstatus', create_type=True), nullable=True),
        sa.Column('last_sync_attempt', sa.DateTime(), nullable=True),
        sa.Column('last_successful_sync', sa.DateTime(), nullable=True),
        sa.Column('next_sync_scheduled', sa.DateTime(), nullable=True),
        sa.Column('sync_error_message', sa.Text(), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True),
        sa.Column('margin_enabled', sa.Boolean(), nullable=True),
        sa.Column('options_enabled', sa.Boolean(), nullable=True),
        sa.Column('futures_enabled', sa.Boolean(), nullable=True),
        sa.Column('total_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('cash_balance', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('buying_power', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('day_pnl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_pnl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('import_transactions_since', sa.DateTime(), nullable=True),
        sa.Column('keep_historical_data_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(op.f('idx_accounts_number'), "broker_accounts", ['account_number'], unique=False)
    op.create_index(op.f('idx_accounts_sync_status'), "broker_accounts", ['sync_status'], unique=False)
    op.create_index(op.f('idx_accounts_user_broker'), "broker_accounts", ['user_id', 'broker'], unique=False)
    op.create_index(op.f('ix_broker_accounts_account_number'), "broker_accounts", ['account_number'], unique=False)
    op.create_index(op.f('ix_broker_accounts_broker'), "broker_accounts", ['broker'], unique=False)
    op.create_index(op.f('ix_broker_accounts_user_id'), "broker_accounts", ['user_id'], unique=False)

    op.create_table(
        "categories",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('color', sa.String(10), nullable=True),
        sa.Column('parent_category_id', sa.Integer(), nullable=True),
        sa.Column('category_type', sa.String(50), nullable=True),
        sa.Column('target_allocation_pct', sa.Float(), nullable=True),
        sa.Column('min_allocation_pct', sa.Float(), nullable=True),
        sa.Column('max_allocation_pct', sa.Float(), nullable=True),
        sa.Column('rebalance_threshold_pct', sa.Float(), nullable=True),
        sa.Column('auto_rebalance', sa.Boolean(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=True, server_default=sa.text("'0'")),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['parent_category_id'], ['categories.id']),
        sa.UniqueConstraint('user_id', 'name', 'category_type', name='uq_category_user_name_type'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )

    op.create_table(
        "instrument_aliases",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('instrument_id', sa.Integer(), nullable=False),
        sa.Column('alias_symbol', sa.String(50), nullable=False),
        sa.Column('alias_type', sa.String(20), nullable=False),
        sa.Column('source', sa.String(50), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id']),
    )
    op.create_index(op.f('idx_aliases_source'), "instrument_aliases", ['source'], unique=False)
    op.create_index(op.f('idx_aliases_symbol'), "instrument_aliases", ['alias_symbol'], unique=False)
    op.create_index(op.f('ix_instrument_aliases_alias_symbol'), "instrument_aliases", ['alias_symbol'], unique=False)
    op.create_index(op.f('ix_instrument_aliases_instrument_id'), "instrument_aliases", ['instrument_id'], unique=False)

    op.create_table(
        "market_tracked_plan",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=True),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('symbol', name='uq_market_tracked_plan_symbol'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id']),
    )
    op.create_index(op.f('ix_market_tracked_plan_id'), "market_tracked_plan", ['id'], unique=False)
    op.create_index(op.f('ix_market_tracked_plan_symbol'), "market_tracked_plan", ['symbol'], unique=False)
    op.create_index(op.f('ix_market_tracked_plan_updated_by_user_id'), "market_tracked_plan", ['updated_by_user_id'], unique=False)

    op.create_table(
        "price_data",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('instrument_id', sa.Integer(), nullable=True),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('open_price', sa.Float(), nullable=True),
        sa.Column('high_price', sa.Float(), nullable=True),
        sa.Column('low_price', sa.Float(), nullable=True),
        sa.Column('close_price', sa.Float(), nullable=False),
        sa.Column('adjusted_close', sa.Float(), nullable=True),
        sa.Column('volume', sa.Integer(), nullable=True),
        sa.Column('true_range', sa.Float(), nullable=True),
        sa.Column('data_source', sa.String(50), nullable=True),
        sa.Column('interval', sa.String(10), nullable=True),
        sa.Column('is_adjusted', sa.Boolean(), nullable=True),
        sa.Column('is_synthetic_ohlc', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('symbol', 'date', 'interval', name='uq_symbol_date_interval'),
        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id']),
    )
    op.create_index(op.f('idx_date_range'), "price_data", ['date'], unique=False)
    op.create_index(op.f('idx_symbol_date'), "price_data", ['symbol', 'date'], unique=False)
    op.create_index(op.f('idx_symbol_interval_date'), "price_data", ['symbol', 'interval', 'date'], unique=False)
    op.create_index(op.f('ix_price_data_date'), "price_data", ['date'], unique=False)
    op.create_index(op.f('ix_price_data_id'), "price_data", ['id'], unique=False)
    op.create_index(op.f('ix_price_data_instrument_id'), "price_data", ['instrument_id'], unique=False)
    op.create_index(op.f('ix_price_data_symbol'), "price_data", ['symbol'], unique=False)

    op.create_table(
        "strategies",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('strategy_type', postgresql.ENUM('ATR_MATRIX', 'MOMENTUM', 'MEAN_REVERSION', 'BREAKOUT', 'OPTIONS_FLOW', 'EARNINGS_PLAY', 'CUSTOM', name='strategytype', create_type=True), nullable=False),
        sa.Column('status', postgresql.ENUM('DRAFT', 'ACTIVE', 'PAUSED', 'STOPPED', 'ARCHIVED', name='strategystatus', create_type=True), nullable=True),
        sa.Column('execution_mode', postgresql.ENUM('PAPER', 'LIVE', 'BACKTEST', name='executionmode', create_type=True), nullable=True),
        sa.Column('auto_execute', sa.Boolean(), nullable=True),
        sa.Column('universe_filter', sa.JSON(), nullable=True),
        sa.Column('min_market_cap', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('max_market_cap', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('allowed_sectors', sa.JSON(), nullable=True),
        sa.Column('excluded_symbols', sa.JSON(), nullable=True),
        sa.Column('max_positions', sa.Integer(), nullable=True),
        sa.Column('position_size_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('max_position_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('max_risk_per_trade', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('max_portfolio_risk', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('stop_loss_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('take_profit_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('max_holding_days', sa.Integer(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('target_annual_return', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('max_drawdown_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('min_win_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('min_risk_reward_ratio', sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column('run_frequency', sa.String(50), nullable=True),
        sa.Column('run_time', sa.String(10), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_status', postgresql.ENUM('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='runstatus', create_type=True), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('winning_trades', sa.Integer(), nullable=True),
        sa.Column('win_rate_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('total_return_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('max_drawdown_experienced', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('sharpe_ratio', sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column('is_validated', sa.Boolean(), nullable=True),
        sa.Column('validation_errors', sa.JSON(), nullable=True),
        sa.Column('validation_warnings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('started_audit', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_audit', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('modified_by_user_id', sa.Integer(), nullable=True),
        sa.Column('execution_node', sa.String(50), nullable=True),
        sa.Column('audit_metadata', sa.JSON(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.UniqueConstraint('user_id', 'name', name='uq_user_strategy_name'),
        sa.ForeignKeyConstraint(['modified_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
    )
    op.create_index(op.f('idx_next_run'), "strategies", ['next_run_at', 'status'], unique=False)
    op.create_index(op.f('idx_strategy_type'), "strategies", ['strategy_type'], unique=False)
    op.create_index(op.f('idx_user_status'), "strategies", ['user_id', 'status'], unique=False)

    op.create_table(
        "user_invites",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', postgresql.ENUM('ADMIN', 'USER', 'READONLY', 'ANALYST', name='userrole', create_type=False), nullable=False, server_default=sa.text("'READONLY'")),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
    )
    op.create_index(op.f('ix_user_invites_email'), "user_invites", ['email'], unique=True)
    op.create_index(op.f('ix_user_invites_token'), "user_invites", ['token'], unique=True)

    op.create_table(
        "watchlists",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.UniqueConstraint('user_id', 'symbol', name='uq_watchlist_user_symbol'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(op.f('idx_watchlist_user_symbol'), "watchlists", ['user_id', 'symbol'], unique=False)
    op.create_index(op.f('ix_watchlists_id'), "watchlists", ['id'], unique=False)
    op.create_index(op.f('ix_watchlists_symbol'), "watchlists", ['symbol'], unique=False)
    op.create_index(op.f('ix_watchlists_user_id'), "watchlists", ['user_id'], unique=False)

    op.create_table(
        "account_balances",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('broker_account_id', sa.Integer(), nullable=False),
        sa.Column('balance_date', sa.DateTime(), nullable=False),
        sa.Column('balance_type', postgresql.ENUM('REALTIME', 'DAILY_SNAPSHOT', 'MONTHLY_STATEMENT', 'QUARTERLY_REPORT', name='accountbalancetype', create_type=True), nullable=False),
        sa.Column('base_currency', sa.String(10), nullable=False),
        sa.Column('total_cash_value', sa.Float(), nullable=True),
        sa.Column('settled_cash', sa.Float(), nullable=True),
        sa.Column('available_funds', sa.Float(), nullable=True),
        sa.Column('cash_balance', sa.Float(), nullable=True),
        sa.Column('net_liquidation', sa.Float(), nullable=True),
        sa.Column('gross_position_value', sa.Float(), nullable=True),
        sa.Column('equity', sa.Float(), nullable=True),
        sa.Column('previous_day_equity', sa.Float(), nullable=True),
        sa.Column('buying_power', sa.Float(), nullable=True),
        sa.Column('initial_margin_req', sa.Float(), nullable=True),
        sa.Column('maintenance_margin_req', sa.Float(), nullable=True),
        sa.Column('reg_t_equity', sa.Float(), nullable=True),
        sa.Column('sma', sa.Float(), nullable=True),
        sa.Column('unrealized_pnl', sa.Float(), nullable=True),
        sa.Column('realized_pnl', sa.Float(), nullable=True),
        sa.Column('daily_pnl', sa.Float(), nullable=True),
        sa.Column('cushion', sa.Float(), nullable=True),
        sa.Column('leverage', sa.Float(), nullable=True),
        sa.Column('lookahead_next_change', sa.Float(), nullable=True),
        sa.Column('lookahead_available_funds', sa.Float(), nullable=True),
        sa.Column('lookahead_excess_liquidity', sa.Float(), nullable=True),
        sa.Column('lookahead_init_margin', sa.Float(), nullable=True),
        sa.Column('lookahead_maint_margin', sa.Float(), nullable=True),
        sa.Column('accrued_cash', sa.Float(), nullable=True),
        sa.Column('accrued_dividend', sa.Float(), nullable=True),
        sa.Column('accrued_interest', sa.Float(), nullable=True),
        sa.Column('exchange_rate', sa.Float(), nullable=True),
        sa.Column('data_source', sa.String(20), nullable=False),
        sa.Column('account_alias', sa.String(100), nullable=True),
        sa.Column('customer_type', sa.String(50), nullable=True),
        sa.Column('account_code', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['broker_account_id'], ['broker_accounts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )

    op.create_table(
        "account_credentials",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('encrypted_credentials', sa.Text(), nullable=True),
        sa.Column('credential_hash', sa.String(255), nullable=True),
        sa.Column('provider', postgresql.ENUM('IBKR', 'TASTYTRADE', 'SCHWAB', 'FIDELITY', 'ROBINHOOD', 'UNKNOWN_BROKER', name='brokertype', create_type=False), nullable=True),
        sa.Column('credential_type', sa.String(32), nullable=True),
        sa.Column('username_hint', sa.String(255), nullable=True),
        sa.Column('last_refreshed_at', sa.DateTime(), nullable=True),
        sa.Column('refresh_token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('rotation_count', sa.Integer(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['broker_accounts.id']),
        sa.UniqueConstraint('account_id'),
    )

    op.create_table(
        "account_syncs",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('sync_type', sa.String(50), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('status', postgresql.ENUM('NEVER_SYNCED', 'QUEUED', 'RUNNING', 'COMPLETED', 'SUCCESS', 'FAILED', 'PARTIAL', 'ERROR', name='syncstatus', create_type=False), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('positions_synced', sa.Integer(), nullable=True),
        sa.Column('transactions_synced', sa.Integer(), nullable=True),
        sa.Column('new_tax_lots_created', sa.Integer(), nullable=True),
        sa.Column('data_range_start', sa.DateTime(), nullable=True),
        sa.Column('data_range_end', sa.DateTime(), nullable=True),
        sa.Column('sync_trigger', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['broker_accounts.id']),
    )
    op.create_index(op.f('idx_syncs_account_date'), "account_syncs", ['account_id', 'started_at'], unique=False)
    op.create_index(op.f('ix_account_syncs_account_id'), "account_syncs", ['account_id'], unique=False)

    op.create_table(
        "backtest_runs",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('initial_capital', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('data_frequency', sa.String(20), nullable=True),
        sa.Column('data_provider', sa.String(50), nullable=True),
        sa.Column('survivorship_bias_free', sa.Boolean(), nullable=True),
        sa.Column('commission_per_trade', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('slippage_bps', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('market_impact_model', sa.String(50), nullable=True),
        sa.Column('status', postgresql.ENUM('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='runstatus', create_type=False), nullable=False),
        sa.Column('final_portfolio_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_return_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('annualized_return_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('max_drawdown_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('sharpe_ratio', sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('win_rate_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('trades_executed', sa.Integer(), nullable=True),
        sa.Column('signals_generated', sa.Integer(), nullable=True),
        sa.Column('execution_time_seconds', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('memory_usage_mb', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('daily_returns', sa.JSON(), nullable=True),
        sa.Column('portfolio_values', sa.JSON(), nullable=True),
        sa.Column('trade_history', sa.JSON(), nullable=True),
        sa.Column('performance_metrics', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id']),
    )
    op.create_index(op.f('idx_backtest_status_date'), "backtest_runs", ['status', 'created_at'], unique=False)
    op.create_index(op.f('idx_strategy_backtest'), "backtest_runs", ['strategy_id', 'created_at'], unique=False)

    op.create_table(
        "dividends",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('external_id', sa.String(100), nullable=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('ex_date', sa.DateTime(), nullable=False),
        sa.Column('pay_date', sa.DateTime(), nullable=True),
        sa.Column('dividend_per_share', sa.Float(), nullable=False),
        sa.Column('shares_held', sa.Float(), nullable=False),
        sa.Column('total_dividend', sa.Float(), nullable=False),
        sa.Column('tax_withheld', sa.Float(), nullable=True),
        sa.Column('net_dividend', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(10), nullable=True),
        sa.Column('frequency', sa.String(20), nullable=True),
        sa.Column('dividend_type', sa.String(20), nullable=True),
        sa.Column('source', sa.String(50), nullable=True),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['broker_accounts.id']),
    )
    op.create_index(op.f('idx_account_symbol_exdate'), "dividends", ['account_id', 'symbol', 'ex_date'], unique=False)
    op.create_index(op.f('idx_dividends_symbol'), "dividends", ['symbol'], unique=False)
    op.create_index(op.f('idx_ex_date'), "dividends", ['ex_date'], unique=False)
    op.create_index(op.f('idx_pay_date'), "dividends", ['pay_date'], unique=False)

    op.create_table(
        "margin_interest",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('broker_account_id', sa.Integer(), nullable=False),
        sa.Column('account_alias', sa.String(100), nullable=True),
        sa.Column('from_date', sa.Date(), nullable=False),
        sa.Column('to_date', sa.Date(), nullable=False),
        sa.Column('starting_balance', sa.Float(), nullable=True),
        sa.Column('interest_accrued', sa.Float(), nullable=False),
        sa.Column('accrual_reversal', sa.Float(), nullable=True),
        sa.Column('ending_balance', sa.Float(), nullable=True),
        sa.Column('interest_rate', sa.Float(), nullable=True),
        sa.Column('daily_rate', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('fx_rate_to_base', sa.Float(), nullable=True),
        sa.Column('interest_type', sa.String(50), nullable=True),
        sa.Column('description', sa.String(200), nullable=True),
        sa.Column('data_source', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['broker_account_id'], ['broker_accounts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(op.f('ix_margin_interest_from_date'), "margin_interest", ['from_date'], unique=False)
    op.create_index(op.f('ix_margin_interest_to_date'), "margin_interest", ['to_date'], unique=False)

    op.create_table(
        "options",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('account_alias', sa.String(100), nullable=True),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('underlying_symbol', sa.String(50), nullable=True),
        sa.Column('contract_id', sa.String(50), nullable=True),
        sa.Column('strike_price', sa.Float(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=False),
        sa.Column('option_type', sa.String(10), nullable=False),
        sa.Column('multiplier', sa.Float(), nullable=False),
        sa.Column('exercised_quantity', sa.Integer(), nullable=True),
        sa.Column('assigned_quantity', sa.Integer(), nullable=True),
        sa.Column('open_quantity', sa.Integer(), nullable=False),
        sa.Column('current_price', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('underlying_price', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('delta', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('gamma', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('theta', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('vega', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('implied_volatility', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('exercise_date', sa.Date(), nullable=True),
        sa.Column('exercise_price', sa.Float(), nullable=True),
        sa.Column('assignment_date', sa.Date(), nullable=True),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('fx_rate_to_base', sa.Float(), nullable=True),
        sa.Column('unrealized_pnl', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('realized_pnl', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('total_cost', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('commission', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('data_source', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['broker_accounts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('account_id', 'underlying_symbol', 'strike_price', 'expiry_date', 'option_type', name='uq_options_contract_per_account'),
    )
    op.create_index(op.f('idx_options_contract'), "options", ['underlying_symbol', 'strike_price', 'expiry_date', 'option_type'], unique=False)
    op.create_index(op.f('ix_options_account_id'), "options", ['account_id'], unique=False)
    op.create_index(op.f('ix_options_contract_id'), "options", ['contract_id'], unique=False)
    op.create_index(op.f('ix_options_symbol'), "options", ['symbol'], unique=False)

    op.create_table(
        "orders",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('order_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('limit_price', sa.Float(), nullable=True),
        sa.Column('stop_price', sa.Float(), nullable=True),
        sa.Column('filled_quantity', sa.Float(), nullable=True),
        sa.Column('filled_avg_price', sa.Float(), nullable=True),
        sa.Column('account_id', sa.String(100), nullable=True),
        sa.Column('broker_order_id', sa.String(100), nullable=True),
        sa.Column('strategy_id', sa.Integer(), nullable=True),
        sa.Column('signal_id', sa.Integer(), nullable=True),
        sa.Column('position_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('broker_type', sa.String(20), nullable=False),
        sa.Column('estimated_commission', sa.Float(), nullable=True),
        sa.Column('estimated_margin_impact', sa.Float(), nullable=True),
        sa.Column('estimated_equity_with_loan', sa.Float(), nullable=True),
        sa.Column('preview_data', sa.JSON(), nullable=True),
        sa.Column('decision_price', sa.Float(), nullable=True),
        sa.Column('slippage_pct', sa.Float(), nullable=True),
        sa.Column('slippage_dollars', sa.Float(), nullable=True),
        sa.Column('fill_latency_ms', sa.Integer(), nullable=True),
        sa.Column('vwap_at_fill', sa.Float(), nullable=True),
        sa.Column('spread_at_order', sa.Float(), nullable=True),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('created_by', sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(op.f('idx_orders_status_created_at'), "orders", ['status', 'created_at'], unique=False)
    op.create_index(op.f('idx_orders_strategy_id'), "orders", ['strategy_id'], unique=False)
    op.create_index(op.f('idx_orders_symbol_status'), "orders", ['symbol', 'status'], unique=False)
    op.create_index(op.f('idx_orders_user_id'), "orders", ['user_id'], unique=False)
    op.create_index(op.f('ix_orders_broker_order_id'), "orders", ['broker_order_id'], unique=False)
    op.create_index(op.f('ix_orders_id'), "orders", ['id'], unique=False)
    op.create_index(op.f('ix_orders_position_id'), "orders", ['position_id'], unique=False)
    op.create_index(op.f('ix_orders_signal_id'), "orders", ['signal_id'], unique=False)
    op.create_index(op.f('ix_orders_status'), "orders", ['status'], unique=False)
    op.create_index(op.f('ix_orders_strategy_id'), "orders", ['strategy_id'], unique=False)
    op.create_index(op.f('ix_orders_symbol'), "orders", ['symbol'], unique=False)
    op.create_index(op.f('ix_orders_user_id'), "orders", ['user_id'], unique=False)

    op.create_table(
        "portfolio_history",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=True),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('total_value', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('cash_value', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('positions_value', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('peak_value', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('drawdown_pct', sa.Float(), nullable=True),
        sa.Column('drawdown_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['broker_accounts.id']),
        sa.UniqueConstraint('user_id', 'account_id', 'as_of_date', name='uix_portfolio_history_user_account_date'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(op.f('ix_portfolio_history_account_id'), "portfolio_history", ['account_id'], unique=False)
    op.create_index(op.f('ix_portfolio_history_as_of_date'), "portfolio_history", ['as_of_date'], unique=False)
    op.create_index(op.f('ix_portfolio_history_user_id'), "portfolio_history", ['user_id'], unique=False)

    op.create_table(
        "portfolio_snapshots",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_date', sa.DateTime(), nullable=False),
        sa.Column('total_value', sa.Float(), nullable=False),
        sa.Column('total_cash', sa.Float(), nullable=False),
        sa.Column('total_equity_value', sa.Float(), nullable=False),
        sa.Column('unrealized_pnl', sa.Float(), nullable=False),
        sa.Column('realized_pnl', sa.Float(), nullable=True),
        sa.Column('day_pnl', sa.Float(), nullable=True),
        sa.Column('day_pnl_pct', sa.Float(), nullable=True),
        sa.Column('beta', sa.Float(), nullable=True),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.Column('volatility', sa.Float(), nullable=True),
        sa.Column('buying_power', sa.Float(), nullable=True),
        sa.Column('margin_used', sa.Float(), nullable=True),
        sa.Column('margin_available', sa.Float(), nullable=True),
        sa.Column('positions_snapshot', sa.Text(), nullable=True),
        sa.Column('sector_allocation', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['account_id'], ['broker_accounts.id']),
    )
    op.create_index(op.f('idx_account_date'), "portfolio_snapshots", ['account_id', 'snapshot_date'], unique=False)
    op.create_index(op.f('idx_snapshot_date'), "portfolio_snapshots", ['snapshot_date'], unique=False)

    op.create_table(
        "strategy_executions",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('brokerage', sa.String(20), nullable=False),
        sa.Column('account_number', sa.String(50), nullable=True),
        sa.Column('allocated_capital', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('current_capital', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('profit_target_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('stop_loss_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('reinvest_profit_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('is_automated', sa.Boolean(), nullable=True),
        sa.Column('max_positions', sa.Integer(), nullable=True),
        sa.Column('position_size_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('total_pnl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_pnl_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('winning_trades', sa.Integer(), nullable=True),
        sa.Column('last_execution', sa.DateTime(), nullable=True),
        sa.Column('next_execution', sa.DateTime(), nullable=True),
        sa.Column('execution_frequency', sa.String(20), nullable=True),
        sa.Column('strategy_parameters', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id']),
    )

    op.create_table(
        "strategy_performance",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('period_type', sa.String(20), nullable=False),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('winning_trades', sa.Integer(), nullable=True),
        sa.Column('losing_trades', sa.Integer(), nullable=True),
        sa.Column('avg_trade_duration_days', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('total_return', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_return_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('annualized_return_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('excess_return_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('volatility_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('max_drawdown_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('sharpe_ratio', sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column('sortino_ratio', sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column('beta', sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column('win_rate_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('avg_winning_trade_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('avg_losing_trade_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('largest_winner_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('largest_loser_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('profit_factor', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('avg_position_size_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('max_positions_held', sa.Integer(), nullable=True),
        sa.Column('avg_positions_held', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('position_turnover_rate', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('avg_slippage_bps', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('fill_rate_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('avg_time_to_fill_seconds', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('benchmark_symbol', sa.String(10), nullable=True),
        sa.Column('benchmark_return_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('alpha', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('tracking_error', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('information_ratio', sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id']),
        sa.UniqueConstraint('strategy_id', 'period_start', 'period_type', name='uq_strategy_period'),
    )
    op.create_index(op.f('idx_period_dates'), "strategy_performance", ['period_start', 'period_end'], unique=False)
    op.create_index(op.f('idx_strategy_period'), "strategy_performance", ['strategy_id', 'period_type'], unique=False)

    op.create_table(
        "strategy_runs",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('run_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='runstatus', create_type=False), nullable=False),
        sa.Column('execution_mode', postgresql.ENUM('PAPER', 'LIVE', 'BACKTEST', name='executionmode', create_type=False), nullable=False),
        sa.Column('universe_size', sa.Integer(), nullable=True),
        sa.Column('candidates_found', sa.Integer(), nullable=True),
        sa.Column('signals_generated', sa.Integer(), nullable=True),
        sa.Column('positions_opened', sa.Integer(), nullable=True),
        sa.Column('positions_closed', sa.Integer(), nullable=True),
        sa.Column('total_pnl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('realized_pnl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('unrealized_pnl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('data_quality_score', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('api_calls_made', sa.Integer(), nullable=True),
        sa.Column('api_errors', sa.Integer(), nullable=True),
        sa.Column('market_conditions', sa.JSON(), nullable=True),
        sa.Column('spy_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('vix_level', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('market_trend', sa.String(20), nullable=True),
        sa.Column('top_opportunities', sa.JSON(), nullable=True),
        sa.Column('risk_alerts', sa.JSON(), nullable=True),
        sa.Column('execution_notes', sa.Text(), nullable=True),
        sa.Column('errors_encountered', sa.JSON(), nullable=True),
        sa.Column('warnings_generated', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id']),
    )
    op.create_index(op.f('idx_execution_mode'), "strategy_runs", ['execution_mode'], unique=False)
    op.create_index(op.f('idx_strategy_run_date'), "strategy_runs", ['strategy_id', 'run_date'], unique=False)
    op.create_index(op.f('idx_strategy_run_status_date'), "strategy_runs", ['status', 'run_date'], unique=False)

    op.create_table(
        "tax_lots",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(64), nullable=False),
        sa.Column('contract_id', sa.String(50), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('cost_per_share', sa.Float(), nullable=True),
        sa.Column('cost_basis', sa.Float(), nullable=True),
        sa.Column('acquisition_date', sa.Date(), nullable=True),
        sa.Column('trade_id', sa.String(50), nullable=True),
        sa.Column('execution_id', sa.String(50), nullable=True),
        sa.Column('order_id', sa.String(50), nullable=True),
        sa.Column('exchange', sa.String(20), nullable=True),
        sa.Column('asset_category', sa.String(20), nullable=True),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('market_value', sa.Float(), nullable=True),
        sa.Column('unrealized_pnl', sa.Float(), nullable=True),
        sa.Column('unrealized_pnl_pct', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('commission', sa.Float(), nullable=True),
        sa.Column('fees', sa.Float(), nullable=True),
        sa.Column('fx_rate', sa.Float(), nullable=True),
        sa.Column('lot_id', sa.String(100), nullable=True),
        sa.Column('settlement_date', sa.Date(), nullable=True),
        sa.Column('holding_period', sa.Integer(), nullable=True),
        sa.Column('source', postgresql.ENUM('OFFICIAL_STATEMENT', 'REALTIME_API', 'MANUAL_ENTRY', 'CALCULATED', name='taxlotsource', create_type=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_price_update', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['broker_accounts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('lot_id'),
    )
    op.create_index(op.f('ix_tax_lots_account_id'), "tax_lots", ['account_id'], unique=False)
    op.create_index(op.f('ix_tax_lots_acquisition_date'), "tax_lots", ['acquisition_date'], unique=False)
    op.create_index(op.f('ix_tax_lots_symbol'), "tax_lots", ['symbol'], unique=False)
    op.create_index(op.f('ix_tax_lots_trade_id'), "tax_lots", ['trade_id'], unique=False)

    op.create_table(
        "trades",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('total_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('commission', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('fees', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('order_type', sa.String(20), nullable=True),
        sa.Column('time_in_force', sa.String(10), nullable=True),
        sa.Column('order_id', sa.String(50), nullable=True),
        sa.Column('execution_id', sa.String(50), nullable=True),
        sa.Column('order_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('settlement_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('strategy_name', sa.String(50), nullable=True),
        sa.Column('signal_id', sa.Integer(), nullable=True),
        sa.Column('entry_signal', sa.String(50), nullable=True),
        sa.Column('exit_signal', sa.String(50), nullable=True),
        sa.Column('risk_amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('position_size_pct', sa.Float(), nullable=True),
        sa.Column('atr_at_entry', sa.Float(), nullable=True),
        sa.Column('stop_loss_price', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('target_price', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('realized_pnl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('pnl_pct', sa.Float(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('is_opening', sa.Boolean(), nullable=True),
        sa.Column('is_paper_trade', sa.Boolean(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('trade_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['signal_id'], ['trade_signals.id']),
        sa.UniqueConstraint('account_id', 'execution_id', name='uq_trades_account_execution'),
        sa.ForeignKeyConstraint(['account_id'], ['broker_accounts.id']),
    )
    op.create_index(op.f('idx_trades_account_symbol_time'), "trades", ['account_id', 'symbol', 'execution_time'], unique=False)
    op.create_index(op.f('ix_trades_id'), "trades", ['id'], unique=False)
    op.create_index(op.f('ix_trades_symbol'), "trades", ['symbol'], unique=False)

    op.create_table(
        "transaction_sync_status",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('last_sync_date', sa.DateTime(), nullable=True),
        sa.Column('last_successful_sync', sa.DateTime(), nullable=True),
        sa.Column('sync_status', sa.String(20), nullable=True),
        sa.Column('earliest_transaction_date', sa.DateTime(), nullable=True),
        sa.Column('latest_transaction_date', sa.DateTime(), nullable=True),
        sa.Column('total_transactions', sa.Integer(), nullable=True),
        sa.Column('total_dividends', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['broker_accounts.id']),
    )
    op.create_index(op.f('idx_account_status'), "transaction_sync_status", ['account_id', 'sync_status'], unique=False)
    op.create_index(op.f('idx_last_sync'), "transaction_sync_status", ['last_sync_date'], unique=False)

    op.create_table(
        "transactions",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('account_alias', sa.String(100), nullable=True),
        sa.Column('external_id', sa.String(100), nullable=True),
        sa.Column('trade_id', sa.String(50), nullable=True),
        sa.Column('order_id', sa.String(50), nullable=True),
        sa.Column('execution_id', sa.String(50), nullable=True),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('conid', sa.String(50), nullable=True),
        sa.Column('security_id', sa.String(50), nullable=True),
        sa.Column('cusip', sa.String(20), nullable=True),
        sa.Column('isin', sa.String(20), nullable=True),
        sa.Column('listing_exchange', sa.String(20), nullable=True),
        sa.Column('underlying_conid', sa.String(50), nullable=True),
        sa.Column('underlying_symbol', sa.String(50), nullable=True),
        sa.Column('multiplier', sa.Float(), nullable=True),
        sa.Column('strike_price', sa.Float(), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('option_type', sa.String(10), nullable=True),
        sa.Column('transaction_type', postgresql.ENUM('BUY', 'SELL', 'DIVIDEND', 'PAYMENT_IN_LIEU', 'DISTRIBUTION', 'BROKER_INTEREST_PAID', 'BROKER_INTEREST_RECEIVED', 'COMMISSION', 'OTHER_FEE', 'DEPOSIT', 'WITHDRAWAL', 'SPLIT', 'SPIN_OFF', 'MERGER', 'WITHHOLDING_TAX', 'TAX_REFUND', 'TRANSFER', 'OTHER', name='transactiontype', create_type=True), nullable=False),
        sa.Column('action', sa.String(10), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('trade_price', sa.Float(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('proceeds', sa.Float(), nullable=True),
        sa.Column('commission', sa.Float(), nullable=True),
        sa.Column('brokerage_commission', sa.Float(), nullable=True),
        sa.Column('clearing_commission', sa.Float(), nullable=True),
        sa.Column('third_party_commission', sa.Float(), nullable=True),
        sa.Column('other_fees', sa.Float(), nullable=True),
        sa.Column('net_amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('fx_rate_to_base', sa.Float(), nullable=True),
        sa.Column('asset_category', sa.String(20), nullable=True),
        sa.Column('sub_category', sa.String(20), nullable=True),
        sa.Column('transaction_date', sa.DateTime(), nullable=False),
        sa.Column('trade_date', sa.Date(), nullable=True),
        sa.Column('settlement_date_target', sa.Date(), nullable=True),
        sa.Column('settlement_date', sa.Date(), nullable=True),
        sa.Column('taxes', sa.Float(), nullable=True),
        sa.Column('taxable_amount', sa.Float(), nullable=True),
        sa.Column('taxable_amount_base', sa.Float(), nullable=True),
        sa.Column('corporate_action_flag', sa.String(10), nullable=True),
        sa.Column('corporate_action_id', sa.String(50), nullable=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('synced_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['broker_accounts.id']),
        sa.UniqueConstraint('account_id', 'external_id', name='uq_transactions_account_external_id'),
        sa.UniqueConstraint('account_id', 'execution_id', name='uq_transactions_account_execution_id'),
    )
    op.create_index(op.f('idx_account_symbol_date'), "transactions", ['account_id', 'symbol', 'transaction_date'], unique=False)
    op.create_index(op.f('idx_external_id'), "transactions", ['external_id'], unique=False)
    op.create_index(op.f('idx_transaction_date'), "transactions", ['transaction_date'], unique=False)
    op.create_index(op.f('idx_transactions_symbol'), "transactions", ['symbol'], unique=False)
    op.create_index(op.f('ix_transactions_account_id'), "transactions", ['account_id'], unique=False)
    op.create_index(op.f('ix_transactions_conid'), "transactions", ['conid'], unique=False)
    op.create_index(op.f('ix_transactions_external_id'), "transactions", ['external_id'], unique=False)
    op.create_index(op.f('ix_transactions_symbol'), "transactions", ['symbol'], unique=False)
    op.create_index(op.f('ix_transactions_transaction_date'), "transactions", ['transaction_date'], unique=False)

    op.create_table(
        "transfers",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('broker_account_id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.String(100), nullable=True),
        sa.Column('client_reference', sa.String(100), nullable=True),
        sa.Column('transfer_date', sa.Date(), nullable=False),
        sa.Column('settle_date', sa.Date(), nullable=True),
        sa.Column('transfer_type', postgresql.ENUM('CASH', 'POSITION', 'ACATS', 'DIVIDEND', 'INTEREST', 'FEE', 'CORPORATE_ACTION', 'OPTION_EXERCISE', 'OPTION_ASSIGNMENT', 'SPLIT', 'MERGER', 'SPINOFF', 'OTHER', name='transfertype', create_type=True), nullable=False),
        sa.Column('direction', sa.String(10), nullable=True),
        sa.Column('symbol', sa.String(50), nullable=True),
        sa.Column('description', sa.String(200), nullable=True),
        sa.Column('contract_id', sa.String(50), nullable=True),
        sa.Column('security_id', sa.String(50), nullable=True),
        sa.Column('security_id_type', sa.String(20), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('trade_price', sa.Float(), nullable=True),
        sa.Column('transfer_price', sa.Float(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('cash_amount', sa.Float(), nullable=True),
        sa.Column('net_cash', sa.Float(), nullable=True),
        sa.Column('commission', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('fx_rate_to_base', sa.Float(), nullable=True),
        sa.Column('delivery_type', sa.String(50), nullable=True),
        sa.Column('transfer_type_code', sa.String(20), nullable=True),
        sa.Column('account_alias', sa.String(100), nullable=True),
        sa.Column('model', sa.String(50), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('external_reference', sa.String(100), nullable=True),
        sa.Column('data_source', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['broker_account_id'], ['broker_accounts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(op.f('ix_transfers_contract_id'), "transfers", ['contract_id'], unique=False)
    op.create_index(op.f('ix_transfers_symbol'), "transfers", ['symbol'], unique=False)
    op.create_index(op.f('ix_transfers_transaction_id'), "transfers", ['transaction_id'], unique=True)
    op.create_index(op.f('ix_transfers_transfer_date'), "transfers", ['transfer_date'], unique=False)

    op.create_table(
        "positions",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('instrument_id', sa.Integer(), nullable=True),
        sa.Column('instrument_type', sa.String(20), nullable=True),
        sa.Column('position_type', postgresql.ENUM('LONG', 'SHORT', 'OPTION_LONG', 'OPTION_SHORT', 'FUTURE_LONG', 'FUTURE_SHORT', name='positiontype', create_type=True), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column('status', postgresql.ENUM('OPEN', 'CLOSED', 'EXPIRED', name='positionstatus', create_type=True), nullable=False),
        sa.Column('average_cost', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('total_cost_basis', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('current_price', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('market_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('unrealized_pnl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('unrealized_pnl_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('day_pnl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('day_pnl_pct', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('position_size_pct', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('sector', sa.String(50), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True),
        sa.Column('beta', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('margin_priority', sa.Integer(), nullable=True),
        sa.Column('custom_category', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('market_cap', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('price_updated_at', sa.DateTime(), nullable=True),
        sa.Column('position_updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_sync_id', sa.Integer(), nullable=True),
        sa.Column('broker_position_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id']),
        sa.ForeignKeyConstraint(['last_sync_id'], ['account_syncs.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['account_id'], ['broker_accounts.id']),
    )
    op.create_index(op.f('idx_positions_status'), "positions", ['status'], unique=False)
    op.create_index(op.f('idx_positions_symbol'), "positions", ['symbol'], unique=False)
    op.create_index(op.f('idx_positions_type'), "positions", ['position_type'], unique=False)
    op.create_index(op.f('idx_positions_updated_at'), "positions", ['updated_at'], unique=False)
    op.create_index(op.f('idx_positions_user_account'), "positions", ['user_id', 'account_id'], unique=False)
    op.create_index(op.f('ix_positions_account_id'), "positions", ['account_id'], unique=False)
    op.create_index(op.f('ix_positions_instrument_id'), "positions", ['instrument_id'], unique=False)
    op.create_index(op.f('ix_positions_symbol'), "positions", ['symbol'], unique=False)
    op.create_index(op.f('ix_positions_user_id'), "positions", ['user_id'], unique=False)

    op.create_table(
        "signals",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('strategy_run_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('signal_type', postgresql.ENUM('ENTRY', 'EXIT', 'SCALE_OUT', 'STOP_LOSS', 'ALERT', name='signaltype', create_type=True), nullable=False),
        sa.Column('signal_strength', sa.Float(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('current_price', sa.Float(), nullable=False),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('targets', sa.JSON(), nullable=True),
        sa.Column('atr_distance', sa.Float(), nullable=True),
        sa.Column('rsi', sa.Float(), nullable=True),
        sa.Column('ma_alignment', sa.Boolean(), nullable=True),
        sa.Column('risk_reward_ratio', sa.Float(), nullable=True),
        sa.Column('time_horizon', sa.String(50), nullable=True),
        sa.Column('company_name', sa.String(200), nullable=True),
        sa.Column('company_synopsis', sa.Text(), nullable=True),
        sa.Column('sector', sa.String(50), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('market_cap_category', sa.String(20), nullable=True),
        sa.Column('status', postgresql.ENUM('PENDING', 'ACTIVE', 'TRIGGERED', 'EXPIRED', 'CANCELLED', name='signalstatus', create_type=True), nullable=True),
        sa.Column('max_price_reached', sa.Float(), nullable=True),
        sa.Column('min_price_reached', sa.Float(), nullable=True),
        sa.Column('actual_return', sa.Float(), nullable=True),
        sa.Column('days_active', sa.Integer(), nullable=True),
        sa.Column('is_executed', sa.Boolean(), nullable=True),
        sa.Column('execution_price', sa.Float(), nullable=True),
        sa.Column('execution_date', sa.DateTime(), nullable=True),
        sa.Column('quantity_executed', sa.Float(), nullable=True),
        sa.Column('signal_accuracy', sa.Float(), nullable=True),
        sa.Column('lessons_learned', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('started_audit', sa.DateTime(), nullable=True),
        sa.Column('completed_audit', sa.DateTime(), nullable=True),
        sa.Column('last_evaluated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('modified_by_user_id', sa.Integer(), nullable=True),
        sa.Column('processing_node', sa.String(50), nullable=True),
        sa.Column('audit_metadata', sa.JSON(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.UniqueConstraint('strategy_id', 'symbol', 'generated_at', name='uq_strategy_symbol_signal'),
        sa.ForeignKeyConstraint(['modified_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['strategy_run_id'], ['strategy_runs.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id']),
    )
    op.create_index(op.f('idx_generated_at'), "signals", ['generated_at'], unique=False)
    op.create_index(op.f('idx_signal_type_status'), "signals", ['signal_type', 'status'], unique=False)
    op.create_index(op.f('idx_signals_symbol_date'), "signals", ['symbol', 'generated_at'], unique=False)
    op.create_index(op.f('idx_strategy_symbol'), "signals", ['strategy_id', 'symbol'], unique=False)

    op.create_table(
        "position_categories",
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('position_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('allocation_pct', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.ForeignKeyConstraint(['position_id'], ['positions.id']),
    )
    op.create_index(op.f('idx_position_category'), "position_categories", ['position_id', 'category_id'], unique=True)

    op.create_table(
        "position_history",
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('position_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_date', sa.DateTime(), nullable=False),
        sa.Column('snapshot_type', sa.String(20), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column('price', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('market_value', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('unrealized_pnl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_cost_basis', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('day_return', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('week_return', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('month_return', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('inception_return', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('volatility', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('max_drawdown', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['position_id'], ['positions.id']),
    )
    op.create_index(op.f('idx_position_history_position_date'), "position_history", ['position_id', 'snapshot_date'], unique=False)
    op.create_index(op.f('idx_position_history_user_date'), "position_history", ['user_id', 'snapshot_date'], unique=False)
    op.create_index(op.f('ix_position_history_position_id'), "position_history", ['position_id'], unique=False)
    op.create_index(op.f('ix_position_history_snapshot_date'), "position_history", ['snapshot_date'], unique=False)
    op.create_index(op.f('ix_position_history_user_id'), "position_history", ['user_id'], unique=False)


def downgrade() -> None:
    raise RuntimeError(
        "Downgrading past the baseline revision 0001 is disabled to avoid "
        "dropping the entire database schema."
    )
