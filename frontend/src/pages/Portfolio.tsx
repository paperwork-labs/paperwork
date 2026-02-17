import React from 'react';
import { Box, HStack, Text, Button, CardRoot, CardBody, Badge } from '@chakra-ui/react';
import { FiRefreshCw } from 'react-icons/fi';
import { usePortfolio } from '../hooks/usePortfolio';
import SortableTable, { type Column } from '../components/SortableTable';
import FinvizHeatMap from '../components/charts/FinvizHeatMap';
import AccountFilterWrapper from '../components/ui/AccountFilterWrapper';
import { transformPortfolioToAccounts } from '../hooks/useAccountFilter';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { formatMoney } from '../utils/format';

type AnyPos = any;

function isNonOptionPosition(p: AnyPos): boolean {
  const t = String(p?.instrument_type || p?.asset_class || p?.type || '').toLowerCase();
  return !(t.includes('option') || t.includes('opt'));
}

const Portfolio: React.FC = () => {
  const q = usePortfolio();
  const data = (q.data as any) || {};
  const accounts = transformPortfolioToAccounts(data);
  const { currency } = useUserPreferences();

  const positions: AnyPos[] = React.useMemo(() => {
    const accs = Object.values<any>(data?.accounts || {});
    const all = accs.flatMap((a: any) => a?.all_positions || []);
    return all.filter(isNonOptionPosition);
  }, [data]);

  const heatmap = React.useMemo(() => {
    return positions
      .map((p: any) => {
        const symbol = String(p?.symbol || p?.instrument?.symbol || '').toUpperCase();
        const value = Number(p?.market_value ?? p?.marketValue ?? p?.value ?? 0);
        const change = Number(p?.day_change_pct ?? p?.dayChangePct ?? p?.pnl_pct ?? 0);
        const sector = String(p?.sector || '—');
        return {
          name: symbol || '—',
          size: Math.max(1, Math.round(value / 1000)),
          change,
          sector,
          value: Number.isFinite(value) ? value : 0,
        };
      })
      .filter((x: any) => x.name !== '—')
      .slice(0, 40);
  }, [positions]);

  const columns: Column<AnyPos>[] = [
    {
      key: 'symbol',
      header: 'Symbol',
      accessor: (p) => String(p?.symbol || p?.instrument?.symbol || ''),
      sortable: true,
      sortType: 'string',
      render: (v) => (
        <Text fontFamily="mono" fontSize="12px">
          {String(v || '—')}
        </Text>
      ),
      width: '120px',
    },
    {
      key: 'qty',
      header: 'Qty',
      accessor: (p) => Number(p?.quantity ?? p?.qty ?? 0),
      sortable: true,
      sortType: 'number',
      isNumeric: true,
      width: '90px',
    },
    {
      key: 'value',
      header: 'Value',
      accessor: (p) => Number(p?.market_value ?? p?.marketValue ?? p?.value ?? 0),
      sortable: true,
      sortType: 'number',
      isNumeric: true,
      render: (v) => (
        <Text fontSize="12px" color="fg.muted">
          {formatMoney(Number(v || 0), currency, { maximumFractionDigits: 0 })}
        </Text>
      ),
      width: '160px',
    },
    {
      key: 'pnl',
      header: 'P&L',
      accessor: (p) => Number(p?.unrealized_pnl ?? p?.unrealizedPnL ?? p?.pnl ?? 0),
      sortable: true,
      sortType: 'number',
      isNumeric: true,
      render: (v) => (
        <Text fontSize="12px" color={Number(v || 0) >= 0 ? 'status.success' : 'status.danger'}>
          {formatMoney(Number(v || 0), currency, { maximumFractionDigits: 0 })}
        </Text>
      ),
      width: '160px',
    },
  ];

  return (
    <Box>
      <HStack justify="space-between" mb={3}>
        <Box>
          <Text fontSize="lg" fontWeight="semibold" color="fg.default">
            Portfolio
          </Text>
          <Text fontSize="sm" color="fg.muted">
            v3-safe view (stocks/ETFs)
          </Text>
        </Box>
        <Button size="sm" variant="outline" onClick={() => q.refetch()} loading={q.isFetching}>
          <FiRefreshCw />
          <Box as="span" ml={2}>
            Reload
          </Box>
        </Button>
      </HStack>

      <AccountFilterWrapper
        data={positions}
        accounts={accounts}
        config={{ showSummary: false, showAllOption: true, variant: 'simple' }}
      >
        {(filtered) => (
          <Box display="flex" flexDirection="column" gap={3}>
            <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
              <CardBody>
                <HStack justify="space-between">
                  <Text fontWeight="semibold">Holdings</Text>
                  <Badge colorPalette="gray">{filtered.length}</Badge>
                </HStack>
              </CardBody>
            </CardRoot>

            {heatmap.length ? (
              <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                <CardBody>
                  <FinvizHeatMap data={heatmap as any} height={320} />
                </CardBody>
              </CardRoot>
            ) : null}

            <Box w="full" borderWidth="1px" borderColor="border.subtle" borderRadius="xl" bg="bg.card">
              <SortableTable
                data={filtered}
                columns={columns}
                defaultSortBy="value"
                defaultSortOrder="desc"
                size="sm"
                maxHeight="70vh"
                emptyMessage={q.isLoading ? 'Loading…' : 'No holdings found.'}
              />
            </Box>
          </Box>
        )}
      </AccountFilterWrapper>
    </Box>
  );
};

export default Portfolio;

