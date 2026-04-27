import React, { useEffect, useState, useCallback } from 'react';
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import api, { portfolioApi } from '../../services/api';
import { formatMoney, formatDateFriendly } from '../../utils/format';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import type { OrderSide } from '../../types/orders';

const ORDER_TYPES = ['market', 'limit', 'stop', 'stop_limit'] as const;
type OrderTypeOption = (typeof ORDER_TYPES)[number];

const CURRENCY = 'USD';

interface TaxLot {
  id: number;
  shares: number;
  purchase_date: string | null;
  cost_per_share: number;
  cost_basis?: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  is_long_term: boolean;
  days_held: number;
  approaching_lt: boolean;
}

export interface OrderModalProps {
  isOpen: boolean;
  onClose: () => void;
  symbol: string;
  currentPrice: number;
  side?: OrderSide;
  sharesHeld?: number;
  averageCost?: number;
  positionId?: number;
  onOrderPlaced?: () => void;
}

interface OrderStatusResult {
  id?: number;
  status?: string;
  broker_order_id?: string;
  filled_quantity?: number;
  filled_avg_price?: number;
  error_message?: string;
}

function getStatusBadgeColor(status: string): 'green' | 'yellow' | 'red' | 'gray' {
  const s = (status || '').toLowerCase();
  if (s === 'filled') return 'green';
  if (['submitted', 'pending_submit', 'partially_filled'].includes(s)) return 'yellow';
  if (['error', 'rejected'].includes(s)) return 'red';
  return 'gray';
}

function statusBadgeClass(palette: ReturnType<typeof getStatusBadgeColor>): string {
  switch (palette) {
    case 'green':
      return 'border-transparent bg-emerald-600 text-white hover:bg-emerald-600/90';
    case 'yellow':
      return 'border-amber-500/40 bg-amber-500/15 text-amber-800 dark:text-amber-200';
    case 'red':
      return 'border-transparent bg-destructive text-destructive-foreground';
    default:
      return 'bg-secondary text-secondary-foreground';
  }
}

function extractError(e: unknown): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string };
  return err?.response?.data?.detail ?? err?.message ?? 'Order failed';
}

