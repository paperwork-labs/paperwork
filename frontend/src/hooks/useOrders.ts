import { useState, useCallback } from 'react';
import api from '../services/api';
import type { Order, OrderPreviewRequest, OrderPreviewResponse, OrderStatus } from '../types/orders';

interface UseOrdersReturn {
  orders: Order[];
  loading: boolean;
  error: string | null;
  fetchOrders: (filters?: { status?: string; symbol?: string; limit?: number }) => Promise<void>;
  previewOrder: (req: OrderPreviewRequest) => Promise<OrderPreviewResponse>;
  submitOrder: (orderId: number) => Promise<Order>;
  cancelOrder: (orderId: number) => Promise<Order>;
  pollOrderStatus: (orderId: number) => Promise<Order>;
}

function extractData<T>(resp: { data?: { data?: T } }): T {
  return (resp?.data as { data?: T })?.data ?? resp?.data as T;
}

function extractError(e: unknown): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string };
  return err?.response?.data?.detail ?? err?.message ?? 'Unknown error';
}

export function useOrders(): UseOrdersReturn {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOrders = useCallback(async (filters?: { status?: string; symbol?: string; limit?: number }) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filters?.status) params.set('status', filters.status);
      if (filters?.symbol) params.set('symbol', filters.symbol);
      if (filters?.limit) params.set('limit', String(filters.limit));
      const resp = await api.get(`/portfolio/orders?${params}`);
      setOrders(extractData<Order[]>(resp) ?? []);
    } catch (e) {
      setError(extractError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const previewOrder = useCallback(async (req: OrderPreviewRequest): Promise<OrderPreviewResponse> => {
    const resp = await api.post('/portfolio/orders/preview', req);
    return extractData<OrderPreviewResponse>(resp);
  }, []);

  const submitOrder = useCallback(async (orderId: number): Promise<Order> => {
    const resp = await api.post('/portfolio/orders/submit', { order_id: orderId });
    return extractData<Order>(resp);
  }, []);

  const cancelOrder = useCallback(async (orderId: number): Promise<Order> => {
    const resp = await api.delete(`/portfolio/orders/${orderId}`);
    return extractData<Order>(resp);
  }, []);

  const pollOrderStatus = useCallback(async (orderId: number): Promise<Order> => {
    const resp = await api.get(`/portfolio/orders/${orderId}/status`);
    return extractData<Order>(resp);
  }, []);

  return { orders, loading, error, fetchOrders, previewOrder, submitOrder, cancelOrder, pollOrderStatus };
}

const TERMINAL_STATUSES: OrderStatus[] = ['filled', 'cancelled', 'error', 'rejected'];

export function useOrderPolling(orderId: number | null, enabled: boolean) {
  const [status, setStatus] = useState<Order | null>(null);
  const { pollOrderStatus } = useOrders();

  const startPolling = useCallback(() => {
    if (!orderId || !enabled) return () => {};

    const interval = setInterval(async () => {
      try {
        const result = await pollOrderStatus(orderId);
        setStatus(result);
        if (TERMINAL_STATUSES.includes(result.status)) {
          clearInterval(interval);
        }
      } catch { /* ignore poll errors */ }
    }, 2000);

    return () => clearInterval(interval);
  }, [orderId, enabled, pollOrderStatus]);

  return { status, startPolling, setStatus };
}
