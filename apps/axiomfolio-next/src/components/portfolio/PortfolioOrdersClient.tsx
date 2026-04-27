"use client";

import React, { useMemo, useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Sparkles } from 'lucide-react';
import hotToast from 'react-hot-toast';
import { ChartContext, ChartSlidePanel } from '@/components/market/SymbolChartUI';
import SortableTable, { type Column } from '@/components/SortableTable';
import PageHeader from '@/components/ui/PageHeader';
import { formatMoney, formatDateTimeFriendly } from '@/utils/format';
import api, { handleApiError } from '@/services/api';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import { ExplanationDrawer } from '@/components/trades/ExplanationDrawer';

import type { Order } from '@/types/orders';
import { useAccountContext } from '@/context/AccountContext';

type OrderRow = Order;

type StatusFilter = 'all' | 'active' | 'filled' | 'cancelled';
type ListSourceFilter = 'all' | 'app' | 'broker';

const ACTIVE_STATUSES = new Set(['preview', 'pending_submit', 'submitted', 'partially_filled']);

function statusBadgeClass(s: string): string {
  const l = s.toLowerCase();
  if (l === 'filled') return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200';
  if (['submitted', 'pending_submit', 'partially_filled'].includes(l))
    return 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100';
  if (['error', 'rejected'].includes(l))
    return 'border-destructive/40 bg-destructive/10 text-destructive';
  return 'border-border bg-muted/50 text-muted-foreground';
}

