/**
 * `AxiomMetricStrip` — compact KPI row that surfaces the six metrics a
 * Stage Analysis / momentum trader cares about at a glance:
 *
 *   1. Stage           — Weinstein-refined sub-stage label (e.g. "2A")
 *   2. RSI             — Wilder 14
 *   3. ATR%            — ATR(14) as % of price
 *   4. MACD            — current line value
 *   5. ADX             — Wilder 14 trend strength
 *   6. RS Mansfield    — relative strength vs benchmark
 *
 * Each card is a `RichTooltip` trigger so users can read the definition
 * without leaving the chart. Numeric cells animate on change via
 * `AnimatedNumber`, contextual color is sourced from `STAGE_HEX` and
 * `heatColorHex` so the strip and the chart stay visually coherent.
 *
 * The component is read-only and does no fetching of its own — the
 * parent feeds it a flat `MetricStripValues` object derived from the
 * latest snapshot. This keeps it trivial to mock in stories/tests.
 */
import * as React from 'react';

import { AnimatedNumber } from '@/components/ui/AnimatedNumber';
import { RichTooltip } from '@/components/ui/RichTooltip';
import { STAGE_HEX, heatColorHex, SIGNAL_HEX } from '@/constants/chart';
import { cn } from '@/lib/utils';

import { MetricStripSkeleton } from './skeletons/MetricStripSkeleton';

const PALETTE_CHANGE_EVENT = 'axiomfolio:color-palette-change';

export interface MetricStripValues {
  stageLabel?: string | null;
  rsi?: number | null;
  atrPct?: number | null;
  macd?: number | null;
  adx?: number | null;
  rsMansfield?: number | null;
}

export interface AxiomMetricStripProps {
  values: MetricStripValues;
  loading?: boolean;
  className?: string;
}

interface MetricCard {
  key: string;
  label: string;
  tooltipTitle: string;
  tooltipBody: string;
  formatted: string;
  rawValue: number | null;
  /** Inline color for the value (hex). When undefined, we fall back to the foreground token. */
  color?: string;
  ariaValue: string;
  /**
   * For numeric cards, the raw float so `AnimatedNumber` can tween between
   * frames. When undefined we render the formatted string statically (e.g.
   * for the stage label, which is a string not a number).
   */
  numeric?: { value: number; format: (n: number) => string } | null;
}

const PCT_FORMAT = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const NUM_FORMAT = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function readIsDark(): boolean {
  if (typeof document === 'undefined') return false;
  return document.documentElement.classList.contains('dark');
}

function pickStageColor(label: string, isDark: boolean): string | undefined {
  const tuple = STAGE_HEX[label];
  if (!tuple) return undefined;
  return isDark ? tuple[1] : tuple[0];
}

/**
 * RSI shading: red above 70 (overbought), green below 30 (oversold),
 * muted in the neutral band. We mirror the heat scale's palette so the
 * strip reads coherently with the rest of the dashboard.
 */
function rsiColor(rsi: number, isDark: boolean): string {
  const i = isDark ? 1 : 0;
  if (rsi >= 70) return SIGNAL_HEX.bearish[i];
  if (rsi <= 30) return SIGNAL_HEX.bullish[i];
  return SIGNAL_HEX.neutral[i];
}

/** ADX > 25 = trending; < 20 = no trend. Highlight the strong-trend band. */
function adxColor(adx: number, isDark: boolean): string {
  const i = isDark ? 1 : 0;
  if (adx >= 25) return SIGNAL_HEX.warning[i];
  return SIGNAL_HEX.neutral[i];
}

function macdColor(value: number, isDark: boolean): string {
  const i = isDark ? 1 : 0;
  if (value > 0) return SIGNAL_HEX.bullish[i];
  if (value < 0) return SIGNAL_HEX.bearish[i];
  return SIGNAL_HEX.neutral[i];
}

