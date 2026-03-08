export type StrategyType = 'atr_matrix' | 'momentum' | 'mean_reversion' | 'breakout' | 'options_flow' | 'earnings_play' | 'custom';
export type StrategyStatus = 'draft' | 'active' | 'paused' | 'stopped' | 'archived';
export type RunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type ExecutionMode = 'backtest' | 'paper' | 'live';

export interface Strategy {
  id: number;
  name: string;
  description: string | null;
  strategy_type: StrategyType;
  status: StrategyStatus;
  parameters: Record<string, unknown>;
  execution_mode?: ExecutionMode | null;
  max_positions?: number | null;
  position_size_pct?: number | null;
  stop_loss_pct?: number | null;
  take_profit_pct?: number | null;
  run_frequency?: string | null;
  created_at: string;
  updated_at: string;
}

export interface StrategyRun {
  id: number;
  strategy_id: number;
  status: RunStatus;
  execution_mode: ExecutionMode;
  started_at: string | null;
  completed_at: string | null;
  result_summary: Record<string, unknown> | null;
  error_message: string | null;
}

export interface BacktestMetrics {
  initial_capital: number;
  final_capital: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  total_trades: number;
  win_rate: number;
  profit_factor: number | null;
  avg_trade_pnl: number;
  max_win: number;
  max_loss: number;
}

export interface BacktestTrade {
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  date: string;
  pnl: number;
}

export interface BacktestResult {
  strategy_id: number;
  metrics: BacktestMetrics;
  equity_curve: Array<{ date: string; equity: number }>;
  trades: BacktestTrade[];
}

export interface StrategyTemplate {
  id: string;
  name: string;
  description: string;
  strategy_type: StrategyType;
  position_size_pct: number;
  max_positions: number;
  stop_loss_pct?: number;
  max_holding_days?: number;
  universe_filter?: Record<string, unknown>;
}

export interface StrategyTemplateDetail extends StrategyTemplate {
  default_config: {
    entry_rules: ConditionGroupData;
    exit_rules: ConditionGroupData;
  };
}

export interface ConditionData {
  field: string;
  operator: string;
  value: unknown;
  value_high?: unknown;
}

export interface ConditionGroupData {
  logic: 'and' | 'or';
  conditions: ConditionData[];
  groups: ConditionGroupData[];
}
