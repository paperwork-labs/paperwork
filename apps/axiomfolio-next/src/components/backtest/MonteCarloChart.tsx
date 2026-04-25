/**
 * MonteCarloChart
 * ===============
 *
 * Fan-chart visualization of a Monte Carlo equity-curve confidence
 * band. Renders three layered ``Area`` series (P5..P95, P25..P75) plus
 * a P50 ``Line`` over the trade-index x-axis.
 *
 * Inherits the canonical ``ChartGlassCard`` frame so it slots into
 * dashboards alongside other premium charts (RegimeStrip, StageTape).
 *
 * Why two filled bands instead of one
 * -----------------------------------
 * A single 5..95 band hides where the bulk of mass actually lies; the
 * inner 25..75 band makes the "typical case" obvious at a glance.
 * Recharts has no native quantile band, so we render two stacked-area
 * subtractive pairs (lower bound is a transparent area to push the
 * upper band above the baseline).
 */
import * as React from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { ChartGlassCard } from '@/components/ui/ChartGlassCard';
import {
  type EquityFanRow,
  type MonteCarloEquityCurve,
  equityCurveToRows,
} from '@/services/backtest';
import { cn } from '@/lib/utils';

/* -------------------------------------------------------------------------
 * Color tokens
 *
 * We keep these as inline CSS variables instead of pulling Tailwind classes
 * because Recharts SVG props (``stroke``, ``fill``) need real CSS color
 * strings, not utility classes. Sourced from the design-system tokens so
 * dark mode flips automatically.
 * ---------------------------------------------------------------------- */

const FAN_OUTER = 'hsl(var(--chart-2) / 0.18)';
const FAN_INNER = 'hsl(var(--chart-2) / 0.32)';
const MEDIAN_STROKE = 'hsl(var(--chart-2))';
const AXIS_STROKE = 'hsl(var(--muted-foreground))';
const GRID_STROKE = 'hsl(var(--border))';

interface MonteCarloChartProps {
  equityCurve: MonteCarloEquityCurve;
  /** Currency code passed to Intl.NumberFormat for axis/tooltip. */
  currency?: string;
  /** Container className override (caller controls outer width/height). */
  className?: string;
  /** Aria label for the chart region. */
  ariaLabel?: string;
}

