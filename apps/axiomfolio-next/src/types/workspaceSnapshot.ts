/**
 * Per-symbol market snapshot used by the portfolio workspace "context" strip.
 * Aligned to `/market-data/snapshots/{symbol}` payload (nested shapes normalized in
 * `parseWorkspaceSnapshotFromMarketDataResponse`).
 */
export interface WorkspaceSnapshot {
  stage_label?: string | number;
  current_stage_days?: number | null;
  rsi?: number | null;
  atrp_14?: number | null;
  pe_ttm?: number | null;
  dividend_yield?: number | null;
  beta?: number | null;
  rs_mansfield_pct?: number | null;
  td_buy_complete?: boolean;
  td_buy_setup?: number;
  td_sell_complete?: boolean;
  td_sell_setup?: number;
  td_buy_countdown?: number;
  td_sell_countdown?: number;
  gaps_unfilled_up?: number | null;
  gaps_unfilled_down?: number | null;
  next_earnings?: string | null;
}

/**
 * Unwrap snapshot from the body returned by `marketDataApi.getSnapshot` (already
 * unwrapped via `makeOptimizedRequest`). Same shape as the legacy: `d =
 * res.data; return d?.data?.snapshot ?? d?.snapshot ?? d` with `res` the top JSON
 * from the client.
 */
export function parseWorkspaceSnapshotFromMarketDataResponse(top: unknown): WorkspaceSnapshot | null {
  if (top == null || typeof top !== 'object') return null;
  const d = (top as Record<string, unknown>).data;
  if (d === undefined) return null;
  if (d === null) return null;
  if (typeof d !== 'object') return null;
  const dRec = d as Record<string, unknown>;
  const inner = dRec.data;
  if (inner != null && typeof inner === 'object' && 'snapshot' in (inner as object)) {
    const snap = (inner as { snapshot?: unknown }).snapshot;
    if (snap != null && typeof snap === 'object') return snap as WorkspaceSnapshot;
  }
  if (dRec.snapshot != null && typeof dRec.snapshot === 'object') {
    return dRec.snapshot as WorkspaceSnapshot;
  }
  return d as WorkspaceSnapshot;
}
