/**
 * Wire types for the `/market-data/prices/{symbol}/indicators` endpoint.
 *
 * The backend returns a calendar-aligned dict-of-series payload:
 *   { dates: ["YYYY-MM-DD", ...], rsi: [...], sma_50: [...], ... }
 * with one entry per ISO date. The series values can be `null` for
 * warm-up periods that are mathematically undefined (e.g. SMA 200 for
 * the first 199 bars), and string-encoded numbers slip through under
 * Decimal serialization on some columns — consumers must therefore
 * treat each cell as `number | string | null` and coerce defensively.
 */

export interface VolumeEventItem {
  date: string;
  type: 'climax' | 'dry_up';
}

export interface KellPatternItem {
  date: string;
  pattern: 'EBC' | 'KRC' | 'PPB';
  confidence: number;
}

export interface IndicatorSeriesResponse {
  symbol: string;
  rows: number;
  backfill_requested: boolean;
  price_data_pending: boolean;
  series: { dates: Array<string | null> } & Record<
    string,
    Array<number | string | null>
  >;
  /** Present only for tiers that have `chart.trade_annotations` (and only when the backend could compute). */
  volume_events?: VolumeEventItem[];
  kell_patterns?: KellPatternItem[];
}

/**
 * Indicator column keys we explicitly support in the frontend overlay
 * controls and metric strip. The backend exposes more columns than
 * this; we keep the union narrow so a typo at a call site is a
 * compile-time error rather than a silent miss.
 */
export type IndicatorKey =
  | 'sma_50'
  | 'sma_100'
  | 'sma_150'
  | 'sma_200'
  | 'ema_21'
  | 'ema_200'
  | 'bollinger_upper'
  | 'bollinger_lower'
  | 'rsi'
  | 'macd'
  | 'macd_signal'
  | 'macd_histogram'
  | 'adx'
  | 'plus_di'
  | 'minus_di'
  | 'atr_14'
  | 'atrp_14'
  | 'rs_mansfield_pct'
  | 'stage_label';
