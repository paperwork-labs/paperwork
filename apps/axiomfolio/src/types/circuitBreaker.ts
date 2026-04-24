export interface CircuitBreakerStatus {
  tier: number;
  allowed: boolean;
  reason: string;
  daily_pnl: number;
  /** Loss as % of starting equity; 0 when daily P&L is flat or positive. */
  daily_pnl_pct: number;
  order_count: number;
  consecutive_losses: number;
  kill_switch_active: boolean;
  trip_reason: string;
  trip_time: string;
}
