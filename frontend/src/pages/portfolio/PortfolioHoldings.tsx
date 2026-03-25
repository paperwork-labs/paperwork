import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Text,
  HStack,
  Button,
  CardRoot,
  CardBody,
  Badge,
} from '@chakra-ui/react';
import { FiRefreshCw } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ChartContext, SymbolLink, ChartSlidePanel } from '../../components/market/SymbolChartUI';
import SortableTable, { type Column, type FilterGroup } from '../../components/SortableTable';
import FinvizHeatMap, { type FinvizData } from '../../components/charts/FinvizHeatMap';
import { TableSkeleton } from '../../components/shared/Skeleton';
import { useAccountFilter } from '../../hooks/useAccountFilter';
import PageHeader from '../../components/ui/PageHeader';
import StageBadge from '../../components/shared/StageBadge';
import PnlText from '../../components/shared/PnlText';
import { usePositions, usePortfolioSync, usePortfolioAccounts } from '../../hooks/usePortfolio';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney, formatDateShort } from '../../utils/format';
import { buildAccountsFromPositions } from '../../utils/portfolio';
import type { AccountData } from '../../hooks/useAccountFilter';
import type { EnrichedPosition } from '../../types/portfolio';
import TradeModal from '../../components/orders/TradeModal';

type TradeTarget = { symbol: string; currentPrice: number; sharesHeld: number; averageCost?: number; positionId?: number } | null;

function isNonOptionPosition(p: EnrichedPosition): boolean {
  const t = String((p as { instrument_type?: string; asset_class?: string })?.instrument_type ?? (p as { instrument_type?: string; asset_class?: string })?.asset_class ?? '').toLowerCase();
  return !t.includes('option');
}

const HOLDINGS_FILTER_PRESETS: Array<{ label: string; filters: FilterGroup }> = [
  {
    label: 'Stage 2 (Uptrend)',
    filters: {
      conjunction: 'OR',
      rules: [
        { id: 's2a', columnKey: 'stage_label', operator: 'equals', valueSource: 'literal', value: '2A' },
        { id: 's2b', columnKey: 'stage_label', operator: 'equals', valueSource: 'literal', value: '2B' },
        { id: 's2c', columnKey: 'stage_label', operator: 'equals', valueSource: 'literal', value: '2C' },
      ],
    },
  },
  {
    label: 'Winners',
    filters: { conjunction: 'AND', rules: [{ id: 'w', columnKey: 'unrealized_pnl', operator: 'gt', valueSource: 'literal', value: '0' }] },
  },
  {
    label: 'Losers',
    filters: { conjunction: 'AND', rules: [{ id: 'l', columnKey: 'unrealized_pnl', operator: 'lt', valueSource: 'literal', value: '0' }] },
  },
  {
    label: 'Declining (3+4)',
    filters: {
      conjunction: 'OR',
      rules: [
        { id: 's3', columnKey: 'stage_label', operator: 'equals', valueSource: 'literal', value: '3' },
        { id: 's4', columnKey: 'stage_label', operator: 'equals', valueSource: 'literal', value: '4' },
      ],
    },
  },
  {
    label: 'High RS (>80)',
    filters: { conjunction: 'AND', rules: [{ id: 'hrs', columnKey: 'rs_mansfield_pct', operator: 'gt', valueSource: 'literal', value: '80' }] },
  },
  {
    label: 'Oversold (RSI<30)',
    filters: { conjunction: 'AND', rules: [{ id: 'os', columnKey: 'rsi', operator: 'lt', valueSource: 'literal', value: '30' }] },
  },
  {
    label: 'Concentrated (>10%)',
    filters: { conjunction: 'AND', rules: [{ id: 'conc', columnKey: 'weight_pct', operator: 'gt', valueSource: 'literal', value: '10' }] },
  },
];

