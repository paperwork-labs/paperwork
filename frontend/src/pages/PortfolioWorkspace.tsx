import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Flex,
  VStack,
  Input,
  InputGroup,
  Text,
  Badge,
  CardRoot,
  CardBody,
  CardHeader,
  SimpleGrid,
  Spinner,
  Button,
  TableScrollArea,
  TableRoot,
  TableHeader,
  TableBody,
  TableRow,
  TableColumnHeader,
  TableCell,
} from '@chakra-ui/react';
import { FiRefreshCw, FiSearch } from 'react-icons/fi';
import PageHeader from '../components/ui/PageHeader';
import SymbolChartWithMarkers from '../components/charts/SymbolChartWithMarkers';
import TradingViewChart from '../components/charts/TradingViewChart';
import { marketDataApi } from '../services/api';
import { portfolioApi } from '../services/api';
import { useAccountContext } from '../context/AccountContext';

interface StockRow {
  id: number;
  symbol: string;
  shares: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

interface TxRow {
  id?: string;
  date?: string;
  time?: string;
  type?: string;
  action?: string;
  symbol?: string;
  quantity?: number;
  price?: number;
  amount?: number;
  description?: string;
}

interface LotRow {
  id?: string;
  purchase_date?: string;
  cost_per_share?: number;
  shares?: number;
  shares_remaining?: number;
}

const PortfolioWorkspace: React.FC = () => {
  const { selected } = useAccountContext();
  const [loading, setLoading] = useState(true);
  const [holdings, setHoldings] = useState<StockRow[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [transactions, setTransactions] = useState<TxRow[]>([]);
  const [lots, setLots] = useState<LotRow[]>([]);
  const [search, setSearch] = useState('');
  const [bars, setBars] = useState<any[]>([]);
  const [showTrades, setShowTrades] = useState(true);
  const [showDividends, setShowDividends] = useState(true);
  const [hoverDaySec, setHoverDaySec] = useState<number | null>(null);
  const [lockedDaySec, setLockedDaySec] = useState<number | null>(null);
  const focusedDaySec = lockedDaySec ?? hoverDaySec;
  const [showLine, setShowLine] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [period, setPeriod] = useState<'1y' | '3y' | '5y' | 'max'>('max'); // fetch all by default
  const [zoomYears, setZoomYears] = useState<number | 'all'>(2); // default zoom to last 2 years
  const currencyFmt = useMemo(() => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }), []);
  const fmtDate = (iso: string | undefined) => {
    if (!iso) return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: '2-digit' });
  };
  // Render-only with Lightweight charts (no TradingView embed toggle)

  const fetchAll = async () => {
    setLoading(true);
    try {
      const param = selected === 'all' || selected === 'taxable' || selected === 'ira' ? undefined : selected;
      const [stocksRes, statementsRes] = await Promise.all([
        portfolioApi.getStocks(param),
        portfolioApi.getStatements(param, 3650),
      ]);

      const stocks: StockRow[] = (stocksRes?.data?.stocks ?? stocksRes?.data?.holdings ?? stocksRes?.stocks ?? []) as StockRow[];
      setHoldings(stocks);
      if (!selectedSymbol && stocks.length > 0) {
        setSelectedSymbol(stocks[0].symbol);
      }
      const tx: TxRow[] = (statementsRes?.data?.transactions ?? statementsRes?.transactions ?? []) as TxRow[];
      setTransactions(tx);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, [selected]);

  // Load history for selected symbol
  useEffect(() => {
    const loadHistory = async () => {
      if (!selectedSymbol) return;
      try {
        const res: any = await marketDataApi.getHistory(selectedSymbol, period, '1d');
        setBars(res?.data?.bars || res?.bars || []);
      } catch {
        setBars([]);
      }
    };
    loadHistory();
  }, [selectedSymbol, period]);

  // Load tax lots for selected holding (to backfill buy markers)
  useEffect(() => {
    const loadLots = async () => {
      if (!selectedSymbol) return setLots([]);
      try {
        const h = holdings.find(h => h.symbol === selectedSymbol);
        if (!h?.id) return setLots([]);
        const res: any = await portfolioApi.getHoldingTaxLots(h.id);
        const tl = res?.data?.tax_lots || [];
        setLots(tl);
      } catch {
        setLots([]);
      }
    };
    loadLots();
  }, [selectedSymbol, holdings]);
  const filteredHoldings = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = holdings.slice().sort((a, b) => b.market_value - a.market_value);
    if (!q) return list;
    return list.filter((h) => h.symbol.toLowerCase().includes(q));
  }, [holdings, search]);

  // Auto-scroll panels to keep focused date in view
  useEffect(() => {
    if (!lockedDaySec && !hoverDaySec) return;
    const daySec = lockedDaySec ?? hoverDaySec;
    if (!daySec) return;
    const day = new Date(daySec * 1000).toISOString().slice(0, 10);
    let el = document.querySelector<HTMLElement>(`[id^="lot-${day}"]`);
    if (!el) el = document.querySelector<HTMLElement>(`[id^="div-${day}"]`);
    if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [lockedDaySec, hoverDaySec]);

  const symbolTx = useMemo(() => {
    if (!selectedSymbol) return [];
    return transactions
      .filter((t) => (t.symbol || '').toUpperCase() === selectedSymbol.toUpperCase())
      .sort((a, b) => (a.date || '').localeCompare(b.date || ''))
      .reverse()
      .slice(0, 50);
  }, [transactions, selectedSymbol]);

  if (loading) {
    return (
      <VStack p={6} gap={6} align="stretch">
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <PageHeader title="Workspace" subtitle="Holdings list • Trades and dividends by symbol" />
          <Spinner />
        </Box>
      </VStack>
    );
  }

  return (
    <VStack p={6} gap={4} align="stretch">
      <Flex gap={4} align="stretch">
        {/* Left: holdings list */}
        <VStack bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl" p={3} gap={3} align="stretch" w="340px" h="calc(100vh - 2rem)">
          <Box display="flex" gap={2} alignItems="center">
            <InputGroup
              startElement={
                <Box color="fg.muted" display="flex" alignItems="center">
                  <FiSearch />
                </Box>
              }
            >
              <Input placeholder="Search holdings..." value={search} onChange={(e) => setSearch(e.target.value)} />
            </InputGroup>
            <Button size="sm" variant="outline" onClick={fetchAll}>
              <FiRefreshCw />
              Refresh
            </Button>
          </Box>
          <VStack gap={2} align="stretch" overflowY="auto">
            {filteredHoldings.map((h) => {
              const active = selectedSymbol?.toUpperCase() === h.symbol.toUpperCase();
              const color = h.unrealized_pnl >= 0 ? 'fg.success' : 'fg.error';
              return (
                <Box
                  key={h.id}
                  onClick={() => setSelectedSymbol(h.symbol)}
                  cursor="pointer"
                  p={2}
                  borderRadius="lg"
                  borderWidth="1px"
                  borderColor={active ? 'border.emphasis' : 'border.subtle'}
                  _hover={{ bg: 'bg.muted' }}
                  display="flex"
                  gap={2}
                  alignItems="center"
                >
                  <Box w="8px" h="8px" borderRadius="full" bg="border.emphasis" />
                  <VStack gap={0} align="start" flex={1}>
                    <Box display="flex" justifyContent="space-between" width="full">
                      <Text fontWeight="bold">{h.symbol}</Text>
                      <Badge colorPalette={h.unrealized_pnl >= 0 ? 'green' : 'red'}>
                        {h.unrealized_pnl_pct.toFixed(2)}%
                      </Badge>
                    </Box>
                    <Box display="flex" justifyContent="space-between" width="full">
                      <Text fontSize="xs" color="fg.muted">{h.shares.toLocaleString()} sh</Text>
                      <Text fontSize="xs" color={color}>${Math.abs(h.unrealized_pnl).toLocaleString()}</Text>
                    </Box>
                  </VStack>
                </Box>
              );
            })}
          </VStack>
        </VStack>

        {/* Right: detail pane */}
        <VStack flex={1} gap={4} align="stretch">
          {/* Chart */}
          <CardRoot borderWidth="1px" borderColor="border.subtle" bg="bg.card">
            <CardHeader pb={2}>
              <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={3}>
                <Text fontWeight="bold">{selectedSymbol || '—'}</Text>
                <Box display="flex" gap={3} alignItems="center" flexWrap="wrap">
                  <Badge>Live</Badge>
                  <Box display="flex" gap={2} alignItems="center">
                    <Text fontSize="xs" color="fg.muted">Advanced</Text>
                    <Button size="xs" variant={showAdvanced ? 'solid' : 'outline'} onClick={() => setShowAdvanced(v => !v)}>
                      {showAdvanced ? 'On' : 'Off'}
                    </Button>
                  </Box>
                  <Box display="flex" gap={2} alignItems="center" opacity={showAdvanced ? 0.4 : 1}>
                    <Text fontSize="xs" color="fg.muted">Range</Text>
                    <Button size="xs" disabled={showAdvanced} variant={period === '1y' ? 'solid' : 'outline'} onClick={() => { setPeriod('1y'); setZoomYears(1); }}>1y</Button>
                    <Button size="xs" disabled={showAdvanced} variant={period === '3y' ? 'solid' : 'outline'} onClick={() => { setPeriod('3y'); setZoomYears(3); }}>3y</Button>
                    <Button size="xs" disabled={showAdvanced} variant={period === '5y' ? 'solid' : 'outline'} onClick={() => { setPeriod('5y'); setZoomYears(5); }}>5y</Button>
                    <Button size="xs" disabled={showAdvanced} variant={period === 'max' ? 'solid' : 'outline'} onClick={() => { setPeriod('max'); setZoomYears('all'); }}>All</Button>
                  </Box>
                  <Box display="flex" gap={2} alignItems="center">
                    <Text fontSize="xs" color="fg.muted">Trades</Text>
                    <Button size="xs" variant={showTrades ? 'solid' : 'outline'} onClick={() => setShowTrades(v => !v)}>
                      {showTrades ? 'On' : 'Off'}
                    </Button>
                  </Box>
                  <Box display="flex" gap={2} alignItems="center">
                    <Text fontSize="xs" color="fg.muted">Dividends</Text>
                    <Button size="xs" variant={showDividends ? 'solid' : 'outline'} onClick={() => setShowDividends(v => !v)}>
                      {showDividends ? 'On' : 'Off'}
                    </Button>
                  </Box>
                  <Box display="flex" gap={2} alignItems="center">
                    <Text fontSize="xs" color="fg.muted">Line</Text>
                    <Button size="xs" variant={showLine ? 'solid' : 'outline'} onClick={() => setShowLine(v => !v)}>
                      {showLine ? 'On' : 'Off'}
                    </Button>
                  </Box>
                </Box>
              </Box>
              {lockedDaySec && (
                <Box mt={2} display="flex" gap={3} alignItems="center" flexWrap="wrap">
                  <Badge colorPalette="purple">Pinned</Badge>
                  <Text fontSize="sm">{new Date(lockedDaySec * 1000).toISOString().slice(0, 10)}</Text>
                  <Button size="xs" variant="outline" onClick={() => setLockedDaySec(null)}>
                    Clear
                  </Button>
                </Box>
              )}
            </CardHeader>
            <CardBody>
              {selectedSymbol ? (
                showAdvanced ? (
                  <TradingViewChart
                    symbol={selectedSymbol}
                    height={520}
                    showHeader={false}
                    theme="dark"
                  />
                ) : (
                  <SymbolChartWithMarkers
                    height={520}
                    bars={bars}
                    showTrades={showTrades}
                    showDividends={showDividends}
                    onHoverDaySec={setHoverDaySec}
                    onClickDaySec={(t) => setLockedDaySec(prev => (prev === t ? null : t || null))}
                    showLine={showLine}
                    zoomYears={zoomYears}
                    avgPrice={(() => {
                      // Weighted average cost based on lots
                      if (!lots?.length) return undefined;
                      const entries = lots.map(l => ({ cost: Number(l.cost_per_share || 0), sh: Number((l.shares_remaining ?? l.shares) || 0) })).filter(e => e.sh > 0 && e.cost > 0);
                      const totSh = entries.reduce((s, e) => s + e.sh, 0);
                      if (!totSh) return undefined;
                      const wavg = entries.reduce((s, e) => s + e.cost * e.sh, 0) / totSh;
                      return Number.isFinite(wavg) ? wavg : undefined;
                    })()}
                    pinnedDaySec={lockedDaySec}
                    buys={symbolTx
                      .filter(t => {
                        const k = (t.type || t.action || '').toUpperCase();
                        const d = (t.description || '').toUpperCase();
                        return k.includes('BUY') || d.includes('BUY') || d.includes('BOT');
                      })
                      .map(t => {
                        const iso = `${t.date || ''}T${t.time || '13:30:00'}Z`;
                        const fallbackClose = (() => {
                          if (!bars?.length) return 0;
                          const target = new Date(iso).getTime();
                          let best = bars[0];
                          let diff = Math.abs(new Date(bars[0].time).getTime() - target);
                          for (const b of bars) {
                            const d = Math.abs(new Date(b.time).getTime() - target);
                            if (d < diff) {
                              best = b; diff = d;
                            }
                          }
                          return Number(best?.close || 0);
                        })();
                        const price = Number(t.price || 0) || fallbackClose;
                        const qty = Number(t.quantity || 0);
                        return { time: iso, price, type: 'BUY' as const, label: `Buy ${qty} @ ${price.toFixed(2)}` };
                      }).concat(
                        // Tax-lot derived opening purchases (fallback)
                        (lots || []).map((l) => {
                          const iso = `${(l.purchase_date || '').slice(0, 10)}T13:30:00Z`;
                          const price = Number(l.cost_per_share || 0) || 0;
                          const qty = Number((l.shares_remaining ?? l.shares) || 0);
                          return { time: iso, price, type: 'BUY' as const, label: `Buy ${qty} @ ${price.toFixed(2)}` };
                        })
                      )}
                    sells={symbolTx
                      .filter(t => {
                        const k = (t.type || t.action || '').toUpperCase();
                        const d = (t.description || '').toUpperCase();
                        return k.includes('SELL') || k.includes('SLD') || d.includes('SELL') || d.includes('SLD');
                      })
                      .map(t => {
                        const iso = `${t.date || ''}T${t.time || '13:30:00'}Z`;
                        const fallbackClose = (() => {
                          if (!bars?.length) return 0;
                          const target = new Date(iso).getTime();
                          let best = bars[0];
                          let diff = Math.abs(new Date(bars[0].time).getTime() - target);
                          for (const b of bars) {
                            const d = Math.abs(new Date(b.time).getTime() - target);
                            if (d < diff) {
                              best = b; diff = d;
                            }
                          }
                          return Number(best?.close || 0);
                        })();
                        const price = Number(t.price || 0) || fallbackClose;
                        const qty = Number(t.quantity || 0);
                        return { time: iso, price, type: 'SELL' as const, label: `Sell ${qty} @ ${price.toFixed(2)}` };
                      })}
                    dividends={symbolTx
                      .filter(t => {
                        const k = (t.type || t.description || '').toUpperCase();
                        return k.includes('DIV');
                      })
                      .map(t => {
                        const amt = Number(t.amount || 0);
                        return { time: `${t.date || ''}T13:30:00Z`, amount: amt, label: `Div $${amt.toFixed(2)}` };
                      })}
                  />
                )
              ) : <Box h="520px" />}
            </CardBody>
          </CardRoot>

          <SimpleGrid columns={{ base: 1, xl: 2 }} gap={4}>
            {/* Tax Lots panel (focused on hover) */}
            <CardRoot borderWidth="1px" borderColor="border.subtle" maxH="320px" overflow="hidden" bg="bg.card">
              <CardHeader pb={2}>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Text fontWeight="bold">Tax Lots</Text>
                  <Badge variant="outline">{(lots || []).length}</Badge>
                </Box>
              </CardHeader>
              <CardBody p={0}>
                <TableScrollArea maxH="260px">
                  <TableRoot size="sm">
                    <TableHeader>
                      <TableRow>
                        <TableColumnHeader>Date</TableColumnHeader>
                        <TableColumnHeader textAlign="end">Shares</TableColumnHeader>
                        <TableColumnHeader textAlign="end">Cost/Share</TableColumnHeader>
                        <TableColumnHeader textAlign="end">Cost</TableColumnHeader>
                        <TableColumnHeader textAlign="end">Value</TableColumnHeader>
                        <TableColumnHeader textAlign="end">P/L</TableColumnHeader>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(lots || [])
                        .slice()
                        .sort((a, b) => new Date(b.purchase_date || '').getTime() - new Date(a.purchase_date || '').getTime())
                        .map((l, idx) => {
                          const lotDay = (l.purchase_date || '').slice(0, 10);
                          const hoverDay = focusedDaySec ? new Date(focusedDaySec * 1000).toISOString().slice(0, 10) : '';
                          const focused = hoverDay && lotDay === hoverDay;
                          const sh = Number((l.shares_remaining ?? l.shares) || 0);
                          const cps = Number(l.cost_per_share || 0);
                          const cost = sh * cps;
                          const lastClose = bars?.length ? Number(bars[bars.length - 1].close || 0) : 0;
                          const val = sh * lastClose;
                          const pnl = val - cost;
                          return (
                            <TableRow
                              id={`lot-${lotDay}-${idx}`}
                              key={`lot-${l.id || idx}`}
                              bg={focused ? 'bg.muted' : undefined}
                            >
                              <TableCell>{fmtDate(l.purchase_date)}</TableCell>
                              <TableCell textAlign="end">{sh.toLocaleString()}</TableCell>
                              <TableCell textAlign="end">{cps ? currencyFmt.format(cps) : '-'}</TableCell>
                              <TableCell textAlign="end">{cost ? currencyFmt.format(cost) : '-'}</TableCell>
                              <TableCell textAlign="end">{val ? currencyFmt.format(val) : '-'}</TableCell>
                              <TableCell textAlign="end" color={pnl >= 0 ? 'fg.success' : 'fg.error'}>
                                {pnl ? currencyFmt.format(pnl) : '-'}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                    </TableBody>
                  </TableRoot>
                </TableScrollArea>
              </CardBody>
            </CardRoot>

            {/* Dividends (focused on hover) */}
            <CardRoot borderWidth="1px" borderColor="border.subtle" maxH="320px" overflow="hidden" bg="bg.card">
              <CardHeader pb={2}>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Text fontWeight="bold">Dividends (received)</Text>
                </Box>
              </CardHeader>
              <CardBody p={0}>
                <TableScrollArea maxH="260px">
                  <TableRoot size="sm">
                    <TableHeader>
                      <TableRow>
                        <TableColumnHeader>Date</TableColumnHeader>
                        <TableColumnHeader textAlign="end">Amount</TableColumnHeader>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {symbolTx
                        .filter((t) => {
                          const k = (t.type || '').toUpperCase();
                          const d = (t.description || '').toUpperCase();
                          return k.includes('DIV') || d.includes('DIV');
                        })
                        .map((t, idx) => {
                          const day = (t.date || '').slice(0, 10);
                          const hoverDay = focusedDaySec ? new Date(focusedDaySec * 1000).toISOString().slice(0, 10) : '';
                          const focused = hoverDay && day === hoverDay;
                          return (
                            <TableRow id={`div-${day}-${idx}`} key={`div-${t.id || idx}`} bg={focused ? 'bg.muted' : undefined}>
                              <TableCell>{fmtDate(t.date)}</TableCell>
                              <TableCell textAlign="end">{t.amount ? currencyFmt.format(Number(t.amount)) : '-'}</TableCell>
                            </TableRow>
                          );
                        })}
                    </TableBody>
                  </TableRoot>
                </TableScrollArea>
              </CardBody>
            </CardRoot>
          </SimpleGrid>
        </VStack>
      </Flex>
    </VStack>
  );
};

export default PortfolioWorkspace;


