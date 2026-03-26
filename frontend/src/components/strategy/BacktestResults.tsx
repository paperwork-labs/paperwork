import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { BacktestResult, BacktestMetrics, BacktestTrade } from '../../types/strategy';
import { useChartColors } from '../../hooks/useChartColors';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney, formatDate } from '../../utils/format';

function colorForValue(value: number, isPercent = false): string {
  if (isPercent || Math.abs(value) < 1e-9) {
    return value > 0 ? 'text-emerald-600 dark:text-emerald-400' : value < 0 ? 'text-destructive' : 'text-foreground';
  }
  return value > 0 ? 'text-emerald-600 dark:text-emerald-400' : value < 0 ? 'text-destructive' : 'text-foreground';
}

function formatPercent(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value.toFixed(2)}%`;
}

function formatRatio(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return value.toFixed(2);
}

interface MetricCardProps {
  label: string;
  value: number | null;
  formatter: (v: number | null) => string;
  colorKey?: 'percent' | 'pnl' | 'neutral';
}

function MetricCard({ label, value, formatter, colorKey = 'neutral' }: MetricCardProps) {
  const colorClass =
    colorKey === 'percent' || colorKey === 'pnl' ? colorForValue(value ?? 0, colorKey === 'percent') : 'text-foreground';
  const formattedValue = formatter(value);
  return (
    <Card size="sm">
      <CardContent className="space-y-0.5 pt-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className={cn('text-lg font-bold', colorClass)}>{formattedValue}</p>
      </CardContent>
    </Card>
  );
}

export default function BacktestResults({ result }: { result: BacktestResult }) {
  const { metrics, equity_curve, trades } = result;
  const colors = useChartColors();
  const { currency, timezone } = useUserPreferences();

  const formatCurrency = (amount: number) =>
    formatMoney(amount, currency, { maximumFractionDigits: 2, minimumFractionDigits: 2 });

  const chartData = React.useMemo(() => {
    if (!equity_curve?.length) return [];
    return equity_curve.map(({ date, equity }) => ({
      date: date.slice(0, 10),
      equity,
    }));
  }, [equity_curve]);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard
          label="Total Return %"
          value={metrics.total_return_pct}
          formatter={formatPercent}
          colorKey="percent"
        />
        <MetricCard
          label="Max Drawdown %"
          value={metrics.max_drawdown_pct}
          formatter={formatPercent}
          colorKey="percent"
        />
        <MetricCard label="Sharpe Ratio" value={metrics.sharpe_ratio} formatter={formatRatio} />
        <MetricCard
          label="Win Rate"
          value={metrics.win_rate}
          formatter={(v) => (v != null && Number.isFinite(v) ? `${(v * 100).toFixed(1)}%` : '—')}
        />
        <MetricCard label="Profit Factor" value={metrics.profit_factor} formatter={formatRatio} />
        <MetricCard
          label="Total Trades"
          value={metrics.total_trades}
          formatter={(v) => (v != null && Number.isFinite(v) ? v.toLocaleString() : '—')}
        />
        <MetricCard
          label="Avg P&L"
          value={metrics.avg_trade_pnl}
          formatter={(v) => (v != null && Number.isFinite(v) ? formatMoney(v, currency) : '—')}
          colorKey="pnl"
        />
        <MetricCard label="Sortino Ratio" value={metrics.sortino_ratio} formatter={formatRatio} />
      </div>

      <Card>
        <CardContent className="pt-6">
          <p className="mb-3 text-sm font-semibold text-muted-foreground">Equity Curve</p>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                <defs>
                  <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={colors.area1} stopOpacity={0.25} />
                    <stop offset="100%" stopColor={colors.area1} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => formatDate(d, timezone)} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => formatCurrency(Number(v))} />
                <Tooltip
                  formatter={(v) => formatCurrency(Number(v ?? 0)) as React.ReactNode}
                  labelFormatter={(d) => formatDate(String(d), timezone)}
                />
                <Area
                  type="monotone"
                  dataKey="equity"
                  stroke={colors.area1}
                  fill="url(#equityGradient)"
                  strokeWidth={1.5}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground">No equity curve data</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0 pt-4">
          <div className="px-4">
            <p className="text-sm font-semibold text-muted-foreground">Trades</p>
          </div>
          {trades.length > 0 ? (
            <div className="mt-2 max-h-[min(60vh,480px)] overflow-auto">
              <table className="w-full border-collapse text-sm">
                <thead className="sticky top-0 z-10 border-b border-border bg-card">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-muted-foreground" scope="col">
                      Date
                    </th>
                    <th className="px-4 py-2 text-left font-medium text-muted-foreground" scope="col">
                      Symbol
                    </th>
                    <th className="px-4 py-2 text-left font-medium text-muted-foreground" scope="col">
                      Side
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-muted-foreground" scope="col">
                      Qty
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-muted-foreground" scope="col">
                      Price
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-muted-foreground" scope="col">
                      P&L
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade, idx) => (
                    <tr key={`${trade.symbol}-${trade.date}-${idx}`} className="border-b border-border/80 last:border-0">
                      <td className="px-4 py-2">{formatDate(trade.date, timezone)}</td>
                      <td className="px-4 py-2 font-mono font-semibold">{trade.symbol}</td>
                      <td className="px-4 py-2">
                        <Badge
                          variant="outline"
                          className={
                            trade.side === 'buy'
                              ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300'
                              : 'border-destructive/40 bg-destructive/10 text-destructive'
                          }
                        >
                          {trade.side === 'buy' ? 'Buy' : 'Sell'}
                        </Badge>
                      </td>
                      <td className="px-4 py-2 text-right">{trade.quantity.toLocaleString()}</td>
                      <td className="px-4 py-2 text-right">{formatCurrency(trade.price)}</td>
                      <td
                        className={cn(
                          'px-4 py-2 text-right',
                          trade.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : trade.pnl < 0 ? 'text-destructive' : ''
                        )}
                      >
                        {formatCurrency(trade.pnl)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-4">
              <p className="text-sm text-muted-foreground">No trades</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