export default function OrderModal({
  isOpen,
  onClose,
  symbol,
  currentPrice,
  side: initialSide = 'buy',
  sharesHeld = 0,
  averageCost,
  positionId,
  onOrderPlaced,
}: OrderModalProps) {
  const { timezone } = useUserPreferences();
  const [step, setStep] = useState(1);
  const [side, setSide] = useState<OrderSide>(initialSide);
  const [orderType, setOrderType] = useState<OrderTypeOption>('market');
  const [quantity, setQuantity] = useState(initialSide === 'sell' ? sharesHeld : 1);
  const [limitPrice, setLimitPrice] = useState(currentPrice);
  const [stopPrice, setStopPrice] = useState(currentPrice);

  const [previewLoading, setPreviewLoading] = useState(false);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [orderId, setOrderId] = useState<number | null>(null);
  const [previewData, setPreviewData] = useState<{
    order_id: number;
    status: string;
    preview: Record<string, unknown>;
    warnings: string[];
  } | null>(null);
  const [orderStatus, setOrderStatus] = useState<OrderStatusResult | null>(null);

  const [taxLots, setTaxLots] = useState<TaxLot[]>([]);
  const [lotsExpanded, setLotsExpanded] = useState(false);
  const [selectedLotIds, setSelectedLotIds] = useState<Set<number>>(new Set());

  const isSell = side === 'sell';

  useEffect(() => {
    if (!isOpen || !positionId || !isSell) {
      setTaxLots([]);
      return;
    }
    (async () => {
      try {
        const resp = await portfolioApi.getHoldingTaxLots(positionId);
        const raw = resp as Record<string, unknown> | undefined;
        const data = (raw?.data as Record<string, unknown>)?.data ?? raw?.data ?? raw;
        const rawLots = (data as Record<string, unknown>)?.tax_lots ?? [];
        const lots = (Array.isArray(rawLots) ? rawLots : []).map((l: Record<string, unknown>) => ({
          ...(l as unknown as TaxLot),
          approaching_lt: !(l as unknown as TaxLot).is_long_term && ((l as unknown as TaxLot).days_held ?? 0) >= 300,
        }));
        setTaxLots(lots);
      } catch {
        setTaxLots([]);
      }
    })();
  }, [isOpen, positionId, isSell]);

  const toggleLot = (lotId: number) => {
    setSelectedLotIds((prev) => {
      const next = new Set(prev);
      if (next.has(lotId)) next.delete(lotId);
      else next.add(lotId);
      const totalSelected = taxLots
        .filter((l) => next.has(l.id))
        .reduce((sum, l) => sum + l.shares, 0);
      if (next.size > 0) setQuantity(totalSelected);
      return next;
    });
  };

  const setQuantityPct = (pct: number) => {
    setSelectedLotIds(new Set());
    if (!isSell) return;
    if (pct >= 1) setQuantity(sharesHeld);
    else setQuantity(Math.floor(sharesHeld * pct));
  };

  const effectivePrice =
    orderType === 'limit' || orderType === 'stop_limit'
      ? limitPrice
      : orderType === 'stop'
        ? (stopPrice ?? currentPrice)
        : currentPrice;
  const estimatedValue = quantity * effectivePrice;
  const pnl = isSell && averageCost != null ? quantity * (effectivePrice - averageCost) : null;

  const fetchPreview = useCallback(async () => {
    setPreviewError(null);
    setPreviewLoading(true);
    try {
      const { data } = await api.post<{
        data: { order_id: number; status: string; preview: Record<string, unknown>; warnings: string[] };
      }>('/portfolio/orders/preview', {
        symbol,
        side,
        order_type: orderType,
        quantity,
        limit_price: ['limit', 'stop_limit'].includes(orderType) ? limitPrice : undefined,
        stop_price: ['stop', 'stop_limit'].includes(orderType) ? stopPrice : undefined,
      });
      const result = data?.data ?? data;
      setOrderId(result.order_id);
      setPreviewData(result);
      setStep(2);
    } catch (e) {
      setPreviewError(extractError(e));
    } finally {
      setPreviewLoading(false);
    }
  }, [symbol, side, orderType, quantity, limitPrice, stopPrice]);

  const submitOrder = useCallback(async () => {
    if (!orderId) return;
    setSubmitError(null);
    setSubmitLoading(true);
    try {
      const { data } = await api.post<{
        data: { order_id: number; status: string; broker_order_id?: string; error?: string };
      }>('/portfolio/orders/submit', { order_id: orderId });
      const result = data?.data ?? data;
      if (result?.error) {
        setSubmitError(result.error);
        return;
      }
      setOrderStatus({
        id: result.order_id,
        status: result.status,
        broker_order_id: result.broker_order_id,
      });
      setStep(3);
      onOrderPlaced?.();
    } catch (e) {
      setSubmitError(extractError(e));
    } finally {
      setSubmitLoading(false);
    }
  }, [orderId, onOrderPlaced]);

  useEffect(() => {
    if (step !== 3 || !orderId) return;
    const interval = setInterval(async () => {
      try {
        const { data } = await api.get<{ data: Record<string, unknown> }>(`/portfolio/orders/${orderId}/status`);
        const result = data?.data ?? data;
        if (result?.error) return;
        setOrderStatus(result as OrderStatusResult);
        const s = String(result?.status ?? '').toLowerCase();
        if (['filled', 'cancelled', 'error', 'rejected'].includes(s)) clearInterval(interval);
      } catch {
        /* ignore poll errors */
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [step, orderId]);

  useEffect(() => {
    if (!isOpen) {
      setStep(1);
      setSide(initialSide);
      setOrderType('market');
      setQuantity(initialSide === 'sell' ? sharesHeld : 1);
      setLimitPrice(currentPrice);
      setStopPrice(currentPrice);
      setOrderId(null);
      setPreviewData(null);
      setOrderStatus(null);
      setPreviewError(null);
      setSubmitError(null);
      setSelectedLotIds(new Set());
      setLotsExpanded(false);
    }
  }, [isOpen, sharesHeld, currentPrice, initialSide]);

  const sideLabel = isSell ? 'Sell' : 'Buy';

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        showCloseButton
        className="flex max-h-[min(90vh,calc(100vh-2rem))] max-w-[95vw] flex-col gap-0 overflow-hidden p-0 max-md:fixed max-md:bottom-0 max-md:left-1/2 max-md:top-auto max-md:max-h-[90vh] max-md:w-[95vw] max-md:-translate-x-1/2 max-md:translate-y-0 max-md:rounded-b-none max-md:rounded-t-xl sm:max-w-md"
      >
        <DialogHeader className="shrink-0 border-b border-border px-6 pt-6 pb-4">
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <Badge
              className={cn(
                'text-xs',
                isSell
                  ? 'border-transparent bg-destructive text-destructive-foreground'
                  : 'border-transparent bg-primary text-primary-foreground'
              )}
            >
              {sideLabel}
            </Badge>
            <span>{symbol}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
          {step === 1 && (
            <div className="flex flex-col gap-4">
              <div>
                <p className="mb-2 text-sm font-semibold">Side</p>
                <div className="flex flex-wrap gap-1">
                  {(['buy', 'sell'] as const).map((s) => (
                    <Button
                      key={s}
                      type="button"
                      size="sm"
                      variant={side === s ? 'default' : 'outline'}
                      className={cn(
                        side === s &&
                          (s === 'buy'
                            ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                            : 'border-destructive/50 bg-destructive text-destructive-foreground hover:bg-destructive/90')
                      )}
                      onClick={() => {
                        setSide(s);
                        setQuantity(s === 'sell' ? sharesHeld : 1);
                      }}
                    >
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </Button>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-2 text-sm font-semibold">Order type</p>
                <div className="flex flex-wrap gap-1">
                  {ORDER_TYPES.map((t) => (
                    <Button
                      key={t}
                      type="button"
                      size="sm"
                      variant={orderType === t ? 'default' : 'outline'}
                      onClick={() => setOrderType(t)}
                    >
                      {t === 'stop_limit' ? 'Stop Limit' : t.charAt(0).toUpperCase() + t.slice(1)}
                    </Button>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-2 text-sm font-semibold">Quantity</p>
                <Input
                  type="number"
                  min={1}
                  max={isSell ? sharesHeld : undefined}
                  value={quantity}
                  onChange={(e) => {
                    const val = Number(e.target.value) || 0;
                    setQuantity(isSell ? Math.min(sharesHeld, Math.max(0, val)) : Math.max(0, val));
                  }}
                />
                {isSell && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {[0.25, 0.5, 0.75, 1].map((p) => (
                      <Button key={p} type="button" size="xs" variant="outline" onClick={() => setQuantityPct(p)}>
                        {p >= 1 ? 'All' : `${p * 100}%`}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
              {isSell && taxLots.length > 0 && (
                <div className="rounded-md border border-border p-2">
                  <button
                    type="button"
                    className="flex w-full cursor-pointer items-center gap-1 text-left"
                    aria-expanded={lotsExpanded}
                    aria-controls="order-modal-tax-lots"
                    onClick={() => setLotsExpanded((p) => !p)}
                  >
                    {lotsExpanded ? <ChevronDown className="size-3.5 shrink-0" /> : <ChevronRight className="size-3.5 shrink-0" />}
                    <span className="text-sm font-semibold">Tax Lots ({taxLots.length})</span>
                    {selectedLotIds.size > 0 && (
                      <Badge variant="secondary" className="ml-1 text-[10px]">
                        {selectedLotIds.size} selected
                      </Badge>
                    )}
                  </button>
                  {lotsExpanded && (
                    <div id="order-modal-tax-lots" className="mt-2">
                      <div className="max-h-[200px] overflow-y-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-border text-left">
                              <th className="w-6 pb-1" scope="col" />
                              <th className="pb-1" scope="col">
                                Date
                              </th>
                              <th className="pb-1 text-right" scope="col">
                                Shares
                              </th>
                              <th className="pb-1 text-right" scope="col">
                                Cost
                              </th>
                              <th className="pb-1 text-right" scope="col">
                                P/L
                              </th>
                              <th className="pb-1 text-center" scope="col">
                                Type
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {taxLots.map((lot) => {
                              const checked = selectedLotIds.has(lot.id);
                              return (
                                <tr
                                  key={lot.id}
                                  className={cn(
                                    'cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/60',
                                    checked && 'bg-muted/40'
                                  )}
                                  onClick={() => toggleLot(lot.id)}
                                >
                                  <td className="py-0.5 text-center" onClick={(e) => e.stopPropagation()}>
                                    <Checkbox
                                      checked={checked}
                                      onCheckedChange={() => toggleLot(lot.id)}
                                      aria-label={`Select tax lot ${lot.id}`}
                                    />
                                  </td>
                                  <td className="py-0.5">{formatDateFriendly(lot.purchase_date, timezone)}</td>
                                  <td className="py-0.5 text-right">{lot.shares}</td>
                                  <td className="py-0.5 text-right">{formatMoney(lot.cost_per_share, CURRENCY)}</td>
                                  <td
                                    className={cn(
                                      'py-0.5 text-right',
                                      lot.unrealized_pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'
                                    )}
                                  >
                                    {lot.unrealized_pnl >= 0 ? '+' : ''}
                                    {formatMoney(lot.unrealized_pnl, CURRENCY, { maximumFractionDigits: 0 })}
                                  </td>
                                  <td className="py-0.5 text-center">
                                    <Badge
                                      variant="secondary"
                                      className={cn(
                                        'text-[10px]',
                                        lot.is_long_term && 'border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300',
                                        !lot.is_long_term &&
                                          lot.approaching_lt &&
                                          'border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200'
                                      )}
                                    >
                                      {lot.is_long_term ? 'LT' : 'ST'}
                                    </Badge>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Select lots to auto-fill quantity. IBKR uses its own lot selection (FIFO/tax-optimized).
                      </p>
                    </div>
                  )}
                </div>
              )}
              {['limit', 'stop_limit'].includes(orderType) && (
                <div>
                  <p className="mb-2 text-sm font-semibold">Limit price</p>
                  <Input
                    type="number"
                    step={0.01}
                    min={0}
                    value={limitPrice}
                    onChange={(e) => setLimitPrice(Number(e.target.value) || 0)}
                  />
                </div>
              )}
              {['stop', 'stop_limit'].includes(orderType) && (
                <div>
                  <p className="mb-2 text-sm font-semibold">Stop price</p>
                  <Input
                    type="number"
                    step={0.01}
                    min={0}
                    value={stopPrice}
                    onChange={(e) => setStopPrice(Number(e.target.value) || 0)}
                  />
                </div>
              )}
              <div className="border-t border-border pt-3">
                <p className="text-sm text-muted-foreground">{isSell ? 'Estimated proceeds' : 'Estimated cost'}</p>
                <p className="text-lg font-bold">{formatMoney(estimatedValue, CURRENCY, { maximumFractionDigits: 2 })}</p>
                {pnl != null && (
                  <p
                    className={cn(
                      'mt-1 text-sm',
                      pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'
                    )}
                  >
                    P&L: {pnl >= 0 ? '+' : ''}
                    {formatMoney(pnl, CURRENCY, { maximumFractionDigits: 2 })}
                  </p>
                )}
              </div>
              {previewError && <p className="text-sm text-destructive">{previewError}</p>}
            </div>
          )}

          {step === 2 && previewData && (
            <div className="flex flex-col gap-4">
              {(
                [
                  ['Symbol', symbol],
                  ['Side', sideLabel],
                  ['Type', orderType === 'stop_limit' ? 'Stop Limit' : orderType],
                  ['Quantity', `${quantity} shares`],
                ] as const
              ).map(([label, value]) => (
                <div key={label} className="flex justify-between gap-2">
                  <span className="text-sm text-muted-foreground">{label}</span>
                  <span className="font-semibold">{value}</span>
                </div>
              ))}
              {['limit', 'stop_limit'].includes(orderType) && (
                <div className="flex justify-between gap-2">
                  <span className="text-sm text-muted-foreground">Limit price</span>
                  <span>{formatMoney(limitPrice, CURRENCY)}</span>
                </div>
              )}
              {['stop', 'stop_limit'].includes(orderType) && (
                <div className="flex justify-between gap-2">
                  <span className="text-sm text-muted-foreground">Stop price</span>
                  <span>{formatMoney(stopPrice, CURRENCY)}</span>
                </div>
              )}
              {previewData.preview?.estimated_commission != null && (
                <div className="flex justify-between gap-2">
                  <span className="text-sm text-muted-foreground">Est. commission</span>
                  <span>{formatMoney(Number(previewData.preview.estimated_commission), CURRENCY)}</span>
                </div>
              )}
              {previewData.preview?.estimated_margin_impact != null && (
                <div className="flex justify-between gap-2">
                  <span className="text-sm text-muted-foreground">Margin impact</span>
                  <span>{formatMoney(Number(previewData.preview.estimated_margin_impact), CURRENCY)}</span>
                </div>
              )}
              {pnl != null && (
                <div className="flex justify-between gap-2">
                  <span className="text-sm text-muted-foreground">Est. P&L</span>
                  <span
                    className={cn(
                      pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'
                    )}
                  >
                    {pnl >= 0 ? '+' : ''}
                    {formatMoney(pnl, CURRENCY, { maximumFractionDigits: 2 })}
                  </span>
                </div>
              )}
              {previewData.warnings?.length > 0 && (
                <div className="flex flex-col gap-1">
                  {previewData.warnings.map((w, i) => (
                    <p key={i} className="text-sm text-amber-700 dark:text-amber-300">
                      {w}
                    </p>
                  ))}
                </div>
              )}
              {submitError && <p className="text-sm text-destructive">{submitError}</p>}
            </div>
          )}

          {step === 3 && orderStatus && (
            <div className="flex flex-col gap-4">
              <div className="flex justify-center">
                <Badge
                  className={cn('text-sm', statusBadgeClass(getStatusBadgeColor(String(orderStatus.status ?? ''))))}
                >
                  {String(orderStatus.status ?? 'Unknown')}
                </Badge>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-sm text-muted-foreground">Order ID</span>
                <span className="font-mono">#{orderStatus.id}</span>
              </div>
              {orderStatus.broker_order_id && (
                <div className="flex justify-between gap-2">
                  <span className="text-sm text-muted-foreground">Broker ID</span>
                  <span className="font-mono text-sm">{String(orderStatus.broker_order_id)}</span>
                </div>
              )}
              {orderStatus.filled_quantity != null && (
                <div className="flex justify-between gap-2">
                  <span className="text-sm text-muted-foreground">Filled</span>
                  <span>{orderStatus.filled_quantity} shares</span>
                </div>
              )}
              {orderStatus.filled_avg_price != null && (
                <div className="flex justify-between gap-2">
                  <span className="text-sm text-muted-foreground">Avg fill</span>
                  <span>{formatMoney(Number(orderStatus.filled_avg_price), CURRENCY)}</span>
                </div>
              )}
              {orderStatus.error_message && (
                <p className="text-sm text-destructive">{String(orderStatus.error_message)}</p>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="shrink-0 border-t border-border px-6 py-4">
          {step === 1 && (
            <>
              <Button type="button" variant="outline" className="w-full sm:w-auto" onClick={onClose}>
                Cancel
              </Button>
              <Button
                type="button"
                className={cn('w-full sm:w-auto', isSell && 'bg-destructive text-destructive-foreground hover:bg-destructive/90')}
                disabled={quantity < 1 || (isSell && quantity > sharesHeld) || previewLoading}
                onClick={() => void fetchPreview()}
              >
                {previewLoading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                Preview Order
              </Button>
            </>
          )}
          {step === 2 && (
            <>
              <Button type="button" variant="outline" className="w-full sm:w-auto" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button
                type="button"
                className={cn('w-full sm:w-auto', isSell && 'bg-destructive text-destructive-foreground hover:bg-destructive/90')}
                disabled={submitLoading}
                onClick={() => void submitOrder()}
              >
                {submitLoading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                Confirm & Submit
              </Button>
            </>
          )}
          {step === 3 && (
            <Button type="button" className="w-full sm:w-auto" onClick={onClose}>
              Close
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