const PortfolioOrders: React.FC = () => {
  const queryClient = useQueryClient();
  const { timezone } = useUserPreferences();
  const { selected, accounts } = useAccountContext();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [listSource, setListSource] = useState<ListSourceFilter>('all');
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [cancellingOrderId, setCancellingOrderId] = useState<number | null>(null);
  const [explainOrderId, setExplainOrderId] = useState<number | null>(null);
  const openChart = useCallback((sym: string) => setChartSymbol(sym), []);

  const resolvedBrokerAccountId = useMemo(() => {
    if (selected === 'all' || selected === 'taxable' || selected === 'ira') {
      return undefined;
    }
    const byNumber = accounts.find((a) => a.account_number === selected);
    if (byNumber) return byNumber.id;
    return accounts.find((a) => String(a.id) === selected)?.id;
  }, [selected, accounts]);

  const ordersQuery = useQuery<OrderRow[]>({
    queryKey: ['allOrders', listSource, resolvedBrokerAccountId],
    queryFn: async () => {
      const res = await api.get('/portfolio/orders', {
        params: {
          limit: 200,
          source: listSource,
          ...(resolvedBrokerAccountId != null ? { account_id: resolvedBrokerAccountId } : {}),
        },
      });
      const body = res.data;
      if (body == null || typeof body !== 'object' || !('data' in body)) {
        throw new Error('Unexpected response from /portfolio/orders');
      }
      const rows = (body as { data: OrderRow[] }).data;
      if (!Array.isArray(rows)) {
        throw new Error('Unexpected response from /portfolio/orders');
      }
      return rows;
    },
    staleTime: 10000,
    refetchInterval: (query) => {
      const data = query.state.data;
      const active = (data ?? []).some((o: OrderRow) => ACTIVE_STATUSES.has(o.status));
      return active ? 5000 : false;
    },
  });
  const allOrders = ordersQuery.data;

  const filtered = useMemo(() => {
    const base = allOrders ?? [];
    switch (statusFilter) {
      case 'active':
        return base.filter((o) => ACTIVE_STATUSES.has(o.status));
      case 'filled':
        return base.filter((o) => o.status === 'filled');
      case 'cancelled':
        return base.filter((o) => ['cancelled', 'rejected', 'error'].includes(o.status));
      default:
        return base;
    }
  }, [allOrders, statusFilter]);

  const handleCancel = useCallback(
    async (orderId: number) => {
      setCancellingOrderId(orderId);
      try {
        await api.delete(`/portfolio/orders/${orderId}`);
        queryClient.invalidateQueries({ queryKey: ['allOrders'] });
      } catch (e: unknown) {
        hotToast.error(`Could not cancel order: ${handleApiError(e)}`);
      } finally {
        setCancellingOrderId(null);
      }
    },
    [queryClient],
  );

  const columns: Column<OrderRow>[] = useMemo(
    () => [
      {
        key: 'provenance',
        header: 'From',
        accessor: (o) => o.provenance ?? 'app',
        sortable: true,
        render: (_v, o) => {
          const isApp = o.provenance !== 'broker_sync';
          return (
            <Badge
              variant="outline"
              className={cn(
                'h-5 min-w-0 text-[10px] font-medium',
                isApp
                  ? 'border-sky-500/40 bg-sky-500/10 text-sky-900 dark:text-sky-100'
                  : 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100',
              )}
            >
              {isApp ? 'Placed' : 'Broker'}
            </Badge>
          );
        },
        width: '78px',
      },
      {
        key: 'symbol',
        header: 'Symbol',
        accessor: (o) => o.symbol,
        sortable: true,
        render: (_v, o) => (
          <button
            type="button"
            className="cursor-pointer font-mono font-semibold text-primary hover:underline"
            onClick={(e) => {
              e.stopPropagation();
              openChart(o.symbol);
            }}
          >
            {o.symbol}
          </button>
        ),
        width: '90px',
      },
      {
        key: 'side',
        header: 'Side',
        accessor: (o) => o.side,
        sortable: true,
        render: (v) => (
          <Badge
            variant="outline"
            className={cn(
              'h-5 text-[10px]',
              v === 'sell'
                ? 'border-red-500/40 text-red-700 dark:text-red-300'
                : 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300',
            )}
          >
            {String(v).toUpperCase()}
          </Badge>
        ),
        width: '65px',
      },
      {
        key: 'order_type',
        header: 'Type',
        accessor: (o) => o.order_type,
        sortable: true,
        render: (v) => <span className="text-xs capitalize">{v}</span>,
        width: '75px',
      },
      {
        key: 'quantity',
        header: 'Qty',
        accessor: (o) => o.quantity,
        sortable: true,
        isNumeric: true,
        render: (v) => <span className="text-xs">{Number(v).toLocaleString()}</span>,
        width: '70px',
      },
      {
        key: 'price',
        header: 'Price',
        accessor: (o) => o.limit_price ?? o.stop_price ?? null,
        sortable: true,
        isNumeric: true,
        render: (_v, o) => {
          if (o.limit_price)
            return (
              <span className="text-xs">
                {formatMoney(o.limit_price, 'USD')}{' '}
                <span className="text-muted-foreground">lmt</span>
              </span>
            );
          if (o.stop_price)
            return (
              <span className="text-xs">
                {formatMoney(o.stop_price, 'USD')}{' '}
                <span className="text-muted-foreground">stp</span>
              </span>
            );
          return <span className="text-xs text-muted-foreground">MKT</span>;
        },
        width: '100px',
      },
      {
        key: 'status',
        header: 'Status',
        accessor: (o) => o.status,
        sortable: true,
        render: (v) => (
          <Badge variant="outline" className={cn('h-5 text-[10px] font-medium', statusBadgeClass(String(v)))}>
            {String(v).replace('_', ' ').toUpperCase()}
          </Badge>
        ),
        width: '110px',
      },
      {
        key: 'filled_quantity',
        header: 'Filled',
        accessor: (o) => o.filled_quantity,
        sortable: true,
        isNumeric: true,
        render: (v, o) => (
          <span className="text-xs">
            {Number(v) > 0 ? `${Number(v).toLocaleString()} / ${Number(o.quantity).toLocaleString()}` : '—'}
          </span>
        ),
        width: '90px',
      },
      {
        key: 'filled_avg_price',
        header: 'Avg Fill',
        accessor: (o) => o.filled_avg_price,
        sortable: true,
        isNumeric: true,
        hiddenOnMobile: true,
        render: (v) => <span className="text-xs">{v != null ? formatMoney(Number(v), 'USD') : '—'}</span>,
        width: '85px',
      },
      {
        key: 'source',
        header: 'Source',
        accessor: (o) => o.source ?? 'manual',
        sortable: true,
        hiddenOnMobile: true,
        render: (v) => {
          const src = String(v);
          const cls =
            src === 'strategy'
              ? 'border-violet-500/40 bg-violet-500/10 text-violet-800 dark:text-violet-200'
              : src === 'rebalance'
                ? 'border-primary/40 bg-primary/10'
                : 'border-border bg-muted/50';
          return (
            <Badge variant="outline" className={cn('h-5 text-[10px]', cls)}>
              {src.charAt(0).toUpperCase() + src.slice(1)}
            </Badge>
          );
        },
        width: '90px',
      },
      {
        key: 'estimated_commission',
        header: 'Comm.',
        accessor: (o) => o.estimated_commission,
        sortable: true,
        isNumeric: true,
        hiddenOnMobile: true,
        render: (v) => <span className="text-xs">{v != null ? formatMoney(Number(v), 'USD') : '—'}</span>,
        width: '75px',
      },
      {
        key: 'created_at',
        header: 'Created',
        accessor: (o) => o.created_at ?? '',
        sortable: true,
        sortType: 'date',
        render: (v) => (
          <span className="text-xs text-muted-foreground">{formatDateTimeFriendly(v, timezone)}</span>
        ),
        width: '130px',
      },
      {
        key: 'actions',
        header: '',
        accessor: () => '',
        sortable: false,
        render: (_v, o) => {
          if (o.provenance === 'broker_sync' || o.id < 0) {
            return null;
          }
          if (ACTIVE_STATUSES.has(o.status) && o.status !== 'preview') {
            const isCancelling = cancellingOrderId === o.id;
            return (
              <Button
                type="button"
                size="xs"
                variant="outline"
                className="h-7 border-destructive/40 text-destructive hover:bg-destructive/10"
                disabled={isCancelling}
                aria-busy={isCancelling}
                onClick={(e) => {
                  e.stopPropagation();
                  void handleCancel(o.id);
                }}
              >
                {isCancelling ? (
                  <>
                    <Loader2 className="size-3 shrink-0 animate-spin" aria-hidden />
                    Cancel
                  </>
                ) : (
                  'Cancel'
                )}
              </Button>
            );
          }
          if (o.status === 'filled' || o.status === 'partially_filled') {
            return (
              <Button
                type="button"
                size="xs"
                variant="ghost"
                className="h-7 text-muted-foreground hover:text-foreground"
                onClick={(e) => {
                  e.stopPropagation();
                  setExplainOrderId(o.id);
                }}
                aria-label="Explain why this trade was placed"
                title="Explain why this trade was placed"
              >
                <Sparkles className="size-3 shrink-0" aria-hidden />
                <span className="ml-1 text-[11px]">Why?</span>
              </Button>
            );
          }
          if (o.error_message) {
            return (
              <span
                className={cn('max-w-[120px] truncate text-xs', semanticTextColorClass('status.danger'))}
                title={o.error_message}
              >
                {o.error_message}
              </span>
            );
          }
          return null;
        },
        width: '80px',
      },
    ],
    [openChart, timezone, handleCancel, cancellingOrderId],
  );

  const listLength = (allOrders ?? []).length;
  const activeCount = (allOrders ?? []).filter((o) => ACTIVE_STATUSES.has(o.status)).length;

  if (ordersQuery.isPending) {
    return (
      <div className="p-4">
        <PageHeader title="Orders" subtitle="Trade order history and active order management" />
        <p className="mt-1 text-xs text-muted-foreground">Sorted by most recent activity</p>
        <div
          className="mt-8 flex min-h-[200px] items-center justify-center text-sm text-muted-foreground"
          data-testid="orders-loading"
        >
          Loading…
        </div>
      </div>
    );
  }

  if (ordersQuery.isError) {
    return (
      <div className="p-4">
        <PageHeader title="Orders" subtitle="Trade order history and active order management" />
        <p className="mt-1 text-xs text-muted-foreground">Sorted by most recent activity</p>
        <div className="mt-6 rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          Could not load orders.{' '}
          <Button type="button" size="xs" variant="outline" onClick={() => void ordersQuery.refetch()}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <PageHeader title="Orders" subtitle="Trade order history and active order management" />
      <p className="mt-1 text-xs text-muted-foreground">Sorted by most recent activity</p>

      <div className="mb-4 mt-4 flex flex-wrap items-center gap-2">
        {(
          [
            { key: 'all', label: 'All' },
            { key: 'app', label: 'Placed' },
            { key: 'broker', label: 'Broker' },
          ] as const
        ).map(({ key, label }) => (
          <Button
            key={key}
            size="xs"
            variant={listSource === key ? 'default' : 'outline'}
            onClick={() => setListSource(key)}
            aria-pressed={listSource === key}
          >
            {label}
          </Button>
        ))}
        <span className="text-muted-foreground" aria-hidden>
          |
        </span>
        {(['all', 'active', 'filled', 'cancelled'] as StatusFilter[]).map((f) => (
          <Button
            key={f}
            size="xs"
            variant={statusFilter === f ? 'default' : 'outline'}
            onClick={() => setStatusFilter(f)}
          >
            {f === 'all'
              ? `All rows (${listLength})`
              : f === 'active'
                ? `Active (${activeCount})`
                : f.charAt(0).toUpperCase() + f.slice(1)}
          </Button>
        ))}
        <div className="min-w-2 flex-1" />
        <Button
          size="xs"
          variant="outline"
          onClick={() => queryClient.invalidateQueries({ queryKey: ['allOrders'] })}
        >
          Refresh
        </Button>
      </div>

      <ChartContext.Provider value={openChart}>
        <SortableTable
          data={filtered}
          columns={columns}
          defaultSortBy="created_at"
          defaultSortOrder="desc"
          size="sm"
          maxHeight="calc(100vh - 240px)"
          emptyMessage="No orders yet."
        />
      </ChartContext.Provider>

      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />

      <ExplanationDrawer
        orderId={explainOrderId}
        open={explainOrderId != null}
        onOpenChange={(open) => {
          if (!open) setExplainOrderId(null);
        }}
      />
    </div>
  );
};

export default PortfolioOrders;