/** Compact currency formatter for the y-axis ($1.2k, $1.4M). */
function compactCurrency(value: number, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

/** Full-precision formatter for the tooltip. */
function fullCurrency(value: number, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

interface TooltipPayloadEntry {
  dataKey: string;
  name?: string;
  value?: number;
}

interface FanTooltipProps {
  active?: boolean;
  // Recharts' Tooltip ``content`` prop has notoriously fragile generics
  // when typed with the dataKey type union; we accept ``unknown`` here
  // and narrow at the call site, since the runtime contract is stable
  // (Recharts always passes ``payload``, ``label``, ``active``).
  payload?: unknown;
  label?: number | string;
  currency: string;
}

function FanTooltip({ active, payload, label, currency }: FanTooltipProps) {
  if (!active || !Array.isArray(payload) || payload.length === 0) return null;
  const byKey = new Map<string, TooltipPayloadEntry>();
  (payload as TooltipPayloadEntry[]).forEach((p) => {
    byKey.set(p.dataKey, p);
  });
  const order: Array<[string, string]> = [
    ['p95', 'P95'],
    ['p75', 'P75'],
    ['p50', 'Median (P50)'],
    ['p25', 'P25'],
    ['p5', 'P5'],
  ];
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="mb-1 font-medium text-popover-foreground">
        Trade #{label}
      </div>
      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 tabular-nums">
        {order.map(([key, displayLabel]) => {
          const entry = byKey.get(key);
          if (!entry || entry.value == null) return null;
          return (
            <React.Fragment key={key}>
              <span className="text-muted-foreground">{displayLabel}</span>
              <span className="text-right text-popover-foreground">
                {fullCurrency(entry.value, currency)}
              </span>
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

export function MonteCarloChart({
  equityCurve,
  currency = 'USD',
  className,
  ariaLabel = 'Monte Carlo equity curve confidence band',
}: MonteCarloChartProps) {
  const rows = React.useMemo<EquityFanRow[]>(
    () => equityCurveToRows(equityCurve),
    [equityCurve],
  );

  // Compute the y-axis domain with 5% padding so the band doesn't hug
  // the chart edges. We pad on the *visible* min/max (p5/p95) rather
  // than median so the upper/lower whiskers always have headroom.
  const { yMin, yMax } = React.useMemo(() => {
    if (rows.length === 0) return { yMin: 0, yMax: 0 };
    let mn = Number.POSITIVE_INFINITY;
    let mx = Number.NEGATIVE_INFINITY;
    for (const r of rows) {
      if (r.p5 < mn) mn = r.p5;
      if (r.p95 > mx) mx = r.p95;
    }
    const pad = (mx - mn) * 0.05;
    return { yMin: Math.max(0, mn - pad), yMax: mx + pad };
  }, [rows]);

  if (rows.length === 0) {
    return (
      <ChartGlassCard
        className={cn('min-h-[280px] items-center justify-center', className)}
        ariaLabel={ariaLabel}
      >
        <p className="text-sm text-muted-foreground">
          No simulation data to display.
        </p>
      </ChartGlassCard>
    );
  }

  return (
    <ChartGlassCard className={cn('min-h-[360px]', className)} ariaLabel={ariaLabel}>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Equity-curve confidence band
          </h3>
          <p className="text-xs text-muted-foreground">
            {rows.length} trades · P5–P95 outer band, P25–P75 inner band
          </p>
        </div>
      </div>
      <div className="h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={rows}
            margin={{ top: 8, right: 16, bottom: 8, left: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
            <XAxis
              dataKey="trade"
              stroke={AXIS_STROKE}
              tick={{ fontSize: 11 }}
              label={{
                value: 'Trade #',
                position: 'insideBottom',
                offset: -2,
                fill: AXIS_STROKE,
                fontSize: 11,
              }}
            />
            <YAxis
              domain={[yMin, yMax]}
              stroke={AXIS_STROKE}
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => compactCurrency(Number(v), currency)}
              width={64}
            />
            <Tooltip
              // Recharts' content type is a tagged union over data-key generics
              // that React's checker can't infer for our case; we provide a
              // narrow render-fn and let the runtime contract stand.
              content={
                ((props: unknown) => (
                  <FanTooltip
                    {...(props as Omit<FanTooltipProps, 'currency'>)}
                    currency={currency}
                  />
                )) as never
              }
            />
            <Legend
              verticalAlign="top"
              align="right"
              iconType="rect"
              wrapperStyle={{ fontSize: 11, paddingBottom: 8 }}
            />
            {/* Outer band: P5..P95 stacked-area trick — the lower
                series renders transparent so the upper one effectively
                fills the gap between the two. */}
            <Area
              type="monotone"
              dataKey="p5"
              name="P5"
              stackId="outer"
              stroke="transparent"
              fill="transparent"
              isAnimationActive={false}
              legendType="none"
            />
            <Area
              type="monotone"
              dataKey="p95"
              name="P5–P95 band"
              stackId="outer-upper"
              stroke="transparent"
              fill={FAN_OUTER}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="p25"
              name="P25"
              stackId="inner"
              stroke="transparent"
              fill="transparent"
              isAnimationActive={false}
              legendType="none"
            />
            <Area
              type="monotone"
              dataKey="p75"
              name="P25–P75 band"
              stackId="inner-upper"
              stroke="transparent"
              fill={FAN_INNER}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="p50"
              name="Median (P50)"
              stroke={MEDIAN_STROKE}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </ChartGlassCard>
  );
}
