import React, { useMemo, useState } from 'react';
import {
  Box,
  Text,
  Stack,
  HStack,
  Button,
  CardRoot,
  CardBody,
  Input,
  NativeSelectRoot,
  NativeSelectField,
  NativeSelectIndicator,
  Badge,
} from '@chakra-ui/react';
import { FiRefreshCw } from 'react-icons/fi';
import PageHeader from '../../components/ui/PageHeader';
import AccountFilterWrapper from '../../components/ui/AccountFilterWrapper';
import SortableTable, { type Column } from '../../components/SortableTable';
import { useActivity, usePortfolioSync, usePortfolioAccounts } from '../../hooks/usePortfolio';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { useDebounce } from '../../hooks/useDebounce';
import { useAccountContext } from '../../context/AccountContext';
import { formatMoney } from '../../utils/format';
import { toStartEnd, buildAccountsFromBroker } from '../../utils/portfolio';
import type { AccountData } from '../../hooks/useAccountFilter';
import type { ActivityRow } from '../../types/portfolio';

const DATE_RANGES = [
  { key: '7d', label: '7d' },
  { key: '30d', label: '30d' },
  { key: '90d', label: '90d' },
  { key: 'ytd', label: 'YTD' },
  { key: '1y', label: '1Y' },
  { key: 'all', label: 'All' },
] as const;

const CATEGORIES = ['TRADE', 'DIVIDEND', 'COMMISSION', 'FEE', 'TRANSFER', ''] as const;
const SIDES = ['BUY', 'SELL', ''] as const;

