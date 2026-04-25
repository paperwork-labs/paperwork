/**
 * Wire shape returned by the backend Trade Decision Explainer endpoints
 * (see backend/api/routes/agent_trade_decision.py and
 * backend/services/agent/trade_decision_explainer.py).
 *
 * Money fields are strings on the wire (Decimal -> str) so the frontend
 * never decides what to round.
 */

export type TradeDecisionTrigger =
  | 'pick'
  | 'scan'
  | 'rebalance'
  | 'manual'
  | 'strategy'
  | 'unknown';

export type TradeDecisionOutcomeStatus = 'open' | 'closed' | 'unknown';

export interface TradeDecisionRiskContext {
  position_size_label: string;
  stop_placement: string;
  regime_alignment: string;
}

export interface TradeDecisionOutcome {
  status: TradeDecisionOutcomeStatus;
  summary: string;
  pnl_label?: string;
}

export interface TradeDecisionPayload {
  trigger: TradeDecisionTrigger;
  headline: string;
  rationale_bullets: string[];
  risk_context: TradeDecisionRiskContext;
  outcome_so_far: TradeDecisionOutcome;
  narrative: string;
}

export interface TradeDecisionExplanation {
  row_id: number;
  order_id: number;
  user_id: number;
  version: number;
  trigger_type: TradeDecisionTrigger;
  schema_version: string;
  model_used: string;
  is_fallback: boolean;
  cost_usd: string;
  prompt_token_count: number;
  completion_token_count: number;
  payload: TradeDecisionPayload;
  narrative: string;
  generated_at: string | null;
  reused: boolean;
}
