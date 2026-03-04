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
import { formatMoney } from '../../utils/format';

const ORDER_TYPES = ['market', 'limit', 'stop'] as const;
type OrderType = (typeof ORDER_TYPES)[number];

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

interface SellOrderModalProps {
  isOpen: boolean;
  onClose: () => void;
  symbol: string;
  currentPrice: number;
  sharesHeld: number;
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
  if (s === 'submitted' || s === 'pending_submit' || s === 'partially_filled') return 'yellow';
  if (s === 'error' || s === 'rejected') return 'red';
  return 'gray';
}

export default function SellOrderModal({
  isOpen,
  onClose,
  symbol,
  currentPrice,
  sharesHeld,
  averageCost,
  positionId,
  onOrderPlaced,
}: SellOrderModalProps) {
  const [step, setStep] = useState(1);
  const [orderType, setOrderType] = useState<OrderType>('market');
  const [quantity, setQuantity] = useState(sharesHeld);
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

  useEffect(() => {
    if (!isOpen || !positionId) { setTaxLots([]); return; }
    (async () => {
      try {
        const resp = await portfolioApi.getHoldingTaxLots(positionId);
        const raw = resp as Record<string, any> | undefined;
        const data = raw?.data?.data ?? raw?.data ?? raw;
        const rawLots = data?.tax_lots ?? [];
        const lots = (Array.isArray(rawLots) ? rawLots : []).map((l: any) => ({
          ...l,
          approaching_lt: !l.is_long_term && (l.days_held ?? 0) >= 300,
        }));
        setTaxLots(lots);
      } catch { setTaxLots([]); }
    })();
  }, [isOpen, positionId]);

  const toggleLot = (lotId: number, lotShares: number) => {
    setSelectedLotIds((prev) => {
      const next = new Set(prev);
      if (next.has(lotId)) { next.delete(lotId); } else { next.add(lotId); }
      const totalSelected = taxLots
        .filter((l) => next.has(l.id))
        .reduce((sum, l) => sum + l.shares, 0);
      if (next.size > 0) setQuantity(totalSelected);
      return next;
    });
  };

  const setQuantityPct = (pct: number) => {
    setSelectedLotIds(new Set());
    if (pct >= 1) setQuantity(sharesHeld);
    else setQuantity(Math.floor(sharesHeld * pct));
  };

  const effectivePrice = orderType === 'limit' ? limitPrice : orderType === 'stop' ? (stopPrice ?? currentPrice) : currentPrice;
  const estimatedProceeds = quantity * effectivePrice;
  const pnl = averageCost != null ? quantity * (effectivePrice - averageCost) : null;

  const fetchPreview = useCallback(async () => {
    setPreviewError(null);
    setPreviewLoading(true);
    try {
      const { data } = await api.post<{ data: { order_id: number; status: string; preview: Record<string, unknown>; warnings: string[] } }>(
        '/portfolio/orders/preview',
        {
          symbol,
          side: 'sell',
          order_type: orderType,
          quantity,
          limit_price: orderType === 'limit' ? limitPrice : undefined,
          stop_price: orderType === 'stop' ? stopPrice : undefined,
        }
      );
      const result = data?.data ?? data;
      setOrderId(result.order_id);
      setPreviewData(result);
      setStep(2);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (e as { message?: string })?.message
        ?? 'Preview failed';
      setPreviewError(String(msg));
    } finally {
      setPreviewLoading(false);
    }
  }, [symbol, orderType, quantity, limitPrice, stopPrice]);

  const submitOrder = useCallback(async () => {
    if (!orderId) return;
    setSubmitError(null);
    setSubmitLoading(true);
    try {
      const { data } = await api.post<{ data: { order_id: number; status: string; broker_order_id?: string; error?: string } }>(
        '/portfolio/orders/submit',
        { order_id: orderId }
      );
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
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (e as { message?: string })?.message
        ?? 'Submit failed';
      setSubmitError(String(msg));
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
        if (['filled', 'cancelled', 'error', 'rejected'].includes(s)) {
          clearInterval(interval);
        }
      } catch {
        /* ignore poll errors */
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [step, orderId]);

  useEffect(() => {
    if (!isOpen) {
      setStep(1);
      setOrderType('market');
      setQuantity(sharesHeld);
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
  }, [isOpen, sharesHeld, currentPrice]);

  const handleClose = () => {
    onClose();
  };

  return (
    <DialogRoot open={isOpen} onOpenChange={(d) => { if (!d.open) handleClose(); }}>
      <DialogBackdrop />
      <DialogPositioner>
        <DialogContent maxW="md">
          <DialogHeader>
            <DialogTitle>Sell {symbol}</DialogTitle>
          </DialogHeader>
          <DialogBody>
            {step === 1 && (
              <VStack align="stretch" gap={4}>
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
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </Button>
                    ))}
                  </HStack>
                </Box>
                <Box>
                  <Text fontSize="sm" fontWeight="semibold" mb={2}>Quantity</Text>
                  <Input
                    type="number"
                    min={1}
                    max={sharesHeld}
                    value={quantity}
                    onChange={(e) => setQuantity(Math.max(0, Math.min(sharesHeld, Number(e.target.value) || 0)))}
                  />
                  <HStack mt={2} gap={1} flexWrap="wrap">
                    {[0.25, 0.5, 0.75, 1].map((p) => (
                      <Button key={p} size="xs" variant="outline" onClick={() => setQuantityPct(p)}>
                        {p >= 1 ? 'All' : `${p * 100}%`}
                      </Button>
                    ))}
                  </HStack>
                </Box>
                {taxLots.length > 0 && (
                  <Box borderWidth="1px" borderColor="border.subtle" borderRadius="md" p={2}>
                    <HStack
                      cursor="pointer"
                      onClick={() => setLotsExpanded((p) => !p)}
                      gap={1}
                    >
                      {lotsExpanded ? <FiChevronDown size={14} /> : <FiChevronRight size={14} />}
                      <Text fontSize="sm" fontWeight="semibold">
                        Tax Lots ({taxLots.length})
                      </Text>
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
                                    bg={checked ? 'blue.950' : undefined}
                                    _hover={{ bg: 'bg.subtle' }}
                                    onClick={() => toggleLot(lot.id, lot.shares)}
                                  >
                                    <Box as="td" py="2px" textAlign="center">
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        readOnly
                                        style={{ cursor: 'pointer' }}
                                      />
                                    </Box>
                                    <Box as="td" py="2px">
                                      {lot.purchase_date
                                        ? new Date(lot.purchase_date).toLocaleDateString()
                                        : '—'}
                                    </Box>
                                    <Box as="td" py="2px" textAlign="end">{lot.shares}</Box>
                                    <Box as="td" py="2px" textAlign="end">
                                      {formatMoney(lot.cost_per_share, CURRENCY)}
                                    </Box>
                                    <Box
                                      as="td"
                                      py="2px"
                                      textAlign="end"
                                      color={lot.unrealized_pnl >= 0 ? 'fg.success' : 'fg.error'}
                                    >
                                      {lot.unrealized_pnl >= 0 ? '+' : ''}
                                      {formatMoney(lot.unrealized_pnl, CURRENCY, { maximumFractionDigits: 0 })}
                                    </Box>
                                    <Box as="td" py="2px" textAlign="center">
                                      <Badge
                                        size="sm"
                                        colorPalette={lot.is_long_term ? 'green' : lot.approaching_lt ? 'yellow' : 'gray'}
                                      >
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
                {orderType === 'limit' && (
                  <Box>
                    <Text fontSize="sm" fontWeight="semibold" mb={2}>Limit price</Text>
                    <Input
                      type="number"
                      step={0.01}
                      min={0}
                      value={limitPrice}
                      onChange={(e) => setLimitPrice(Number(e.target.value) || 0)}
                    />
                  </Box>
                )}
                {orderType === 'stop' && (
                  <Box>
                    <Text fontSize="sm" fontWeight="semibold" mb={2}>Stop price</Text>
                    <Input
                      type="number"
                      step={0.01}
                      min={0}
                      value={stopPrice}
                      onChange={(e) => setStopPrice(Number(e.target.value) || 0)}
                    />
                  </Box>
                )}
                <Box borderTopWidth="1px" borderColor="border.subtle" pt={3}>
                  <Text fontSize="sm" color="fg.muted">Estimated proceeds</Text>
                  <Text fontSize="lg" fontWeight="bold">{formatMoney(estimatedProceeds, CURRENCY, { maximumFractionDigits: 2 })}</Text>
                  {pnl != null && (
                    <Text
                      fontSize="sm"
                      color={pnl >= 0 ? 'fg.success' : 'fg.error'}
                      mt={1}
                    >
                      P&L: {pnl >= 0 ? '+' : ''}{formatMoney(pnl, CURRENCY, { maximumFractionDigits: 2 })}
                    </Text>
                  )}
                </Box>
                {previewError && (
                  <Text fontSize="sm" color="fg.error">{previewError}</Text>
                )}
              </VStack>
            )}

            {step === 2 && previewData && (
              <VStack align="stretch" gap={4}>
                <HStack justify="space-between">
                  <Text fontSize="sm" color="fg.muted">Symbol</Text>
                  <Text fontWeight="semibold">{symbol}</Text>
                </HStack>
                <HStack justify="space-between">
                  <Text fontSize="sm" color="fg.muted">Side</Text>
                  <Text>Sell</Text>
                </HStack>
                <HStack justify="space-between">
                  <Text fontSize="sm" color="fg.muted">Type</Text>
                  <Text>{orderType}</Text>
                </HStack>
                <HStack justify="space-between">
                  <Text fontSize="sm" color="fg.muted">Quantity</Text>
                  <Text>{quantity} shares</Text>
                </HStack>
                {orderType === 'limit' && (
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="fg.muted">Limit price</Text>
                    <Text>{formatMoney(limitPrice, CURRENCY)}</Text>
                  </HStack>
                )}
                {orderType === 'stop' && (
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="fg.muted">Stop price</Text>
                    <Text>{formatMoney(stopPrice, CURRENCY)}</Text>
                  </HStack>
                )}
                {previewData.preview && (
                  <>
                    {previewData.preview.estimated_commission != null && (
                      <HStack justify="space-between">
                        <Text fontSize="sm" color="fg.muted">Est. commission</Text>
                        <Text>{formatMoney(Number(previewData.preview.estimated_commission), CURRENCY)}</Text>
                      </HStack>
                    )}
                    {previewData.preview.estimated_margin_impact != null && (
                      <HStack justify="space-between">
                        <Text fontSize="sm" color="fg.muted">Margin impact</Text>
                        <Text>{formatMoney(Number(previewData.preview.estimated_margin_impact), CURRENCY)}</Text>
                      </HStack>
                    )}
                  </>
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
                {submitError && (
                  <Text fontSize="sm" color="fg.error">{submitError}</Text>
                )}
              </VStack>
            )}

            {step === 3 && orderStatus && (
              <VStack align="stretch" gap={4}>
                <HStack justify="center">
                  <Badge
                    size="lg"
                    colorPalette={getStatusBadgeColor(String(orderStatus.status ?? ''))}
                    variant="solid"
                  >
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
          <DialogFooter>
            {step === 1 && (
              <>
                <Button variant="outline" onClick={handleClose}>Cancel</Button>
                <Button
                  colorPalette="red"
                  loading={previewLoading}
                  disabled={quantity < 1 || quantity > sharesHeld}
                  onClick={fetchPreview}
                >
                  Preview Order
                </Button>
              </>
            )}
            {step === 2 && (
              <>
                <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
                <Button
                  colorPalette="red"
                  loading={submitLoading}
                  onClick={submitOrder}
                >
                  Confirm & Submit
                </Button>
              </>
            )}
            {step === 3 && (
              <Button onClick={handleClose}>Close</Button>
            )}
          </DialogFooter>
          <DialogCloseTrigger />
        </DialogContent>
      </DialogPositioner>
    </DialogRoot>
  );
}
