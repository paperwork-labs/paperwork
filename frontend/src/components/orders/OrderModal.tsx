import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Text,
  VStack,
  HStack,
  Input,
  Button,
  Badge,
  Collapsible,
  DialogRoot,
  DialogBackdrop,
  DialogPositioner,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogBody,
  DialogFooter,
  DialogCloseTrigger,
} from '@chakra-ui/react';
import { FiChevronDown, FiChevronRight } from 'react-icons/fi';
import api, { portfolioApi } from '../../services/api';
import { formatMoney, formatDateFriendly } from '../../utils/format';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import type { OrderSide, OrderStatus } from '../../types/orders';

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
  const maxQuantity = isSell ? sharesHeld : Infinity;

  useEffect(() => {
    if (!isOpen || !positionId || !isSell) { setTaxLots([]); return; }
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
      } catch { setTaxLots([]); }
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
      const { data } = await api.post<{ data: { order_id: number; status: string; preview: Record<string, unknown>; warnings: string[] } }>(
        '/portfolio/orders/preview',
        {
          symbol,
          side,
          order_type: orderType,
          quantity,
          limit_price: ['limit', 'stop_limit'].includes(orderType) ? limitPrice : undefined,
          stop_price: ['stop', 'stop_limit'].includes(orderType) ? stopPrice : undefined,
        },
      );
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
      const { data } = await api.post<{ data: { order_id: number; status: string; broker_order_id?: string; error?: string } }>(
        '/portfolio/orders/submit',
        { order_id: orderId },
      );
      const result = data?.data ?? data;
      if (result?.error) { setSubmitError(result.error); return; }
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
      } catch { /* ignore poll errors */ }
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

  const sideColor = isSell ? 'red' : 'green';
  const sideLabel = isSell ? 'Sell' : 'Buy';

  return (
    <DialogRoot open={isOpen} onOpenChange={(d) => { if (!d.open) onClose(); }}>
      <DialogBackdrop />
      <DialogPositioner
        display="flex"
        alignItems={{ base: 'flex-end', md: 'center' }}
        justifyContent="center"
      >
        <DialogContent
          maxW={{ base: '95vw', md: 'md' }}
          borderRadius={{ base: '16px 16px 0 0', md: 'xl' }}
          maxH={{ base: '90vh', md: 'auto' }}
          overflowY="auto"
        >
          <DialogHeader>
            <DialogTitle>
              <HStack gap={2}>
                <Badge colorPalette={sideColor} variant="solid" size="lg">{sideLabel}</Badge>
                <Text>{symbol}</Text>
              </HStack>
            </DialogTitle>
          </DialogHeader>
          <DialogBody>
            {/* Step 1: Configure */}
            {step === 1 && (
              <VStack align="stretch" gap={4}>
                <Box>
                  <Text fontSize="sm" fontWeight="semibold" mb={2}>Side</Text>
                  <HStack gap={1}>
                    {(['buy', 'sell'] as const).map((s) => (
                      <Button
                        key={s}
                        size="sm"
                        variant={side === s ? 'solid' : 'outline'}
                        colorPalette={s === 'buy' ? 'green' : 'red'}
                        onClick={() => {
                          setSide(s);
                          setQuantity(s === 'sell' ? sharesHeld : 1);
                        }}
                      >
                        {s.charAt(0).toUpperCase() + s.slice(1)}
                      </Button>
                    ))}
                  </HStack>
                </Box>
                <Box>
                  <Text fontSize="sm" fontWeight="semibold" mb={2}>Order type</Text>
                  <HStack gap={1} flexWrap="wrap">
                    {ORDER_TYPES.map((t) => (
                      <Button
                        key={t}
                        size="sm"
                        variant={orderType === t ? 'solid' : 'outline'}
                        onClick={() => setOrderType(t)}
                      >
                        {t === 'stop_limit' ? 'Stop Limit' : t.charAt(0).toUpperCase() + t.slice(1)}
                      </Button>
                    ))}
                  </HStack>
                </Box>
                <Box>
                  <Text fontSize="sm" fontWeight="semibold" mb={2}>Quantity</Text>
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
                    <HStack mt={2} gap={1} flexWrap="wrap">
                      {[0.25, 0.5, 0.75, 1].map((p) => (
                        <Button key={p} size="xs" variant="outline" onClick={() => setQuantityPct(p)}>
                          {p >= 1 ? 'All' : `${p * 100}%`}
                        </Button>
                      ))}
                    </HStack>
                  )}
                </Box>
                {isSell && taxLots.length > 0 && (
                  <Box borderWidth="1px" borderColor="border.subtle" borderRadius="md" p={2}>
                    <HStack cursor="pointer" onClick={() => setLotsExpanded((p) => !p)} gap={1}>
                      {lotsExpanded ? <FiChevronDown size={14} /> : <FiChevronRight size={14} />}
                      <Text fontSize="sm" fontWeight="semibold">Tax Lots ({taxLots.length})</Text>
                      {selectedLotIds.size > 0 && (
                        <Badge size="sm" colorPalette="blue">{selectedLotIds.size} selected</Badge>
                      )}
                    </HStack>
                    <Collapsible.Root open={lotsExpanded}>
                      <Collapsible.Content>
                        <Box maxH="200px" overflowY="auto" mt={2}>
                          <Box as="table" w="100%" fontSize="xs">
                            <Box as="thead">
                              <Box as="tr">
                                <Box as="th" w="24px" />
                                <Box as="th" textAlign="start" pb={1}>Date</Box>
                                <Box as="th" textAlign="end" pb={1}>Shares</Box>
                                <Box as="th" textAlign="end" pb={1}>Cost</Box>
                                <Box as="th" textAlign="end" pb={1}>P/L</Box>
                                <Box as="th" textAlign="center" pb={1}>Type</Box>
                              </Box>
                            </Box>
                            <Box as="tbody">
                              {taxLots.map((lot) => {
                                const checked = selectedLotIds.has(lot.id);
                                return (
                                  <Box
                                    as="tr"
                                    key={lot.id}
                                    cursor="pointer"
                                    bg={checked ? 'bg.muted' : undefined}
                                    _hover={{ bg: 'bg.subtle' }}
                                    onClick={() => toggleLot(lot.id)}
                                  >
                                    <Box as="td" py="2px" textAlign="center">
                                      <input type="checkbox" checked={checked} readOnly style={{ cursor: 'pointer' }} />
                                    </Box>
                                    <Box as="td" py="2px">
                                      {formatDateFriendly(lot.purchase_date, timezone)}
                                    </Box>
                                    <Box as="td" py="2px" textAlign="end">{lot.shares}</Box>
                                    <Box as="td" py="2px" textAlign="end">{formatMoney(lot.cost_per_share, CURRENCY)}</Box>
                                    <Box as="td" py="2px" textAlign="end" color={lot.unrealized_pnl >= 0 ? 'fg.success' : 'fg.error'}>
                                      {lot.unrealized_pnl >= 0 ? '+' : ''}
                                      {formatMoney(lot.unrealized_pnl, CURRENCY, { maximumFractionDigits: 0 })}
                                    </Box>
                                    <Box as="td" py="2px" textAlign="center">
                                      <Badge size="sm" colorPalette={lot.is_long_term ? 'green' : lot.approaching_lt ? 'yellow' : 'gray'}>
                                        {lot.is_long_term ? 'LT' : 'ST'}
                                      </Badge>
                                    </Box>
                                  </Box>
                                );
                              })}
                            </Box>
                          </Box>
                        </Box>
                        <Text fontSize="xs" color="fg.muted" mt={1}>
                          Select lots to auto-fill quantity. IBKR uses its own lot selection (FIFO/tax-optimized).
                        </Text>
                      </Collapsible.Content>
                    </Collapsible.Root>
                  </Box>
                )}
                {['limit', 'stop_limit'].includes(orderType) && (
                  <Box>
                    <Text fontSize="sm" fontWeight="semibold" mb={2}>Limit price</Text>
                    <Input type="number" step={0.01} min={0} value={limitPrice} onChange={(e) => setLimitPrice(Number(e.target.value) || 0)} />
                  </Box>
                )}
                {['stop', 'stop_limit'].includes(orderType) && (
                  <Box>
                    <Text fontSize="sm" fontWeight="semibold" mb={2}>Stop price</Text>
                    <Input type="number" step={0.01} min={0} value={stopPrice} onChange={(e) => setStopPrice(Number(e.target.value) || 0)} />
                  </Box>
                )}
                <Box borderTopWidth="1px" borderColor="border.subtle" pt={3}>
                  <Text fontSize="sm" color="fg.muted">{isSell ? 'Estimated proceeds' : 'Estimated cost'}</Text>
                  <Text fontSize="lg" fontWeight="bold">{formatMoney(estimatedValue, CURRENCY, { maximumFractionDigits: 2 })}</Text>
                  {pnl != null && (
                    <Text fontSize="sm" color={pnl >= 0 ? 'fg.success' : 'fg.error'} mt={1}>
                      P&L: {pnl >= 0 ? '+' : ''}{formatMoney(pnl, CURRENCY, { maximumFractionDigits: 2 })}
                    </Text>
                  )}
                </Box>
                {previewError && <Text fontSize="sm" color="fg.error">{previewError}</Text>}
              </VStack>
            )}

            {/* Step 2: Review */}
            {step === 2 && previewData && (
              <VStack align="stretch" gap={4}>
                {([
                  ['Symbol', symbol],
                  ['Side', sideLabel],
                  ['Type', orderType === 'stop_limit' ? 'Stop Limit' : orderType],
                  ['Quantity', `${quantity} shares`],
                ] as const).map(([label, value]) => (
                  <HStack key={label} justify="space-between">
                    <Text fontSize="sm" color="fg.muted">{label}</Text>
                    <Text fontWeight="semibold">{value}</Text>
                  </HStack>
                ))}
                {['limit', 'stop_limit'].includes(orderType) && (
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="fg.muted">Limit price</Text>
                    <Text>{formatMoney(limitPrice, CURRENCY)}</Text>
                  </HStack>
                )}
                {['stop', 'stop_limit'].includes(orderType) && (
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="fg.muted">Stop price</Text>
                    <Text>{formatMoney(stopPrice, CURRENCY)}</Text>
                  </HStack>
                )}
                {previewData.preview?.estimated_commission != null && (
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="fg.muted">Est. commission</Text>
                    <Text>{formatMoney(Number(previewData.preview.estimated_commission), CURRENCY)}</Text>
                  </HStack>
                )}
                {previewData.preview?.estimated_margin_impact != null && (
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="fg.muted">Margin impact</Text>
                    <Text>{formatMoney(Number(previewData.preview.estimated_margin_impact), CURRENCY)}</Text>
                  </HStack>
                )}
                {pnl != null && (
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="fg.muted">Est. P&L</Text>
                    <Text color={pnl >= 0 ? 'fg.success' : 'fg.error'}>
                      {pnl >= 0 ? '+' : ''}{formatMoney(pnl, CURRENCY, { maximumFractionDigits: 2 })}
                    </Text>
                  </HStack>
                )}
                {previewData.warnings?.length > 0 && (
                  <VStack align="stretch" gap={1}>
                    {previewData.warnings.map((w, i) => (
                      <Text key={i} fontSize="sm" color="fg.warning">{w}</Text>
                    ))}
                  </VStack>
                )}
                {submitError && <Text fontSize="sm" color="fg.error">{submitError}</Text>}
              </VStack>
            )}

            {/* Step 3: Status */}
            {step === 3 && orderStatus && (
              <VStack align="stretch" gap={4}>
                <HStack justify="center">
                  <Badge size="lg" colorPalette={getStatusBadgeColor(String(orderStatus.status ?? ''))} variant="solid">
                    {(orderStatus.status as string) ?? 'Unknown'}
                  </Badge>
                </HStack>
                <HStack justify="space-between">
                  <Text fontSize="sm" color="fg.muted">Order ID</Text>
                  <Text fontFamily="mono">#{orderStatus.id}</Text>
                </HStack>
                {orderStatus.broker_order_id && (
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="fg.muted">Broker ID</Text>
                    <Text fontFamily="mono" fontSize="sm">{String(orderStatus.broker_order_id)}</Text>
                  </HStack>
                )}
                {orderStatus.filled_quantity != null && (
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="fg.muted">Filled</Text>
                    <Text>{orderStatus.filled_quantity} shares</Text>
                  </HStack>
                )}
                {orderStatus.filled_avg_price != null && (
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="fg.muted">Avg fill</Text>
                    <Text>{formatMoney(Number(orderStatus.filled_avg_price), CURRENCY)}</Text>
                  </HStack>
                )}
                {orderStatus.error_message && (
                  <Text fontSize="sm" color="fg.error">{String(orderStatus.error_message)}</Text>
                )}
              </VStack>
            )}
          </DialogBody>
          <DialogFooter flexDirection={{ base: 'column', sm: 'row' }}>
            {step === 1 && (
              <>
                <Button variant="outline" onClick={onClose} w={{ base: 'full', sm: 'auto' }}>Cancel</Button>
                <Button
                  colorPalette={sideColor}
                  loading={previewLoading}
                  disabled={quantity < 1 || (isSell && quantity > sharesHeld)}
                  onClick={fetchPreview}
                  w={{ base: 'full', sm: 'auto' }}
                >
                  Preview Order
                </Button>
              </>
            )}
            {step === 2 && (
              <>
                <Button variant="outline" onClick={() => setStep(1)} w={{ base: 'full', sm: 'auto' }}>Back</Button>
                <Button colorPalette={sideColor} loading={submitLoading} onClick={submitOrder} w={{ base: 'full', sm: 'auto' }}>
                  Confirm & Submit
                </Button>
              </>
            )}
            {step === 3 && <Button onClick={onClose} w={{ base: 'full', sm: 'auto' }}>Close</Button>}
          </DialogFooter>
          <DialogCloseTrigger />
        </DialogContent>
      </DialogPositioner>
    </DialogRoot>
  );
}
