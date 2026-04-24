/**
 * `IncomeCalendar` — Snowball-style 12 × 31 dividend income grid.
 *
 * Backed by `GET /api/v1/portfolio/income/calendar`. Two modes:
 *   - `past`       — realised dividends aggregated by `pay_date`
 *   - `projection` — forecasted next-12-months income from per-symbol
 *                    historical cadence × current shares held
 *
 * UX rules (anchored to `no-silent-fallback.mdc`):
 *   - Loading: skeleton grid (12 month rows × 31 placeholder cells),
 *     not a spinner. Honors `prefers-reduced-motion` via framer-motion.
 *   - Error:   explicit `<ErrorPanel>` with retry — never an empty grid.
 *   - Empty:   guidance copy (add positions / import history), distinct
 *              from the error state.
 *   - Net toggle is disabled with a tooltip when the payload reports
 *     `tax_data_available: false`.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { CalendarDays } from "lucide-react";

import { ChartGlassCard } from "@/components/ui/ChartGlassCard";
import { RichTooltip } from "@/components/ui/RichTooltip";
import {
  SegmentedPeriodSelector,
  type SegmentedPeriodOption,
} from "@/components/ui/SegmentedPeriodSelector";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useUserPreferences } from "@/hooks/useUserPreferences";
import { cn } from "@/lib/utils";
import { portfolioApi } from "@/services/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type IncomeCalendarMode = "past" | "projection";

export interface IncomeCalendarSymbolBreakdown {
  symbol: string;
  amount: number;
}

export interface IncomeCalendarCell {
  date: string; // ISO date (YYYY-MM-DD)
  total: number;
  tax_withheld: number;
  by_symbol: IncomeCalendarSymbolBreakdown[];
}

export interface IncomeCalendarMonthTotal {
  month: string; // YYYY-MM
  total: number;
  tax_withheld: number;
  projected: boolean;
}

export interface IncomeCalendarResponse {
  mode: IncomeCalendarMode;
  months: number;
  tax_data_available: boolean;
  cells: IncomeCalendarCell[];
  monthly_totals: IncomeCalendarMonthTotal[];
  generated_at: string;
}

export interface IncomeCalendarProps {
  initialMode?: IncomeCalendarMode;
  months?: number;
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants & helpers
// ---------------------------------------------------------------------------

const MODE_OPTIONS: ReadonlyArray<SegmentedPeriodOption<IncomeCalendarMode>> = [
  { value: "past", label: "Past 12 months" },
  { value: "projection", label: "Next 12 months" },
];

const MONTH_LABEL_FMT = new Intl.DateTimeFormat(undefined, {
  month: "short",
  year: "2-digit",
});

const DAY_LABEL_FMT = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
});

// Tailwind: a bespoke 31-column grid. Tailwind's default scale tops out
// at `grid-cols-12`, so we use the arbitrary-value escape hatch.
const DAY_COLUMNS = "grid-cols-[repeat(31,minmax(0,1fr))]";

// 5 discrete intensity buckets mapped to design tokens. Bucket 0 is an
// empty cell (no payment); buckets 1-4 grow in saturation. We use the
// `--chart-success` token (R G B triplet defined in `frontend/src/index.css`)
// at four alpha tiers so the gradient stays color-blind-aware via the
// `data-palette="cb"` override on `:root`.
const INTENSITY_CLASS: Record<0 | 1 | 2 | 3 | 4, string> = {
  0: "bg-muted/30",
  1: "bg-[rgb(var(--chart-success)/0.18)]",
  2: "bg-[rgb(var(--chart-success)/0.38)]",
  3: "bg-[rgb(var(--chart-success)/0.62)]",
  4: "bg-[rgb(var(--chart-success)/0.88)]",
};

function parseISODate(iso: string): Date {
  // `YYYY-MM-DD` parsed as local-midnight, NOT UTC — otherwise users in
  // negative-offset timezones see cells slip back one day.
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1);
}

function parseMonth(month: string): Date {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, 1);
}

function buildCellMap(cells: IncomeCalendarCell[]): Map<string, IncomeCalendarCell> {
  const out = new Map<string, IncomeCalendarCell>();
  for (const c of cells) out.set(c.date, c);
  return out;
}

/**
 * Percentile-based intensity scale. A linear scale fails when one
 * cell is 100x larger than the rest (typical for special dividends);
 * using percentiles keeps the typical day in the middle of the
 * gradient instead of vanishing into bucket 1.
 */
