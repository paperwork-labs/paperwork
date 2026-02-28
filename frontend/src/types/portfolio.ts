/**
 * Consolidated portfolio-related types for frontend.
 * Single source of truth for Position, EnrichedPosition, OptionPosition, TaxLot,
 * Transaction/Activity, Dividend, PortfolioSummary, AccountData, etc.
 */

/** Equity position from /portfolio/stocks (backend Position model). */
export interface Position {
  id: number;
  symbol: string;
  account_number: string | null;
  broker: string;
  shares: number;
  current_price: number;
  market_value: number;
  cost_basis: number;
  average_cost: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  day_pnl?: number;
  day_pnl_pct?: number;
  sector?: string;
  industry?: string;
  last_updated?: string | null;
}

/** Position enriched with market snapshot data (stage, RS, performance). */
export interface EnrichedPosition extends Position {
  stage_label?: string | null;
  rs_mansfield_pct?: number | null;
  perf_1d?: number | null;
  perf_5d?: number | null;
  perf_20d?: number | null;
  rsi?: number | null;
  atr_14?: number | null;
  sma_50?: number | null;
  sma_200?: number | null;
  market_cap?: number | null;
  market_cap_label?: string | null;
}

/** Option contract position from /portfolio/options/unified/portfolio. */
export interface OptionPosition {
  id: number;
  symbol: string;
  underlying_symbol: string;
  strike_price: number;
  expiration_date: string;
  option_type: 'call' | 'put';
  quantity: number;
  average_open_price?: number;
  current_price?: number;
  market_value?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  day_pnl?: number;
  account_number?: string;
  days_to_expiration?: number;
  multiplier?: number;
  last_updated?: string;
}

/** Tax lot from /portfolio/stocks/{id}/tax-lots. */
export interface TaxLot {
  id: number;
  shares: number;
  shares_remaining: number;
  purchase_date: string | null;
  cost_per_share: number;
  market_value?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  is_long_term?: boolean;
  days_held?: number;
}

/** Unified activity row from /portfolio/activity (trades, transactions, dividends). */
export interface ActivityRow {
  ts: string;
  day?: string;
  account_id?: number;
  symbol?: string | null;
  category?: string;
  side?: string | null;
  quantity?: number | null;
  price?: number | null;
  amount?: number | null;
  net_amount?: number | null;
  commission?: number | null;
  src?: string;
  external_id?: string | null;
}

/** Transaction row (legacy shape for statements/statements endpoint). */
export interface TransactionRow {
  id?: string;
  date?: string;
  time?: string;
  type?: string;
  action?: string;
  symbol?: string;
  quantity?: number;
  price?: number;
  amount?: number;
  description?: string;
  commission?: number;
  net_amount?: number;
  currency?: string;
  account?: string;
}

/** Dividend from /portfolio/dividends. */
export interface Dividend {
  symbol: string;
  ex_date: string;
  pay_date: string;
  dividend_per_share: number;
  shares_held?: number;
  total_dividend: number;
  currency?: string;
  account_id?: number;
}

/** Dashboard summary from /portfolio/dashboard. */
export interface PortfolioSummary {
  total_value: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_pct?: number;
  total_market_value?: number;
  total_cost_basis?: number;
  day_change?: number;
  day_change_pct?: number;
  positions_count?: number;
  holdings_count?: number;
  accounts_summary?: unknown[];
  sector_allocation?: Array<{ name: string; value: number; percentage?: number }>;
  top_performers?: Array<{ symbol: string; return_pct?: number; unrealized_pnl?: number }>;
  top_losers?: Array<{ symbol: string; return_pct?: number; unrealized_pnl?: number }>;
  last_updated?: string;
  brokerages?: string[];
}

/** Account data for selector and filtering (used by AccountSelector, useAccountFilter). */
export interface AccountData {
  account_id: string;
  account_name: string;
  account_type: string;
  broker: string;
  total_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct?: number;
  positions_count: number;
  allocation_pct: number;
  available_funds?: number;
  buying_power?: number;
  day_change?: number;
  day_change_pct?: number;
}

/** Item that can be filtered by account (holdings, activity, etc.). */
export interface FilterableItem {
  account?: string;
  account_id?: string;
  account_number?: string;
  brokerage?: string;
  broker?: string;
  [key: string]: unknown;
}

/** Account filter configuration. */
export interface AccountFilterConfig {
  showAllOption?: boolean;
  defaultSelection?: string;
  filterByBrokerage?: boolean;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'simple' | 'detailed';
  showSummary?: boolean;
}

/** Portfolio analytics from /portfolio/analytics/{account_id}. */
export interface PortfolioAnalytics {
  account_id: number;
  as_of_date?: string;
  portfolio_metrics?: {
    total_value: number;
    total_cost_basis: number;
    total_unrealized_pnl: number;
    total_unrealized_pnl_pct: number;
    ytd_return?: number;
    total_return?: number;
    annualized_return?: number;
    volatility?: number;
    sharpe_ratio?: number;
    max_drawdown?: number;
    beta?: number;
    equity_allocation?: number;
    options_allocation?: number;
    cash_allocation?: number;
  };
  tax_opportunities?: unknown[];
  asset_allocation?: {
    total_value: number;
    by_asset_class?: Record<string, { value: number; percentage: number }>;
    top_holdings?: Array<{ symbol: string; value: number; percentage: number }>;
    concentration_risk?: number;
  };
  performance_attribution?: {
    by_security?: Record<string, number>;
    top_contributors?: Array<{ symbol: string; pnl: number }>;
    top_detractors?: Array<{ symbol: string; pnl: number }>;
    total_securities?: number;
  };
  positions_count?: number;
  tax_lots_count?: number;
}

/** Stock row (simplified for workspace / table display). */
export interface StockRow {
  id: number;
  symbol: string;
  shares: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

/** Tax lot row (for workspace table). */
export interface LotRow {
  id?: string | number;
  purchase_date?: string;
  cost_per_share?: number;
  shares?: number;
  shares_remaining?: number;
  market_value?: number;
  unrealized_pnl?: number;
  is_long_term?: boolean;
  days_held?: number;
}

/** Options summary from /portfolio/options/unified/summary. */
export interface OptionsSummary {
  total_positions: number;
  total_market_value: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_pct: number;
  total_day_pnl?: number;
  total_day_pnl_pct?: number;
  calls_count: number;
  puts_count: number;
  expiring_this_week: number;
  expiring_this_month: number;
  underlyings_count: number;
  avg_days_to_expiration?: number;
  underlyings?: string[];
}

/** Underlying grouping in options portfolio. */
export interface OptionsUnderlyingGroup {
  calls: OptionPosition[];
  puts: OptionPosition[];
  total_value: number;
  total_pnl: number;
}