const PortfolioTransactions: React.FC = () => {
  const [dateRange, setDateRange] = useState<string>('30d');
  const [category, setCategory] = useState<string>('');
  const [side, setSide] = useState<string>('');
  const [symbolSearch, setSymbolSearch] = useState<string>('');
  const debouncedSymbol = useDebounce(symbolSearch, 300);
  const { selected } = useAccountContext();

  const { currency } = useUserPreferences();
  const accountsQuery = usePortfolioAccounts();
  const rawAccounts = accountsQuery.data ?? [];
  const accounts = useMemo(() => buildAccountsFromBroker(rawAccounts as import('../../utils/portfolio').BrokerAccountLike[]), [rawAccounts]);

  const { start, end } = useMemo(() => toStartEnd(dateRange), [dateRange]);
  const accountIdForApi = useMemo(() => {
    if (selected === 'all') return undefined;
    const acc = (rawAccounts as { id?: number; account_number?: string }[]).find(
      (a) => (a.account_number ?? String(a.id)) === selected
    );
    return acc?.id as number | undefined;
  }, [selected, rawAccounts]);

  const activityParams = useMemo(
    () => ({
      accountId: accountIdForApi != null ? String(accountIdForApi) : undefined,
      start,
      end,
      symbol: debouncedSymbol.trim() || undefined,
      category: category || undefined,
      side: side || undefined,
      limit: 500,
      offset: 0,
    }),
    [accountIdForApi, start, end, debouncedSymbol, category, side]
  );

  const activityQuery = useActivity(activityParams);
  const syncMutation = usePortfolioSync();

  const activity = useMemo(() => {
    const data = activityQuery.data as any;
    const rows = data?.data?.activity ?? data?.activity ?? [];
    return rows as ActivityRow[];
  }, [activityQuery.data]);

  const columns: Column<ActivityRow>[] = useMemo(
    () => [
      {
        key: 'ts',
        header: 'Date',
        accessor: (r) => r.ts,
        sortable: true,
        sortType: 'string',
        render: (v) => <Text fontSize="sm">{typeof v === 'string' ? v.slice(0, 10) : '—'}</Text>,
        width: '100px',
      },
      {
        key: 'symbol',
        header: 'Symbol',
        accessor: (r) => r.symbol ?? '—',
        sortable: true,
        sortType: 'string',
        render: (v) => <Text fontFamily="mono" fontSize="sm">{String(v ?? '—')}</Text>,
        width: '90px',
      },
      {
        key: 'category',
        header: 'Type',
        accessor: (r) => r.category ?? '—',
        sortable: true,
        sortType: 'string',
        render: (v) => {
          const pal = v === 'DIVIDEND' ? 'green' : v === 'TRADE' ? 'blue' : 'gray';
          return <Badge size="sm" colorPalette={pal}>{String(v ?? '—')}</Badge>;
        },
        width: '100px',
      },
      {
        key: 'side',
        header: 'Side',
        accessor: (r) => r.side ?? '—',
        sortable: true,
        sortType: 'string',
        render: (v) => <Text fontSize="sm" color="fg.muted">{String(v ?? '—')}</Text>,
        width: '70px',
      },
      {
        key: 'quantity',
        header: 'Qty',
        accessor: (r) => r.quantity ?? 0,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <Text fontSize="sm">{v != null ? Number(v) : '—'}</Text>,
        width: '80px',
      },
      {
        key: 'price',
        header: 'Price',
        accessor: (r) => r.price ?? 0,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <Text fontSize="sm" color="fg.muted">{v != null ? formatMoney(Number(v), currency) : '—'}</Text>,
        width: '90px',
      },
      {
        key: 'amount',
        header: 'Amount',
        accessor: (r) => r.amount ?? r.net_amount ?? 0,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => (
          <Text fontSize="sm" color={Number(v ?? 0) >= 0 ? 'status.success' : 'status.danger'}>
            {v != null ? formatMoney(Number(v), currency) : '—'}
          </Text>
        ),
        width: '110px',
      },
      {
        key: 'commission',
        header: 'Commission',
        accessor: (r) => r.commission ?? 0,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <Text fontSize="sm" color="fg.muted">{v != null && Number(v) !== 0 ? formatMoney(Number(v), currency) : '—'}</Text>,
        width: '100px',
      },
    ],
    [currency]
  );

  return (
    <Box p={4}>
      <Stack gap={4}>
        <PageHeader
          title="Transactions"
          subtitle="Unified activity feed (trades, dividends, fees)"
          rightContent={
            <Button
              size="sm"
              variant="outline"
              onClick={() => syncMutation.mutate()}
              loading={syncMutation.isLoading}
            >
              <HStack gap={2}><FiRefreshCw /> Sync</HStack>
            </Button>
          }
        />

        <AccountFilterWrapper
          data={activity as import('../../hooks/useAccountFilter').FilterableItem[]}
          accounts={accounts}
          config={{ showAllOption: true, showSummary: false, variant: 'simple' }}
          loading={activityQuery.isLoading || accountsQuery.isLoading}
          error={activityQuery.error || accountsQuery.error ? 'Failed to load activity' : null}
        >
          {() => (
            <>
              <HStack gap={3} flexWrap="wrap">
                {DATE_RANGES.map((r) => (
                  <Button
                    key={r.key}
                    size="xs"
                    variant={dateRange === r.key ? 'solid' : 'outline'}
                    colorPalette="brand"
                    onClick={() => setDateRange(r.key)}
                  >
                    {r.label}
                  </Button>
                ))}
                <NativeSelectRoot size="sm" w="auto">
                  <NativeSelectField value={category} onChange={(e) => setCategory(e.target.value)}>
                    <option value="">All types</option>
                    {CATEGORIES.filter(Boolean).map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </NativeSelectField>
                  <NativeSelectIndicator />
                </NativeSelectRoot>
                <NativeSelectRoot size="sm" w="auto">
                  <NativeSelectField value={side} onChange={(e) => setSide(e.target.value)}>
                    <option value="">All sides</option>
                    {SIDES.filter(Boolean).map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </NativeSelectField>
                  <NativeSelectIndicator />
                </NativeSelectRoot>
                <Input
                  size="sm"
                  placeholder="Symbol"
                  w="100px"
                  value={symbolSearch}
                  onChange={(e) => setSymbolSearch(e.target.value)}
                />
              </HStack>

              <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                <CardBody>
                  <HStack justify="space-between" mb={2}>
                    <Badge colorPalette="gray">{activity.length} rows</Badge>
                  </HStack>
                  <SortableTable
                    data={activity}
                    columns={columns}
                    defaultSortBy="ts"
                    defaultSortOrder="desc"
                    size="sm"
                    maxHeight="70vh"
                    emptyMessage={activityQuery.isLoading ? 'Loading…' : 'No activity in this range.'}
                  />
                </CardBody>
              </CardRoot>
            </>
          )}
        </AccountFilterWrapper>
      </Stack>
    </Box>
  );
};

export default PortfolioTransactions;