function buildIntensityScale(
  cells: IncomeCalendarCell[],
): (amount: number) => 0 | 1 | 2 | 3 | 4 {
  const positives = cells
    .map((c) => c.total)
    .filter((n) => n > 0)
    .sort((a, b) => a - b);
  if (positives.length === 0) {
    return (amount) => (amount > 0 ? 1 : 0);
  }
  const q = (p: number): number => {
    const idx = Math.min(positives.length - 1, Math.floor(p * positives.length));
    return positives[idx];
  };
  const t1 = q(0.25);
  const t2 = q(0.5);
  const t3 = q(0.75);
  return (amount: number): 0 | 1 | 2 | 3 | 4 => {
    if (amount <= 0) return 0;
    if (amount <= t1) return 1;
    if (amount <= t2) return 2;
    if (amount <= t3) return 3;
    return 4;
  };
}

function makeCurrencyFormatter(currency: string, fractionDigits: number) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: 0,
  });
}

function formatCompactCurrency(amount: number, currency: string): string {
  // Compact for cells (small typography); 0 dp keeps numbers legible.
  if (amount === 0) return "";
  if (amount < 1) return makeCurrencyFormatter(currency, 2).format(amount);
  return makeCurrencyFormatter(currency, 0).format(amount);
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

interface DayCellProps {
  day: number;
  cell?: IncomeCalendarCell;
  intensity: 0 | 1 | 2 | 3 | 4;
  netMode: boolean;
  taxAvailable: boolean;
  currency: string;
}

const DayCell: React.FC<DayCellProps> = React.memo(function DayCell({
  day,
  cell,
  intensity,
  netMode,
  taxAvailable,
  currency,
}) {
  const total = cell?.total ?? 0;
  const tax = cell?.tax_withheld ?? 0;
  const displayed = netMode && taxAvailable ? Math.max(0, total - tax) : total;
  const visible = formatCompactCurrency(displayed, currency);

  const cellNode = (
    <div
      role="gridcell"
      aria-label={
        cell
          ? `${DAY_LABEL_FMT.format(parseISODate(cell.date))}: ${makeCurrencyFormatter(currency, 2).format(displayed)}`
          : `Day ${day}: no dividends`
      }
      className={cn(
        "flex aspect-square items-center justify-center rounded-[4px]",
        "text-[9px] font-mono leading-none tabular-nums text-foreground/85",
        "transition-colors",
        INTENSITY_CLASS[intensity],
        intensity > 0 && "ring-1 ring-foreground/[0.04]",
      )}
    >
      <span className="truncate px-0.5">{visible}</span>
    </div>
  );

  if (!cell) return cellNode;

  return (
    <RichTooltip
      side="top"
      align="center"
      maxWidth={280}
      ariaLabel="Dividend payment breakdown"
      trigger={cellNode}
    >
      <div className="space-y-2">
        <div className="text-xs font-medium text-foreground">
          {DAY_LABEL_FMT.format(parseISODate(cell.date))}
        </div>
        <div className="font-mono text-sm font-semibold tabular-nums text-foreground">
          {makeCurrencyFormatter(currency, 2).format(displayed)}
          {netMode && taxAvailable ? (
            <span className="ml-1 text-[10px] font-normal text-muted-foreground">
              net
            </span>
          ) : null}
        </div>
        <ul className="space-y-0.5">
          {cell.by_symbol.map((b) => (
            <li
              key={b.symbol}
              className="flex items-center justify-between gap-3 text-[11px]"
            >
              <span className="text-muted-foreground">{b.symbol}</span>
              <span className="font-mono tabular-nums text-foreground">
                {makeCurrencyFormatter(currency, 2).format(b.amount)}
              </span>
            </li>
          ))}
        </ul>
        {tax > 0 && !netMode ? (
          <div className="border-t border-border/50 pt-1 text-[10px] text-muted-foreground">
            Tax withheld: {makeCurrencyFormatter(currency, 2).format(tax)}
          </div>
        ) : null}
      </div>
    </RichTooltip>
  );
});

interface MonthRowProps {
  month: IncomeCalendarMonthTotal;
  cellMap: Map<string, IncomeCalendarCell>;
  intensityFor: (amount: number) => 0 | 1 | 2 | 3 | 4;
  netMode: boolean;
  taxAvailable: boolean;
  currency: string;
}

const MonthRow: React.FC<MonthRowProps> = ({
  month,
  cellMap,
  intensityFor,
  netMode,
  taxAvailable,
  currency,
}) => {
  const monthDate = parseMonth(month.month);
  const year = monthDate.getFullYear();
  const monthIndex = monthDate.getMonth();
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
  const monthlyDisplay =
    netMode && taxAvailable
      ? Math.max(0, month.total - month.tax_withheld)
      : month.total;

  return (
    <div
      role="row"
      className="grid grid-cols-[5rem_1fr_5.5rem] items-center gap-3"
    >
      <div className="text-xs font-medium text-muted-foreground">
        {MONTH_LABEL_FMT.format(monthDate)}
      </div>
      <div className={cn("grid gap-[2px]", DAY_COLUMNS)}>
        {Array.from({ length: 31 }).map((_, i) => {
          const day = i + 1;
          if (day > daysInMonth) {
            return (
              <div
                key={day}
                aria-hidden
                className="aspect-square rounded-[4px] bg-transparent"
              />
            );
          }
          const iso = `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const cell = cellMap.get(iso);
          return (
            <DayCell
              key={day}
              day={day}
              cell={cell}
              intensity={intensityFor(cell?.total ?? 0)}
              netMode={netMode}
              taxAvailable={taxAvailable}
              currency={currency}
            />
          );
        })}
      </div>
      <div
        className={cn(
          "text-right font-mono text-sm font-semibold tabular-nums",
          monthlyDisplay > 0 ? "text-foreground" : "text-muted-foreground/60",
          month.projected && "italic",
        )}
        title={month.projected ? "Projected" : "Actual"}
      >
        {monthlyDisplay > 0
          ? makeCurrencyFormatter(currency, 0).format(monthlyDisplay)
          : "—"}
      </div>
    </div>
  );
};

const SkeletonGrid: React.FC = () => {
  const reducedMotion = useReducedMotion();
  return (
    <div
      role="status"
      aria-label="Loading income calendar"
      className="space-y-2"
    >
      {Array.from({ length: 12 }).map((_, rowIdx) => (
        <div
          key={rowIdx}
          className="grid grid-cols-[5rem_1fr_5.5rem] items-center gap-3"
        >
          <div className="h-3 w-12 rounded bg-muted" />
          <div className={cn("grid gap-[2px]", DAY_COLUMNS)}>
            {Array.from({ length: 31 }).map((__, i) => (
              <motion.div
                key={i}
                aria-hidden
                className="aspect-square rounded-[4px] bg-muted/40"
                initial={false}
                animate={
                  reducedMotion
                    ? undefined
                    : { opacity: [0.5, 0.85, 0.5] }
                }
                transition={
                  reducedMotion
                    ? undefined
                    : {
                        duration: 1.6,
                        repeat: Infinity,
                        delay: (rowIdx * 31 + i) * 0.005,
                      }
                }
              />
            ))}
          </div>
          <div className="h-3 w-16 justify-self-end rounded bg-muted" />
        </div>
      ))}
    </div>
  );
};

const ErrorPanel: React.FC<{ onRetry: () => void; message?: string }> = ({
  onRetry,
  message,
}) => (
  <div
    role="alert"
    className="flex flex-col items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/[0.04] p-8 text-center"
  >
    <div className="text-sm font-medium text-foreground">
      We couldn&apos;t load your income calendar
    </div>
    <div className="text-xs text-muted-foreground">
      {message ?? "The request failed. Check your connection and try again."}
    </div>
    <button
      type="button"
      onClick={onRetry}
      className={cn(
        "mt-1 inline-flex h-8 items-center rounded-md border border-border",
        "bg-background px-3 text-xs font-medium text-foreground",
        "transition-colors hover:bg-muted",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
      )}
    >
      Retry
    </button>
  </div>
);

const EmptyPanel: React.FC = () => (
  <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border/70 bg-muted/20 p-10 text-center">
    <CalendarDays className="size-8 text-muted-foreground" aria-hidden />
    <div className="text-sm font-medium text-foreground">
      Your income calendar is quiet — no pay dates on the books yet.
    </div>
    <div className="max-w-sm text-xs text-muted-foreground">
      Add positions or import history and sync; checks will start landing on the grid.
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const IncomeCalendar: React.FC<IncomeCalendarProps> = ({
  initialMode = "past",
  months = 12,
  className,
}) => {
  const [mode, setMode] = React.useState<IncomeCalendarMode>(initialMode);
  const [netMode, setNetMode] = React.useState(false);
  const { currency } = useUserPreferences();

  const query = useQuery<IncomeCalendarResponse>({
    queryKey: ["portfolio", "income", "calendar", mode, months],
    queryFn: async () => {
      // makeOptimizedRequest already unwraps `response.data`, so the
      // typed return is the calendar payload itself.
      return (await portfolioApi.getIncomeCalendar(
        mode,
        months,
      )) as IncomeCalendarResponse;
    },
    staleTime: 1000 * 60 * 5,
  });

  const data = query.data;
  const taxAvailable = Boolean(data?.tax_data_available);

  const cellMap = React.useMemo(
    () => buildCellMap(data?.cells ?? []),
    [data?.cells],
  );
  const intensityFor = React.useMemo(
    () => buildIntensityScale(data?.cells ?? []),
    [data?.cells],
  );
  const annualTotal = React.useMemo(() => {
    if (!data) return 0;
    const sum = data.monthly_totals.reduce((acc, m) => acc + m.total, 0);
    const tax = data.monthly_totals.reduce(
      (acc, m) => acc + m.tax_withheld,
      0,
    );
    return netMode && taxAvailable ? Math.max(0, sum - tax) : sum;
  }, [data, netMode, taxAvailable]);

  return (
    <ChartGlassCard
      ariaLabel="Dividend income calendar"
      className={cn("flex flex-col gap-4", className)}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-foreground">
            Dividend Income
          </h2>
          <p className="text-xs text-muted-foreground">
            {mode === "past"
              ? "Realised dividends, by pay date."
              : "Projected dividends from history × current shares."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SegmentedPeriodSelector<IncomeCalendarMode>
            options={MODE_OPTIONS}
            value={mode}
            onChange={setMode}
            ariaLabel="Income calendar mode"
            size="sm"
          />
          <TooltipProvider delayDuration={120}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => taxAvailable && setNetMode((v) => !v)}
                  disabled={!taxAvailable}
                  aria-pressed={netMode && taxAvailable}
                  className={cn(
                    "inline-flex h-7 items-center rounded-full border px-3 text-[11px]",
                    "font-medium transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    netMode && taxAvailable
                      ? "border-foreground/20 bg-foreground/5 text-foreground"
                      : "border-border bg-background text-muted-foreground hover:text-foreground",
                    !taxAvailable && "cursor-not-allowed opacity-60 hover:text-muted-foreground",
                  )}
                >
                  {netMode && taxAvailable ? "Tax-paid (net)" : "Gross"}
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                {taxAvailable
                  ? "Toggle between gross and tax-withheld (net) amounts."
                  : "No tax withholding data available for these dividends."}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>

      {query.isPending ? <SkeletonGrid /> : null}

      {query.isError ? (
        <ErrorPanel
          onRetry={() => {
            void query.refetch();
          }}
          message={query.error instanceof Error ? query.error.message : undefined}
        />
      ) : null}

      {!query.isPending && !query.isError && data && data.cells.length === 0 ? (
        <EmptyPanel />
      ) : null}

      {!query.isPending && !query.isError && data && data.cells.length > 0 ? (
        <div
          className="space-y-2"
          role="grid"
          aria-label="Dividend income calendar"
        >
          {data.monthly_totals.map((month) => (
            <MonthRow
              key={month.month}
              month={month}
              cellMap={cellMap}
              intensityFor={intensityFor}
              netMode={netMode && taxAvailable}
              taxAvailable={taxAvailable}
              currency={currency}
            />
          ))}
          <div className="mt-2 grid grid-cols-[5rem_1fr_5.5rem] items-center gap-3 border-t border-border/40 pt-2">
            <div className="text-xs font-medium text-muted-foreground">
              {mode === "past" ? "Trailing 12mo" : "Next 12mo"}
            </div>
            <div className="text-[10px] text-muted-foreground">
              {data.cells.length} payment{data.cells.length === 1 ? "" : "s"}
              {data.monthly_totals.some((m) => m.projected) ? " · projected" : ""}
            </div>
            <div className="text-right font-mono text-base font-semibold tabular-nums text-foreground">
              {makeCurrencyFormatter(currency, 0).format(annualTotal)}
            </div>
          </div>
        </div>
      ) : null}
    </ChartGlassCard>
  );
};

export default IncomeCalendar;