function buildCards(values: MetricStripValues, isDark: boolean): MetricCard[] {
  const stage =
    typeof values.stageLabel === 'string' && values.stageLabel.length > 0
      ? values.stageLabel
      : null;
  const stageColor = stage ? pickStageColor(stage, isDark) : undefined;

  const rsi = numericOrNull(values.rsi);
  const atrPct = numericOrNull(values.atrPct);
  const macd = numericOrNull(values.macd);
  const adx = numericOrNull(values.adx);
  const rs = numericOrNull(values.rsMansfield);

  return [
    {
      key: 'stage',
      label: 'Stage',
      tooltipTitle: 'Weinstein Stage',
      tooltipBody:
        'Refined Stage Analysis sub-stage. 2A–2C are the constructive uptrend, 4A–4C the destructive downtrend.',
      formatted: stage ?? '—',
      rawValue: null,
      color: stageColor,
      ariaValue: stage ? `Stage ${stage}` : 'Stage unavailable',
      numeric: null,
    },
    {
      key: 'rsi',
      label: 'RSI',
      tooltipTitle: 'Relative Strength Index (14)',
      tooltipBody:
        'Wilder RSI on a 0–100 scale. Above 70 is typically overbought, below 30 oversold.',
      formatted: rsi !== null ? NUM_FORMAT.format(rsi) : '—',
      rawValue: rsi,
      color: rsi !== null ? rsiColor(rsi, isDark) : undefined,
      ariaValue: rsi !== null ? `RSI ${NUM_FORMAT.format(rsi)}` : 'RSI unavailable',
      numeric: rsi !== null ? { value: rsi, format: (n) => NUM_FORMAT.format(n) } : null,
    },
    {
      key: 'atrp',
      label: 'ATR%',
      tooltipTitle: 'Average True Range (14) as % of price',
      tooltipBody:
        'Average daily range over the last 14 sessions, expressed as a percentage of the current price. Used to size positions to a fixed dollar risk.',
      formatted: atrPct !== null ? `${PCT_FORMAT.format(atrPct)}%` : '—',
      rawValue: atrPct,
      color: atrPct !== null ? heatColorHex(-atrPct) : undefined,
      ariaValue:
        atrPct !== null
          ? `ATR percent ${PCT_FORMAT.format(atrPct)}`
          : 'ATR percent unavailable',
      numeric:
        atrPct !== null
          ? { value: atrPct, format: (n) => `${PCT_FORMAT.format(n)}%` }
          : null,
    },
    {
      key: 'macd',
      label: 'MACD',
      tooltipTitle: 'MACD (12,26,9)',
      tooltipBody:
        'Moving Average Convergence/Divergence — momentum oscillator. Above zero is bullish, below zero bearish.',
      formatted: macd !== null ? NUM_FORMAT.format(macd) : '—',
      rawValue: macd,
      color: macd !== null ? macdColor(macd, isDark) : undefined,
      ariaValue: macd !== null ? `MACD ${NUM_FORMAT.format(macd)}` : 'MACD unavailable',
      numeric: macd !== null ? { value: macd, format: (n) => NUM_FORMAT.format(n) } : null,
    },
    {
      key: 'adx',
      label: 'ADX',
      tooltipTitle: 'Average Directional Index (14)',
      tooltipBody:
        'Trend strength on a 0–100 scale. Above 25 indicates a meaningful trend; below 20 suggests a chop / range.',
      formatted: adx !== null ? NUM_FORMAT.format(adx) : '—',
      rawValue: adx,
      color: adx !== null ? adxColor(adx, isDark) : undefined,
      ariaValue: adx !== null ? `ADX ${NUM_FORMAT.format(adx)}` : 'ADX unavailable',
      numeric: adx !== null ? { value: adx, format: (n) => NUM_FORMAT.format(n) } : null,
    },
    {
      key: 'rs',
      label: 'RS Mansfield',
      tooltipTitle: 'Relative Strength (Mansfield)',
      tooltipBody:
        'Mansfield-style relative strength vs the benchmark, normalized to its 52-week mean. Positive = outperforming; negative = lagging.',
      formatted: rs !== null ? signed(rs) : '—',
      rawValue: rs,
      color: rs !== null ? heatColorHex(rs) : undefined,
      ariaValue: rs !== null ? `RS Mansfield ${signed(rs)}` : 'RS Mansfield unavailable',
      numeric: rs !== null ? { value: rs, format: signed } : null,
    },
  ];
}

