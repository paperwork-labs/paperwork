/**
 * Stable keys mirrored from `backend/services/billing/feature_catalog.py`.
 * Use for `useEntitlement().can()` / `TierGate` so typos are compile-time errors.
 */
export const FEATURE_CHART_TRADE_ANNOTATIONS = 'chart.trade_annotations' as const;
export const FEATURE_CHART_TRADE_RATIONALE = 'chart.trade_rationale' as const;
export const FEATURE_CHART_RS_RIBBON = 'chart.rs_ribbon' as const;

export type FeatureChartKey =
  | typeof FEATURE_CHART_TRADE_ANNOTATIONS
  | typeof FEATURE_CHART_TRADE_RATIONALE
  | typeof FEATURE_CHART_RS_RIBBON;
