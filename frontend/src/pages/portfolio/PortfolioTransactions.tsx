import React, { useMemo, useState, useEffect } from 'react';
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
import { TableSkeleton } from '../../components/shared/Skeleton';
// AccountFilterWrapper removed -- uses global header selector now
import Pagination from '../../components/ui/Pagination';
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

const CATEGORIES = [
  'TRADE',
  'DIVIDEND',
  'PAYMENT_IN_LIEU',
  'WITHHOLDING_TAX',
  'COMMISSION',
  'BROKER_INTEREST_PAID',
  'BROKER_INTEREST_RECEIVED',
  'DEPOSIT',
  'TRANSFER',
  'INTEREST',
  'OTHER_FEE',
  'TAX_REFUND',
  'OTHER',
  '',
] as const;
const SIDES = ['BUY', 'SELL', ''] as const;

const PortfolioTransactions: React.FC = () => {
  const [dateRange, setDateRange] = useState<string>('30d');
  const [category, setCategory] = useState<string>('');
  const [side, setSide] = useState<string>('');
  const [symbolSearch, setSymbolSearch] = useState<string>('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
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
      limit: pageSize,
      offset: (page - 1) * pageSize,
    }),
    [accountIdForApi, start, end, debouncedSymbol, category, side, page, pageSize]
  );

  useEffect(() => {
    setPage(1);
  }, [dateRange, category, side, debouncedSymbol, selected]);

  const activityQuery = useActivity(activityParams);
  const syncMutation = usePortfolioSync();

  const activity = useMemo(() => {
    const data = activityQuery.data as import('../../services/api').ActivityResponse | undefined;
    const rows = data?.data?.activity ?? data?.activity ?? [];
    return (Array.isArray(rows) ? rows : []) as ActivityRow[];
  }, [activityQuery.data]);

  type ActivityResp = { total?: number; data?: { total?: number } };
  const resp = activityQuery.data as ActivityResp | undefined;
  const apiTotal = resp?.total ?? resp?.data?.total;
  const hasApiTotal = apiTotal !== undefined && apiTotal !== null;
  const total = hasApiTotal ? apiTotal! : activity.length;

  const summary = useMemo(() => {
    const amt = (r: ActivityRow) => Number(r.amount ?? r.net_amount ?? 0);
    let dividends = 0;
    let feesCommissions = 0;
    let interestReceived = 0;
    for (const r of activity) {
      const c = r.category ?? '';
      const a = amt(r);
      if (c === 'DIVIDEND') dividends += a;
      else if (['COMMISSION', 'OTHER_FEE', 'BROKER_INTEREST_PAID'].includes(c)) feesCommissions += a;
      else if (['BROKER_INTEREST_RECEIVED', 'INTEREST'].includes(c)) interestReceived += a;
    }
    return { dividends, feesCommissions, interestReceived };
  }, [activity]);

  const accountLookup = useMemo(() => {
    const map: Record<number, string> = {};
    for (const a of rawAccounts as Array<{ id?: number; broker?: string; account_number?: string }>) {
      if (a.id) map[a.id] = a.broker ?? a.account_number ?? String(a.id);
    }
    return map;
  }, [rawAccounts]);

  const columns: Column<ActivityRow>[] = useMemo(
    () => [
      {
        key: 'ts',
        header: 'Date',
        accessor: (r) => r.ts,
        sortable: true,
        sortType: 'string',
        render: (v) => <Text fontSize="sm">{typeof v === 'string' ? v.slice(0, 16).replace('T', ' ') : '—'}</Text>,
        width: '130px',
      },
      {
        key: 'account',
        header: 'Account',
        accessor: (r) => r.account_id ?? 0,
        sortable: true,
        sortType: 'number',
        render: (v) => <Text fontSize="xs" color="fg.muted">{accountLookup[Number(v)] ?? '—'}</Text>,
        width: '90px',
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
    [currency, accountLookup]
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

        {accountsQuery.isLoading ? (
          <TableSkeleton rows={10} cols={7} />
        ) : (activityQuery.error || accountsQuery.error) ? (
          <Text color="status.danger">Failed to load activity</Text>
        ) : (
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
                  {activityQuery.isLoading ? (
                    <TableSkeleton rows={10} cols={7} />
                  ) : (
                    <>
                      <HStack
                        gap={4}
                        p={3}
                        mb={3}
                        borderRadius="md"
                        bg="bg.muted"
                        flexWrap="wrap"
                        fontSize="sm"
                      >
                        <HStack gap={2}>
                          <Text color="fg.muted">Dividends:</Text>
                          <Text color={summary.dividends >= 0 ? 'status.success' : 'status.danger'}>
                            {formatMoney(summary.dividends, currency)}
                          </Text>
                        </HStack>
                        <HStack gap={2}>
                          <Text color="fg.muted">Fees/Commissions:</Text>
                          <Text color={summary.feesCommissions <= 0 ? 'status.danger' : 'status.success'}>
                            {formatMoney(summary.feesCommissions, currency)}
                          </Text>
                        </HStack>
                        <HStack gap={2}>
                          <Text color="fg.muted">Interest received:</Text>
                          <Text color={summary.interestReceived >= 0 ? 'status.success' : 'status.danger'}>
                            {formatMoney(summary.interestReceived, currency)}
                          </Text>
                        </HStack>
                      </HStack>
                      <HStack justify="space-between" mb={2}>
                        <Badge colorPalette="gray">
                          {hasApiTotal ? `${activity.length} of ${total}` : `${activity.length} rows (this page)`}
                        </Badge>
                      </HStack>
                      <SortableTable
                        data={activity}
                        columns={columns}
                        defaultSortBy="ts"
                        defaultSortOrder="desc"
                        size="sm"
                        maxHeight="70vh"
                        emptyMessage="No activity in this range."
                      />
                      <Pagination
                        page={page}
                        pageSize={pageSize}
                        total={total}
                        onPageChange={setPage}
                        onPageSizeChange={(ps) => {
                          setPageSize(ps);
                          setPage(1);
                        }}
                      />
                    </>
                  )}
                </CardBody>
              </CardRoot>
          </>
        )}
      </Stack>
    </Box>
  );
};

export default PortfolioTransactions;