function numericOrNull(v: number | null | undefined): number | null {
  if (v == null) return null;
  return Number.isFinite(v) ? v : null;
}

function signed(n: number): string {
  const sign = n > 0 ? '+' : '';
  return `${sign}${NUM_FORMAT.format(n)}`;
}

export function AxiomMetricStrip({
  values,
  loading = false,
  className,
}: AxiomMetricStripProps) {
  // Same theme reactivity contract as `StageOverlay` / `HoldingPriceChart`.
  // Bumping `themeTick` invalidates the memoized cards so contextual colors
  // re-resolve on dark-mode / palette toggles.
  const [themeTick, setThemeTick] = React.useState(0);
  React.useEffect(() => {
    if (typeof window === 'undefined') return;
    const bump = () => setThemeTick((t) => t + 1);
    window.addEventListener(PALETTE_CHANGE_EVENT, bump);
    const observer = new MutationObserver(bump);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class', 'data-palette'],
    });
    return () => {
      window.removeEventListener(PALETTE_CHANGE_EVENT, bump);
      observer.disconnect();
    };
  }, []);

  const cards = React.useMemo(() => {
    // Reference themeTick so the memo invalidates on theme/palette change.
    void themeTick;
    return buildCards(values, readIsDark());
  }, [values, themeTick]);

  if (loading) {
    return (
      <MetricStripSkeleton
        className={className}
        count={6}
        label="indicator metrics"
      />
    );
  }

  return (
    <div
      role="group"
      aria-label="Key indicator metrics"
      data-testid="axiom-metric-strip"
      className={cn(
        'flex w-full flex-wrap items-stretch gap-3 sm:flex-nowrap',
        className,
      )}
    >
      {cards.map((card) => (
        <MetricCardView key={card.key} card={card} />
      ))}
    </div>
  );
}

interface MetricCardViewProps {
  card: MetricCard;
}

function MetricCardView({ card }: MetricCardViewProps) {
  const valueClass = cn(
    'font-heading text-lg font-semibold tabular-nums',
    !card.color && 'text-foreground',
  );
  const style = card.color ? { color: card.color } : undefined;

  const valueNode =
    card.numeric && card.rawValue !== null ? (
      <AnimatedNumber
        className={valueClass}
        value={card.numeric.value}
        format={card.numeric.format}
        ariaLabel={card.ariaValue}
      />
    ) : (
      <span
        className={cn(valueClass, 'inline-block')}
        style={style}
        aria-label={card.ariaValue}
      >
        {card.formatted}
      </span>
    );

  return (
    <RichTooltip
      side="top"
      ariaLabel={card.tooltipTitle}
      trigger={
        <div
          tabIndex={0}
          className={cn(
            'group flex min-w-0 flex-1 flex-col gap-1 rounded-lg border border-border/40 bg-card/40 p-3',
            'cursor-help backdrop-blur-sm transition-colors',
            'hover:border-border hover:bg-card/60',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          )}
        >
          <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {card.label}
          </span>
          <span style={style}>{valueNode}</span>
        </div>
      }
    >
      <div className="flex flex-col gap-1 text-sm">
        <span className="font-medium text-foreground">{card.tooltipTitle}</span>
        <span className="text-muted-foreground">{card.tooltipBody}</span>
      </div>
    </RichTooltip>
  );
}

export default AxiomMetricStrip;