const PortfolioHoldings: React.FC = () => {
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [tradeTarget, setTradeTarget] = useState<TradeTarget>(null);
  const navigate = useNavigate();
  const { currency, timezone } = useUserPreferences();
  const positionsQuery = usePositions();
  const accountsQuery = usePortfolioAccounts();
  const syncMutation = usePortfolioSync();

  const positions = useMemo(() => {
    const raw = (positionsQuery.data ?? []) as EnrichedPosition[];
    return raw.filter(isNonOptionPosition);
  }, [positionsQuery.data]);

  const rawAccounts = accountsQuery.data ?? [];
  const accounts: AccountData[] = useMemo(
    () =>
      buildAccountsFromPositions(
        rawAccounts.map((a: any) => ({
          id: a.id,
          account_number: a.account_number ?? String(a.id),
          broker: a.broker ?? 'Unknown',
          account_name: a.account_name,
          account_type: a.account_type,
        })),
        positions
      ),
    [rawAccounts, positions]
  );

  const filterState = useAccountFilter(positions as import('../../hooks/useAccountFilter').FilterableItem[], accounts);
  const filtered = filterState.filteredData as EnrichedPosition[];

  const priceRefreshTriggered = useRef(false);
  useEffect(() => {
    if (priceRefreshTriggered.current || positions.length === 0 || positionsQuery.isPending) return;
    const missingPrice = positions.some(p => Number(p.current_price ?? 0) === 0 && Number(p.shares ?? (p as { quantity?: number }).quantity ?? 0) !== 0);
    if (missingPrice) {
      priceRefreshTriggered.current = true;
      fetch('/api/v1/accounts/prices/refresh', { method: 'POST' })
        .then((response) => {
          if (!response.ok) throw new Error(`Price refresh failed: ${response.status}`);
          setTimeout(() => positionsQuery.refetch(), 3000);
        })
        .catch((err) => {
          priceRefreshTriggered.current = false;
          toast.error(err?.message || 'Failed to refresh prices');
        });
    }
  }, [positions, positionsQuery.isPending]);

  const heatmap = useMemo((): FinvizData[] => {
    return filtered
      .map((p) => ({
        name: String(p.symbol ?? '').toUpperCase() || '—',
        size: Math.max(1, Math.round(Number(p.market_value ?? 0) / 1000)),
        change: Number(p.day_pnl_pct ?? p.perf_1d ?? 0),
        sector: String(p.sector ?? '—'),
        value: Number.isFinite(Number(p.market_value)) ? Number(p.market_value) : 0,
      }))
      .filter((x): x is FinvizData => x.name !== '—')
      .slice(0, 40);
  }, [filtered]);

  const totalValue = useMemo(() => positions.reduce((s, p) => s + Number(p.market_value ?? 0), 0), [positions]);

  const columns: Column<EnrichedPosition>[] = useMemo(
    () => [
      {
        key: 'symbol',
        header: 'Symbol',
        accessor: (p) => p.symbol,
        sortable: true,
        sortType: 'string',
        render: (_, row) => (
          <SymbolLink symbol={row.symbol} />
        ),
        width: '100px',
      },
      {
        key: 'account',
        header: 'Account',
        accessor: (p) => `${(p.broker || '').toUpperCase()} ${(p.account_number || '').slice(-4)}`,
        sortable: true,
        sortType: 'string',
        render: (v) => <Text fontSize="xs" color="fg.muted">{String(v)}</Text>,
        width: '110px',
      },
      {
        key: 'shares',
        header: 'Shares',
        accessor: (p) => Number((p as { shares?: number }).shares ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        width: '90px',
      },
      {
        key: 'average_cost',
        header: 'Avg Cost',
        accessor: (p) => p.average_cost != null ? Number(p.average_cost) : null,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => v == null ? <Text fontSize="sm" color="fg.muted" title="Cost basis unavailable (transferred position)">N/A</Text> : <Text fontSize="sm" color="fg.muted">{formatMoney(Number(v), currency)}</Text>,
        width: '100px',
      },
      {
        key: 'current_price',
        header: 'Price',
        accessor: (p) => Number(p.current_price ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => Number(v) === 0 ? <Text fontSize="sm" color="fg.subtle">···</Text> : <Text fontSize="sm" color="fg.muted">{formatMoney(Number(v), currency)}</Text>,
        width: '100px',
      },
      {
        key: 'market_value',
        header: 'Value',
        accessor: (p) => Number(p.market_value ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v, row) => Number(row.current_price ?? 0) === 0 ? <Text fontSize="sm" color="fg.subtle">···</Text> : <Text fontSize="sm" color="fg.muted">{formatMoney(Number(v), currency, { maximumFractionDigits: 0 })}</Text>,
        width: '110px',
      },
      {
        key: 'day_pnl_pct',
        header: 'Day P&L %',
        accessor: (p) => Number(p.day_pnl_pct ?? p.perf_1d ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <PnlText value={Number(v)} format="percent" fontSize="sm" />,
        width: '100px',
      },
      {
        key: 'unrealized_pnl',
        header: 'P&L',
        accessor: (p) => Number(p.unrealized_pnl ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <PnlText value={Number(v)} format="currency" fontSize="sm" currency={currency} />,
        width: '110px',
      },
      {
        key: 'unrealized_pnl_pct',
        header: 'P&L %',
        accessor: (p) => Number(p.unrealized_pnl_pct ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <PnlText value={Number(v)} format="percent" fontSize="sm" />,
        width: '90px',
      },
      {
        key: 'weight_pct',
        header: 'Weight %',
        accessor: (p) => (totalValue ? (Number(p.market_value ?? 0) / totalValue) * 100 : 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <Text fontSize="sm" color="fg.muted">{Number(v).toFixed(1)}%</Text>,
        width: '90px',
      },
      {
        key: 'stage_label',
        header: 'Stage',
        accessor: (p) => p.stage_label ?? '—',
        sortable: true,
        sortType: 'string',
        render: (v) => (v && v !== '—' ? <StageBadge stage={String(v)} size="sm" /> : <Text fontSize="xs" color="fg.muted">—</Text>),
        width: '70px',
      },
      {
        key: 'rs_mansfield_pct',
        header: 'RS %',
        accessor: (p) => Number(p.rs_mansfield_pct ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => (
          <Text fontSize="sm" color={Number(v) >= 0 ? 'status.success' : 'fg.muted'}>
            {Number(v).toFixed(1)}%
          </Text>
        ),
        width: '80px',
      },
      {
        key: 'current_stage_days',
        header: 'Stage Days',
        accessor: (p) => (p as any).current_stage_days ?? null,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => {
          const n = Number(v);
          return n ? <Text fontSize="sm" color="fg.muted">{n}d</Text> : <Text fontSize="sm" color="fg.muted">—</Text>;
        },
        width: '80px',
      },
      {
        key: 'td_signal',
        header: 'TD Seq',
        accessor: (p) => {
          const buy = (p as any).td_buy_setup ?? 0;
          const sell = (p as any).td_sell_setup ?? 0;
          return buy >= 9 ? buy : sell >= 9 ? -sell : buy > sell ? buy : -sell;
        },
        sortable: true,
        sortType: 'number',
        render: (_, row) => {
          const r = row as any;
          const parts: string[] = [];
          if (r.td_buy_complete) parts.push('Buy 9');
          else if (r.td_buy_setup >= 7) parts.push(`B${r.td_buy_setup}`);
          if (r.td_sell_complete) parts.push('Sell 9');
          else if (r.td_sell_setup >= 7) parts.push(`S${r.td_sell_setup}`);
          if (r.td_buy_countdown >= 12) parts.push(`BC${r.td_buy_countdown}`);
          if (r.td_sell_countdown >= 12) parts.push(`SC${r.td_sell_countdown}`);
          if (!parts.length) return <Text fontSize="xs" color="fg.muted">—</Text>;
          return (
            <HStack gap={0.5}>
              {parts.map((p, i) => (
                <Badge key={i} size="sm" variant="outline" colorPalette={p.startsWith('B') ? 'green' : 'red'}>{p}</Badge>
              ))}
            </HStack>
          );
        },
        width: '90px',
      },
      {
        key: 'gaps',
        header: 'Gaps',
        accessor: (p) => ((p as any).gaps_unfilled_up ?? 0) + ((p as any).gaps_unfilled_down ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (_, row) => {
          const up = (row as any).gaps_unfilled_up ?? 0;
          const dn = (row as any).gaps_unfilled_down ?? 0;
          if (!up && !dn) return <Text fontSize="xs" color="fg.muted">—</Text>;
          return (
            <HStack gap={1}>
              {up > 0 && <Text fontSize="xs" color="green.400">{up}↑</Text>}
              {dn > 0 && <Text fontSize="xs" color="red.400">{dn}↓</Text>}
            </HStack>
          );
        },
        width: '70px',
      },
      {
        key: 'pe_ttm',
        header: 'P/E',
        accessor: (p) => (p as any).pe_ttm ?? null,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => {
          if (v == null) return <Text fontSize="xs" color="fg.muted">—</Text>;
          const n = Number(v);
          const color = n < 0 ? 'red.400' : n > 50 ? 'yellow.400' : 'fg.muted';
          return <Text fontSize="xs" color={color}>{n.toFixed(1)}</Text>;
        },
        width: '65px',
      },
      {
        key: 'next_earnings',
        header: 'Earnings',
        accessor: (p) => (p as any).next_earnings ?? null,
        sortable: true,
        sortType: 'date',
        render: (v) => {
          if (!v) return <Text fontSize="xs" color="fg.muted">—</Text>;
          const d = new Date(String(v));
          if (isNaN(d.getTime())) return <Text fontSize="xs" color="fg.muted">—</Text>;
          const daysOut = Math.ceil((d.getTime() - Date.now()) / (1000 * 86400));
          const color = daysOut <= 7 ? 'yellow.400' : 'fg.muted';
          return <Text fontSize="xs" color={color}>{formatDateShort(v, timezone)}</Text>;
        },
        width: '80px',
      },
      {
        key: 'cost_basis',
        header: 'Cost Basis',
        accessor: (p) => {
          if (p.cost_basis != null) return Number(p.cost_basis);
          if (p.average_cost != null) return Number(p.average_cost) * Number((p as any).shares ?? 0);
          return null;
        },
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => v == null ? <Text fontSize="sm" color="fg.muted" title="Cost basis unavailable (transferred position)">N/A</Text> : <Text fontSize="sm" color="fg.muted">{formatMoney(Number(v), currency, { maximumFractionDigits: 0 })}</Text>,
        width: '110px',
      },
      {
        key: 'perf_5d',
        header: '5D %',
        accessor: (p) => Number((p as any).perf_5d ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <PnlText value={Number(v)} format="percent" fontSize="sm" />,
        width: '80px',
        hidden: true,
      },
      {
        key: 'perf_20d',
        header: '20D %',
        accessor: (p) => Number((p as any).perf_20d ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <PnlText value={Number(v)} format="percent" fontSize="sm" />,
        width: '80px',
        hidden: true,
      },
      {
        key: 'rsi',
        header: 'RSI',
        accessor: (p) => Number((p as any).rsi ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => {
          const n = Number(v);
          const color = n > 70 ? 'status.danger' : n < 30 ? 'status.success' : 'fg.muted';
          return <Text fontSize="sm" color={color}>{n ? n.toFixed(0) : '—'}</Text>;
        },
        width: '65px',
        hidden: true,
      },
      {
        key: 'atr_14',
        header: 'ATR',
        accessor: (p) => Number((p as any).atr_14 ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <Text fontSize="sm" color="fg.muted">{Number(v) ? Number(v).toFixed(2) : '—'}</Text>,
        width: '75px',
        hidden: true,
      },
      {
        key: 'sector',
        header: 'Sector',
        accessor: (p) => (p.sector as string) ?? '—',
        sortable: true,
        sortType: 'string',
        render: (v) => <Text fontSize="xs" color="fg.muted">{String(v || '—')}</Text>,
        width: '100px',
      },
      {
        key: 'market_cap_label',
        header: 'Market Cap',
        accessor: (p) => (p as any).market_cap_label ?? '—',
        sortable: true,
        sortType: 'string',
        render: (v) => <Text fontSize="xs" color="fg.muted">{String(v || '—')}</Text>,
        width: '100px',
      },
      {
        key: 'industry',
        header: 'Industry',
        accessor: (p) => ((p as any).industry as string) ?? '—',
        sortable: true,
        sortType: 'string',
        render: (v) => <Text fontSize="xs" color="fg.muted">{String(v || '—')}</Text>,
        width: '120px',
      },
      {
        key: 'actions',
        header: '',
        accessor: () => '',
        sortable: false,
        render: (_, row) => (
          <Button
            size="xs"
            variant="outline"
            colorPalette="blue"
            onClick={(e) => {
              e.stopPropagation();
              setTradeTarget({
                symbol: row.symbol,
                currentPrice: Number(row.current_price ?? 0),
                sharesHeld: Number((row as any).shares ?? 0),
                averageCost: row.average_cost != null ? Number(row.average_cost) : undefined,
                positionId: row.id,
              });
            }}
          >
            Trade
          </Button>
        ),
        width: '60px',
      },
    ],
    [currency, totalValue, timezone]
  );

  const openChart = (symbol: string) => setChartSymbol(symbol);

  const handleRowClick = (row: EnrichedPosition) => {
    navigate(`/portfolio/workspace?symbol=${encodeURIComponent(row.symbol)}`);
  };

  return (
    <ChartContext.Provider value={openChart}>
      <Box p={4}>
        <PageHeader
          title="Holdings"
          subtitle="Stocks and ETFs with market data (stage, RS)"
          rightContent={
            <HStack gap={2}>
              <Button
                size="sm"
                variant={showHeatmap ? 'solid' : 'outline'}
                colorPalette="brand"
                onClick={() => setShowHeatmap(!showHeatmap)}
              >
                Heatmap
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => syncMutation.mutate()}
                loading={syncMutation.isPending}
              >
                <HStack gap={2}><FiRefreshCw /> Sync</HStack>
              </Button>
            </HStack>
          }
        />

        {(positionsQuery.isPending || accountsQuery.isPending) ? (
          <TableSkeleton rows={8} cols={6} />
        ) : (positionsQuery.error || accountsQuery.error) ? (
          <Text color="status.danger">Failed to load holdings</Text>
        ) : (
          <Box display="flex" flexDirection="column" gap={4}>
            {showHeatmap && heatmap.length > 0 && (
              <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                <CardBody>
                  <FinvizHeatMap data={heatmap} height={320} />
                </CardBody>
              </CardRoot>
            )}

            <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
              <CardBody>
                <HStack justify="space-between" mb={2}>
                  <Badge colorPalette="gray">{filtered.length} positions</Badge>
                </HStack>
                <SortableTable
                  data={filtered as EnrichedPosition[]}
                  columns={columns}
                  defaultSortBy="market_value"
                  defaultSortOrder="desc"
                  size="sm"
                  maxHeight="70vh"
                  emptyMessage="No holdings found."
                  filtersEnabled
                  filterPresets={HOLDINGS_FILTER_PRESETS}
                  onRowClick={handleRowClick}
                />
              </CardBody>
            </CardRoot>
          </Box>
        )}
      </Box>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
      {tradeTarget && (
        <TradeModal
          isOpen={!!tradeTarget}
          onClose={() => setTradeTarget(null)}
          symbol={tradeTarget.symbol}
          currentPrice={tradeTarget.currentPrice}
          sharesHeld={tradeTarget.sharesHeld}
          averageCost={tradeTarget.averageCost}
          positionId={tradeTarget.positionId}
          onOrderPlaced={() => positionsQuery.refetch()}
        />
      )}
    </ChartContext.Provider>
  );
};

export default PortfolioHoldings;
