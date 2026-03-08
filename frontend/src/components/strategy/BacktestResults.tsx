import React from 'react';
import {
  Box,
  Text,
  SimpleGrid,
  CardRoot,
  CardBody,
  Badge,
  VStack,
  TableScrollArea,
  TableRoot,
  TableHeader,
  TableBody,
  TableRow,
  TableColumnHeader,
  TableCell,
} from '@chakra-ui/react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { BacktestResult, BacktestMetrics, BacktestTrade } from '../../types/strategy';
import { useChartColors } from '../../hooks/useChartColors';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney } from '../../utils/format';

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

function colorForValue(value: number, isPercent = false): string {
  if (isPercent || Math.abs(value) < 1e-9) {
    return value > 0 ? 'status.success' : value < 0 ? 'status.danger' : 'fg.default';
  }
  return value > 0 ? 'status.success' : value < 0 ? 'status.danger' : 'fg.default';
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
  const colorForValueFn = () => {
    if (colorKey === 'percent' || colorKey === 'pnl') {
      return colorForValue(value ?? 0, colorKey === 'percent');
    }
    return 'fg.default';
  };
  const color = colorForValueFn();
  const formattedValue = formatter(value);
  return (
    <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
      <CardBody p={3}>
        <Text fontSize="xs" color="fg.muted">
          {label}
        </Text>
        <Text fontSize="lg" fontWeight="bold" color={color}>
          {formattedValue}
        </Text>
      </CardBody>
    </CardRoot>
  );
}

export default function BacktestResults({ result }: { result: BacktestResult }) {
  const { metrics, equity_curve, trades } = result;
  const colors = useChartColors();
  const { currency } = useUserPreferences();

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
    <VStack align="stretch" gap={6}>
      {/* Metrics cards */}
      <SimpleGrid columns={{ base: 2, md: 4 }} gap={3}>
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
        <MetricCard
          label="Sharpe Ratio"
          value={metrics.sharpe_ratio}
          formatter={formatRatio}
        />
        <MetricCard
          label="Win Rate"
          value={metrics.win_rate}
          formatter={(v) => (v != null && Number.isFinite(v) ? `${(v * 100).toFixed(1)}%` : '—')}
        />
        <MetricCard
          label="Profit Factor"
          value={metrics.profit_factor}
          formatter={formatRatio}
        />
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
        <MetricCard
          label="Sortino Ratio"
          value={metrics.sortino_ratio}
          formatter={formatRatio}
        />
      </SimpleGrid>

      {/* Equity curve */}
      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
        <CardBody>
          <Text fontSize="sm" fontWeight="semibold" color="fg.muted" mb={3}>
            Equity Curve
          </Text>
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
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10 }}
                  tickFormatter={(d) => formatDate(d)}
                />
                <YAxis
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => formatCurrency(Number(v))}
                />
                <Tooltip
                  formatter={(v: number | undefined) => formatCurrency(Number(v ?? 0)) as React.ReactNode}
                  labelFormatter={(d) => formatDate(d)}
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
            <Text fontSize="sm" color="fg.muted">
              No equity curve data
            </Text>
          )}
        </CardBody>
      </CardRoot>

      {/* Trade list table */}
      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
        <CardBody p={0}>
          <Box px={4} pt={4}>
            <Text fontSize="sm" fontWeight="semibold" color="fg.muted">
              Trades
            </Text>
          </Box>
          {trades.length > 0 ? (
            <TableScrollArea>
              <TableRoot size="sm">
                <TableHeader>
                  <TableRow>
                    <TableColumnHeader>Date</TableColumnHeader>
                    <TableColumnHeader>Symbol</TableColumnHeader>
                    <TableColumnHeader>Side</TableColumnHeader>
                    <TableColumnHeader textAlign="end">Qty</TableColumnHeader>
                    <TableColumnHeader textAlign="end">Price</TableColumnHeader>
                    <TableColumnHeader textAlign="end">P&L</TableColumnHeader>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {trades.map((trade, idx) => (
                    <TableRow key={`${trade.symbol}-${trade.date}-${idx}`}>
                      <TableCell>{formatDate(trade.date)}</TableCell>
                      <TableCell>
                        <Text fontFamily="mono" fontWeight="semibold">
                          {trade.symbol}
                        </Text>
                      </TableCell>
                      <TableCell>
                        <Badge
                          colorPalette={trade.side === 'buy' ? 'green' : 'red'}
                          variant="subtle"
                          size="sm"
                        >
                          {trade.side === 'buy' ? 'Buy' : 'Sell'}
                        </Badge>
                      </TableCell>
                      <TableCell textAlign="end">
                        {trade.quantity.toLocaleString()}
                      </TableCell>
                      <TableCell textAlign="end">
                        {formatCurrency(trade.price)}
                      </TableCell>
                      <TableCell
                        textAlign="end"
                        color={trade.pnl >= 0 ? 'status.success' : trade.pnl < 0 ? 'status.danger' : 'fg.default'}
                      >
                        {formatCurrency(trade.pnl)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </TableRoot>
            </TableScrollArea>
          ) : (
            <Box p={4}>
              <Text fontSize="sm" color="fg.muted">
                No trades
              </Text>
            </Box>
          )}
        </CardBody>
      </CardRoot>
    </VStack>
  );
}
