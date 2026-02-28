import React, { useMemo, useState } from 'react';
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
import { ChartContext, SymbolLink, ChartSlidePanel } from '../../components/market/SymbolChartUI';
import SortableTable, { type Column, type FilterGroup } from '../../components/SortableTable';
import FinvizHeatMap, { type FinvizData } from '../../components/charts/FinvizHeatMap';
import { TableSkeleton } from '../../components/shared/Skeleton';
import AccountFilterWrapper from '../../components/ui/AccountFilterWrapper';
import PageHeader from '../../components/ui/PageHeader';
import StageBadge from '../../components/shared/StageBadge';
import PnlText from '../../components/shared/PnlText';
import { usePositions, usePortfolioSync, usePortfolioAccounts } from '../../hooks/usePortfolio';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney } from '../../utils/format';
import { buildAccountsFromPositions } from '../../utils/portfolio';
import type { AccountData } from '../../hooks/useAccountFilter';
import type { EnrichedPosition } from '../../types/portfolio';

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
  const navigate = useNavigate();
  const { currency } = useUserPreferences();
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

  const heatmap = useMemo((): FinvizData[] => {
    return positions
      .map((p) => ({
        name: String(p.symbol ?? '').toUpperCase() || '—',
        size: Math.max(1, Math.round(Number(p.market_value ?? 0) / 1000)),
        change: Number(p.day_pnl_pct ?? p.perf_1d ?? 0),
        sector: String(p.sector ?? '—'),
        value: Number.isFinite(Number(p.market_value)) ? Number(p.market_value) : 0,
      }))
      .filter((x): x is FinvizData => x.name !== '—')
      .slice(0, 40);
  }, [positions]);

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
        accessor: (p) => Number(p.average_cost ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <Text fontSize="sm" color="fg.muted">{formatMoney(Number(v), currency)}</Text>,
        width: '100px',
      },
      {
        key: 'current_price',
        header: 'Price',
        accessor: (p) => Number(p.current_price ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <Text fontSize="sm" color="fg.muted">{formatMoney(Number(v), currency)}</Text>,
        width: '100px',
      },
      {
        key: 'market_value',
        header: 'Value',
        accessor: (p) => Number(p.market_value ?? 0),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <Text fontSize="sm" color="fg.muted">{formatMoney(Number(v), currency, { maximumFractionDigits: 0 })}</Text>,
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
        key: 'cost_basis',
        header: 'Cost Basis',
        accessor: (p) => Number(p.cost_basis ?? (Number(p.average_cost ?? 0) * Number((p as any).shares ?? 0))),
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <Text fontSize="sm" color="fg.muted">{formatMoney(Number(v), currency, { maximumFractionDigits: 0 })}</Text>,
        width: '110px',
        hidden: true,
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
        hidden: true,
      },
      {
        key: 'industry',
        header: 'Industry',
        accessor: (p) => ((p as any).industry as string) ?? '—',
        sortable: true,
        sortType: 'string',
        render: (v) => <Text fontSize="xs" color="fg.muted">{String(v || '—')}</Text>,
        width: '120px',
        hidden: true,
      },
    ],
    [currency, totalValue]
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
                loading={syncMutation.isLoading}
              >
                <HStack gap={2}><FiRefreshCw /> Sync</HStack>
              </Button>
            </HStack>
          }
        />

        <AccountFilterWrapper
          data={positions as import('../../hooks/useAccountFilter').FilterableItem[]}
          accounts={accounts}
          config={{ showAllOption: true, showSummary: false, variant: 'simple' }}
          loading={positionsQuery.isLoading || accountsQuery.isLoading}
          error={positionsQuery.error || accountsQuery.error ? 'Failed to load holdings' : null}
          loadingComponent={<TableSkeleton rows={8} cols={6} />}
        >
          {(filtered) => (
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
                    emptyMessage={positionsQuery.isLoading ? 'Loading…' : 'No holdings found.'}
                    filtersEnabled
                    filterPresets={HOLDINGS_FILTER_PRESETS}
                    onRowClick={handleRowClick}
                  />
                </CardBody>
              </CardRoot>
            </Box>
          )}
        </AccountFilterWrapper>
      </Box>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
};

export default PortfolioHoldings;
