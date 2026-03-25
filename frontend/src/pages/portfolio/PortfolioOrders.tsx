import React, { useMemo, useState, useCallback } from 'react';
import {
  Box,
  Text,
  HStack,
  Button,
  Badge,
} from '@chakra-ui/react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ChartContext, ChartSlidePanel } from '../../components/market/SymbolChartUI';
import SortableTable, { type Column } from '../../components/SortableTable';
import PageHeader from '../../components/ui/PageHeader';
import { formatMoney, formatDateTimeFriendly } from '../../utils/format';
import api from '../../services/api';
import { useUserPreferences } from '../../hooks/useUserPreferences';

import type { Order } from '../../types/orders';

type OrderRow = Order;

type StatusFilter = 'all' | 'active' | 'filled' | 'cancelled';

const ACTIVE_STATUSES = new Set(['preview', 'pending_submit', 'submitted', 'partially_filled']);

function statusColor(s: string): string {
  const l = s.toLowerCase();
  if (l === 'filled') return 'green';
  if (['submitted', 'pending_submit', 'partially_filled'].includes(l)) return 'yellow';
  if (['error', 'rejected'].includes(l)) return 'red';
  return 'gray';
}

const PortfolioOrders: React.FC = () => {
  const queryClient = useQueryClient();
  const { timezone } = useUserPreferences();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const openChart = useCallback((sym: string) => setChartSymbol(sym), []);

  const ordersQuery = useQuery<OrderRow[]>({
    queryKey: ['allOrders'],
    queryFn: async () => {
      const res = await api.get('/portfolio/orders', { params: { limit: 200 } });
      return res.data?.data ?? res.data ?? [];
    },
    staleTime: 10000,
    refetchInterval: (query) => {
      const data = query.state.data;
      const active = (data ?? []).some((o: OrderRow) => ACTIVE_STATUSES.has(o.status));
      return active ? 5000 : false;
    },
  });
  const allOrders = ordersQuery.data ?? [];

  const filtered = useMemo(() => {
    switch (statusFilter) {
      case 'active': return allOrders.filter(o => ACTIVE_STATUSES.has(o.status));
      case 'filled': return allOrders.filter(o => o.status === 'filled');
      case 'cancelled': return allOrders.filter(o => ['cancelled', 'rejected', 'error'].includes(o.status));
      default: return allOrders;
    }
  }, [allOrders, statusFilter]);

  const handleCancel = async (orderId: number) => {
    try {
      await api.delete(`/portfolio/orders/${orderId}`);
      queryClient.invalidateQueries({ queryKey: ['allOrders'] });
    } catch {
      // silently handled -- status will update on next poll
    }
  };

  const columns: Column<OrderRow>[] = useMemo(() => [
    {
      key: 'symbol',
      header: 'Symbol',
      accessor: (o) => o.symbol,
      sortable: true,
      render: (_v, o) => (
        <Text fontFamily="mono" fontWeight="semibold" cursor="pointer" _hover={{ textDecoration: 'underline', color: 'brand.500' }} onClick={(e) => { e.stopPropagation(); openChart(o.symbol); }}>
          {o.symbol}
        </Text>
      ),
      width: '90px',
    },
    {
      key: 'side',
      header: 'Side',
      accessor: (o) => o.side,
      sortable: true,
      render: (v) => (
        <Badge size="sm" colorPalette={v === 'sell' ? 'red' : 'green'} variant="subtle">
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
      render: (v) => <Text fontSize="xs" textTransform="capitalize">{v}</Text>,
      width: '75px',
    },
    {
      key: 'quantity',
      header: 'Qty',
      accessor: (o) => o.quantity,
      sortable: true,
      isNumeric: true,
      render: (v) => <Text fontSize="xs">{Number(v).toLocaleString()}</Text>,
      width: '70px',
    },
    {
      key: 'price',
      header: 'Price',
      accessor: (o) => o.limit_price ?? o.stop_price ?? null,
      sortable: true,
      isNumeric: true,
      render: (_v, o) => {
        if (o.limit_price) return <Text fontSize="xs">{formatMoney(o.limit_price, 'USD')} <Text as="span" color="fg.muted">lmt</Text></Text>;
        if (o.stop_price) return <Text fontSize="xs">{formatMoney(o.stop_price, 'USD')} <Text as="span" color="fg.muted">stp</Text></Text>;
        return <Text fontSize="xs" color="fg.muted">MKT</Text>;
      },
      width: '100px',
    },
    {
      key: 'status',
      header: 'Status',
      accessor: (o) => o.status,
      sortable: true,
      render: (v) => (
        <Badge size="sm" colorPalette={statusColor(v)} variant="subtle">
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
        <Text fontSize="xs">
          {Number(v) > 0 ? `${Number(v).toLocaleString()} / ${Number(o.quantity).toLocaleString()}` : '—'}
        </Text>
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
      render: (v) => <Text fontSize="xs">{v != null ? formatMoney(Number(v), 'USD') : '—'}</Text>,
      width: '85px',
    },
    {
      key: 'source',
      header: 'Source',
      accessor: (o) => o.source ?? 'manual',
      sortable: true,
      hiddenOnMobile: true,
      render: (v) => (
        <Badge size="sm" variant="subtle" colorPalette={v === 'strategy' ? 'purple' : v === 'rebalance' ? 'blue' : 'gray'}>
          {String(v).charAt(0).toUpperCase() + String(v).slice(1)}
        </Badge>
      ),
      width: '90px',
    },
    {
      key: 'estimated_commission',
      header: 'Comm.',
      accessor: (o) => o.estimated_commission,
      sortable: true,
      isNumeric: true,
      hiddenOnMobile: true,
      render: (v) => <Text fontSize="xs">{v != null ? formatMoney(Number(v), 'USD') : '—'}</Text>,
      width: '75px',
    },
    {
      key: 'created_at',
      header: 'Created',
      accessor: (o) => o.created_at ?? '',
      sortable: true,
      sortType: 'date',
      render: (v) => <Text fontSize="xs" color="fg.muted">{formatDateTimeFriendly(v, timezone)}</Text>,
      width: '130px',
    },
    {
      key: 'actions',
      header: '',
      accessor: () => '',
      sortable: false,
      render: (_v, o) => {
        if (ACTIVE_STATUSES.has(o.status) && o.status !== 'preview') {
          return (
            <Button size="xs" variant="outline" colorPalette="red" onClick={(e) => { e.stopPropagation(); handleCancel(o.id); }}>
              Cancel
            </Button>
          );
        }
        if (o.error_message) {
          return <Text fontSize="xs" color="fg.error" maxW="120px" truncate>{o.error_message}</Text>;
        }
        return null;
      },
      width: '80px',
    },
  ], [openChart, timezone]);

  const activeCount = allOrders.filter(o => ACTIVE_STATUSES.has(o.status)).length;

  return (
    <Box p={4}>
      <PageHeader
        title="Orders"
        subtitle="Trade order history and active order management"
      />

      <HStack gap={2} mt={4} mb={4}>
        {(['all', 'active', 'filled', 'cancelled'] as StatusFilter[]).map((f) => (
          <Button
            key={f}
            size="xs"
            variant={statusFilter === f ? 'solid' : 'outline'}
            onClick={() => setStatusFilter(f)}
          >
            {f === 'all' ? `All (${allOrders.length})` : f === 'active' ? `Active (${activeCount})` : f.charAt(0).toUpperCase() + f.slice(1)}
          </Button>
        ))}
        <Box flex="1" />
        <Button size="xs" variant="outline" onClick={() => queryClient.invalidateQueries({ queryKey: ['allOrders'] })}>
          Refresh
        </Button>
      </HStack>

      <ChartContext.Provider value={openChart}>
        <SortableTable
          data={filtered}
          columns={columns}
          defaultSortBy="created_at"
          defaultSortOrder="desc"
          size="sm"
          maxHeight="calc(100vh - 240px)"
          emptyMessage="No orders found."
        />
      </ChartContext.Provider>

      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </Box>
  );
};

export default PortfolioOrders;
