"use client";

import React, { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import { useChartColors } from '@/hooks/useChartColors';
import { usePortfolioPerformanceHistory } from '@/hooks/usePortfolio';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { formatMoney } from '@/utils/format';
import { marketDataApi } from '@/services/api';
import {
  Area,
  AreaChart,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const PERIODS = [
  { key: '30d', label: '30d' },
  { key: '90d', label: '90d' },
  { key: '1y', label: '1Y' },
  { key: 'all', label: 'All' },
] as const;

const HISTORY_PERIOD_STORAGE_KEY = 'axiomfolio:portfolio:history-period';
const HISTORY_PERIOD_KEYS: ReadonlySet<string> = new Set(PERIODS.map((p) => p.key));

const readStoredHistoryPeriod = (): string => {
  try {
    const stored = window.localStorage.getItem(HISTORY_PERIOD_STORAGE_KEY);
    if (stored && HISTORY_PERIOD_KEYS.has(stored)) return stored;
  } catch {
    // localStorage may be unavailable
  }
  return '1y';
};

const PerformanceTab: React.FC = () => {
  const [historyPeriod, setHistoryPeriodState] = useState<string>(() => readStoredHistoryPeriod());
  const setHistoryPeriod = React.useCallback((next: string) => {
    setHistoryPeriodState(next);
    try {
      window.localStorage.setItem(HISTORY_PERIOD_STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);
  const [showBenchmark, setShowBenchmark] = useState<boolean>(true);
  const { currency } = useUserPreferences();
  const colors = useChartColors();
  const historyQuery = usePortfolioPerformanceHistory({ period: historyPeriod });
  const historySeries = historyQuery.data;

  const [spyBars, setSpyBars] = React.useState<Array<{ time: string; close: number }>>([]);
  const [spyError, setSpyError] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    setSpyError(false);
    marketDataApi
      .getHistory('SPY', historyPeriod === 'all' ? '5y' : historyPeriod, '1d')
      .then((res: { bars?: unknown; data?: unknown }) => {
        if (cancelled) return;
        const bars = (res?.bars || res?.data || []) as Array<{ time?: string; date?: string; close: number }>;
        setSpyBars(bars.map((b) => ({ time: (b.time || b.date || '').slice(0, 10), close: b.close })));
      })
      .catch(() => {
        if (!cancelled) {
          setSpyBars([]);
          setSpyError(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [historyPeriod]);

  const equityCurveData = useMemo(() => {
    if (!historySeries?.length) return [];
    const spyMap = new Map(spyBars.map((b) => [b.time, b.close]));
    const firstPortfolioValue = historySeries[0].total_value || 1;
    let firstSpyClose: number | null = null;
    return historySeries.map((pt) => {
      const dateKey = String(pt.date ?? '').slice(0, 10);
      const spyClose = spyMap.get(dateKey);
      if (spyClose && firstSpyClose === null) firstSpyClose = spyClose;
      const portfolioPct = (pt.total_value / firstPortfolioValue - 1) * 100;
      const spyPct =
        spyClose && firstSpyClose ? (spyClose / firstSpyClose - 1) * 100 : undefined;
      return { date: dateKey, total_value: pt.total_value, portfolio_pct: portfolioPct, spy_pct: spyPct };
    });
  }, [historySeries, spyBars]);

  if (historyQuery.isPending) {
    return <p className="text-sm text-muted-foreground">Loading performance history…</p>;
  }
  if (historyQuery.isError) {
    return (
      <div className="flex flex-col items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4" role="alert">
        <p className={cn('text-sm', semanticTextColorClass('status.danger'))}>Failed to load performance history.</p>
        <Button size="sm" variant="outline" onClick={() => historyQuery.refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <Card className="gap-0 border border-border shadow-none ring-0">
      <CardContent className="py-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-semibold text-muted-foreground">
              {showBenchmark ? 'Performance vs SPY' : 'Value over time'}
            </span>
            <Button size="xs" variant={showBenchmark ? 'default' : 'outline'} onClick={() => setShowBenchmark((v) => !v)}>
              vs SPY
            </Button>
          </div>
          <div className="flex flex-wrap gap-1">
            {PERIODS.map((p) => (
              <Button
                key={p.key}
                size="xs"
                variant={historyPeriod === p.key ? 'default' : 'outline'}
                onClick={() => setHistoryPeriod(p.key)}
              >
                {p.label}
              </Button>
            ))}
          </div>
        </div>
        {spyError ? (
          <p className="mb-2 text-xs text-muted-foreground" role="status">
            Benchmark series unavailable; portfolio line still shown.
          </p>
        ) : null}
        {equityCurveData.length > 0 ? (
          <div className="h-[300px] w-full min-w-0" aria-label="Performance chart" role="img">
            {showBenchmark ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={equityCurveData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                  <defs>
                    <linearGradient id="portfolioPctGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={colors.area1} stopOpacity={0.2} />
                      <stop offset="100%" stopColor={colors.area1} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                  <Tooltip
                    formatter={(v, name) =>
                      [`${Number(v ?? 0).toFixed(2)}%`, name === 'portfolio_pct' ? 'Portfolio' : 'SPY'] as [
                        React.ReactNode,
                        string,
                      ]
                    }
                    labelFormatter={(d) => String(d)}
                  />
                  <Area
                    type="monotone"
                    dataKey="portfolio_pct"
                    stroke={colors.area1}
                    fill="url(#portfolioPctGradient)"
                    strokeWidth={2}
                    name="portfolio_pct"
                  />
                  <Line
                    type="monotone"
                    dataKey="spy_pct"
                    stroke={colors.area2}
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    dot={false}
                    name="spy_pct"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={equityCurveData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                  <defs>
                    <linearGradient id="portfolioValueGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={colors.area1} stopOpacity={0.25} />
                      <stop offset="100%" stopColor={colors.area1} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => formatMoney(v, currency, { maximumFractionDigits: 0 })}
                  />
                  <Tooltip
                    formatter={(v) => formatMoney(Number(v ?? 0), currency) as React.ReactNode}
                    labelFormatter={(d) => String(d)}
                  />
                  <Area
                    type="monotone"
                    dataKey="total_value"
                    stroke={colors.area1}
                    fill="url(#portfolioValueGradient)"
                    strokeWidth={1.5}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No performance history yet. Snapshots are recorded after sync.</p>
        )}
      </CardContent>
    </Card>
  );
};

export default PerformanceTab;
