import React, { useMemo, useState, useEffect } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import PageHeader from '../../components/ui/PageHeader';
import { TableSkeleton } from '../../components/shared/Skeleton';
import Pagination from '../../components/ui/Pagination';
import SortableTable, { type Column } from '../../components/SortableTable';
import { useActivity, usePortfolioSync, usePortfolioAccounts } from '../../hooks/usePortfolio';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { useDebounce } from '../../hooks/useDebounce';
import { useAccountContext } from '../../context/AccountContext';
import { formatMoney } from '../../utils/format';
import { toStartEnd } from '../../utils/portfolio';
import type { ActivityRow } from '../../types/portfolio';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';

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

  const { start, end } = useMemo(() => toStartEnd(dateRange), [dateRange]);
  const accountIdForApi = useMemo(() => {
    if (selected === 'all') return undefined;
    const acc = (rawAccounts as { id?: number; account_number?: string }[]).find(
      (a) => (a.account_number ?? String(a.id)) === selected,
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
    [accountIdForApi, start, end, debouncedSymbol, category, side, page, pageSize],
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
        render: (v) => (
          <span className="text-sm">
            {typeof v === 'string' ? v.slice(0, 16).replace('T', ' ') : '—'}
          </span>
        ),
        width: '130px',
      },
      {
        key: 'account',
        header: 'Account',
        accessor: (r) => r.account_id ?? 0,
        sortable: true,
        sortType: 'number',
        render: (v) => (
          <span className="text-xs text-muted-foreground">{accountLookup[Number(v)] ?? '—'}</span>
        ),
        width: '90px',
      },
      {
        key: 'symbol',
        header: 'Symbol',
        accessor: (r) => r.symbol ?? '—',
        sortable: true,
        sortType: 'string',
        render: (v) => <span className="font-mono text-sm">{String(v ?? '—')}</span>,
        width: '90px',
      },
      {
        key: 'category',
        header: 'Type',
        accessor: (r) => r.category ?? '—',
        sortable: true,
        sortType: 'string',
        render: (v) => {
          const cat = String(v ?? '—');
          const variantClass =
            cat === 'DIVIDEND'
              ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200'
              : cat === 'TRADE'
                ? 'border-primary/40 bg-primary/10'
                : 'border-border bg-muted/50';
          return (
            <Badge variant="outline" className={cn('h-5 text-[10px] font-medium', variantClass)}>
              {cat}
            </Badge>
          );
        },
        width: '100px',
      },
      {
        key: 'side',
        header: 'Side',
        accessor: (r) => r.side ?? '—',
        sortable: true,
        sortType: 'string',
        render: (v) => <span className="text-sm text-muted-foreground">{String(v ?? '—')}</span>,
        width: '70px',
      },
      {
        key: 'quantity',
        header: 'Qty',
        accessor: (r) => r.quantity ?? 0,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => <span className="text-sm">{v != null ? Number(v) : '—'}</span>,
        width: '80px',
      },
      {
        key: 'price',
        header: 'Price',
        accessor: (r) => r.price ?? 0,
        sortable: true,
        sortType: 'number',
        isNumeric: true,
        render: (v) => (
          <span className="text-sm text-muted-foreground">
            {v != null ? formatMoney(Number(v), currency) : '—'}
          </span>
        ),
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
          <span
            className={cn(
              'text-sm',
              semanticTextColorClass(Number(v ?? 0) >= 0 ? 'status.success' : 'status.danger'),
            )}
          >
            {v != null ? formatMoney(Number(v), currency) : '—'}
          </span>
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
        render: (v) => (
          <span className="text-sm text-muted-foreground">
            {v != null && Number(v) !== 0 ? formatMoney(Number(v), currency) : '—'}
          </span>
        ),
        width: '100px',
      },
    ],
    [currency, accountLookup],
  );

  return (
    <div className="p-4">
      <div className="flex flex-col gap-4">
        <PageHeader
          title="Transactions"
          subtitle="Unified activity feed (trades, dividends, fees)"
          rightContent={
            <Button
              size="sm"
              variant="outline"
              className="gap-2"
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
            >
              {syncMutation.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <RefreshCw className="size-4" aria-hidden />
              )}
              Sync
            </Button>
          }
        />

        {accountsQuery.isPending ? (
          <TableSkeleton rows={10} cols={7} />
        ) : activityQuery.error || accountsQuery.error ? (
          <p className={cn('text-sm', semanticTextColorClass('status.danger'))}>Failed to load activity</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              {DATE_RANGES.map((r) => (
                <Button
                  key={r.key}
                  size="xs"
                  variant={dateRange === r.key ? 'default' : 'outline'}
                  onClick={() => setDateRange(r.key)}
                >
                  {r.label}
                </Button>
              ))}
              <select
                className="h-8 rounded-md border border-input bg-background px-2 text-xs shadow-xs md:text-sm"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                aria-label="Filter by type"
              >
                <option value="">All types</option>
                {CATEGORIES.filter(Boolean).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <select
                className="h-8 rounded-md border border-input bg-background px-2 text-xs shadow-xs md:text-sm"
                value={side}
                onChange={(e) => setSide(e.target.value)}
                aria-label="Filter by side"
              >
                <option value="">All sides</option>
                {SIDES.filter(Boolean).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <Input
                className="h-8 w-[100px] text-xs md:text-sm"
                placeholder="Symbol"
                value={symbolSearch}
                onChange={(e) => setSymbolSearch(e.target.value)}
                aria-label="Filter by symbol"
              />
            </div>

            <Card className="gap-0 border border-border shadow-none ring-0">
              <CardContent className="py-4">
                {activityQuery.isPending ? (
                  <TableSkeleton rows={10} cols={7} />
                ) : (
                  <>
                    <div className="mb-3 flex flex-wrap gap-4 rounded-md bg-muted/50 p-3 text-sm">
                      <div className="flex gap-2">
                        <span className="text-muted-foreground">Dividends:</span>
                        <span
                          className={semanticTextColorClass(
                            summary.dividends >= 0 ? 'status.success' : 'status.danger',
                          )}
                        >
                          {formatMoney(summary.dividends, currency)}
                        </span>
                      </div>
                      <div className="flex gap-2">
                        <span className="text-muted-foreground">Fees/Commissions:</span>
                        <span
                          className={semanticTextColorClass(
                            summary.feesCommissions <= 0 ? 'status.danger' : 'status.success',
                          )}
                        >
                          {formatMoney(summary.feesCommissions, currency)}
                        </span>
                      </div>
                      <div className="flex gap-2">
                        <span className="text-muted-foreground">Interest received:</span>
                        <span
                          className={semanticTextColorClass(
                            summary.interestReceived >= 0 ? 'status.success' : 'status.danger',
                          )}
                        >
                          {formatMoney(summary.interestReceived, currency)}
                        </span>
                      </div>
                    </div>
                    <div className="mb-2 flex justify-between">
                      <Badge variant="secondary" className="h-5">
                        {hasApiTotal ? `${activity.length} of ${total}` : `${activity.length} rows (this page)`}
                      </Badge>
                    </div>
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
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
};

export default PortfolioTransactions;
