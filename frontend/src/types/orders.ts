export type OrderSide = 'buy' | 'sell';
export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit';
export type OrderStatus =
  | 'preview'
  | 'pending_submit'
  | 'submitted'
  | 'partially_filled'
  | 'filled'
  | 'cancelled'
  | 'rejected'
  | 'error';
export type OrderSource = 'manual' | 'strategy' | 'rebalance';
export type BrokerType = 'ibkr' | 'tastytrade' | 'schwab';

export interface Order {
  id: number;
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  status: OrderStatus;
  quantity: number;
  limit_price: number | null;
  stop_price: number | null;
  filled_quantity: number;
  filled_avg_price: number | null;
  account_id: string | null;
  broker_order_id: string | null;
  strategy_id: number | null;
  signal_id: number | null;
  position_id: number | null;
  user_id: number | null;
  source: OrderSource;
  broker_type: BrokerType;
  estimated_commission: number | null;
  estimated_margin_impact: number | null;
  preview_data: Record<string, unknown> | null;
  error_message: string | null;
  submitted_at: string | null;
  filled_at: string | null;
  cancelled_at: string | null;
  created_at: string | null;
  created_by: string | null;
}

export interface OrderPreviewRequest {
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  quantity: number;
  limit_price?: number;
  stop_price?: number;
}

export interface OrderPreviewResponse {
  order_id: number;
  status: OrderStatus;
  preview: {
    estimated_commission: number | null;
    estimated_margin_impact: number | null;
    estimated_equity_with_loan: number | null;
  };
  warnings: string[];
}

export interface OrderSubmitRequest {
  order_id: number;
}
