import React, { useState, useMemo } from 'react';
import {
  Box,
  Text,
  Stack,
  HStack,
  Button,
  CardRoot,
  CardBody,
  VStack,
  Badge,
  Collapsible,
  SimpleGrid,
  Input,
  TableScrollArea,
  TableRoot,
  TableHeader,
  TableBody,
  TableRow,
  TableColumnHeader,
  TableCell,
} from '@chakra-ui/react';
import { FiRefreshCw, FiChevronDown, FiChevronRight, FiWifi, FiWifiOff, FiGrid, FiList } from 'react-icons/fi';
import { useQuery } from 'react-query';
import { ChartContext, SymbolLink, ChartSlidePanel } from '../../components/market/SymbolChartUI';
import StatCard from '../../components/shared/StatCard';
import { StatCardSkeleton, TableSkeleton } from '../../components/shared/Skeleton';
import PnlText from '../../components/shared/PnlText';
import PageHeader from '../../components/ui/PageHeader';
import AccountFilterWrapper from '../../components/ui/AccountFilterWrapper';
import SortableTable from '../../components/SortableTable';
import type { Column, FilterGroup } from '../../components/SortableTable';
import { useOptions, usePortfolioSync, usePortfolioAccounts } from '../../hooks/usePortfolio';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { useAccountContext } from '../../context/AccountContext';
import { formatMoney } from '../../utils/format';
import { buildAccountsFromBroker } from '../../utils/portfolio';
import type { AccountData, FilterableItem } from '../../hooks/useAccountFilter';
import api from '../../services/api';

type OptionPos = {
  id: number;
  symbol: string;
  underlying_symbol: string;
  strike_price: number;
  expiration_date: string | null;
  option_type: string;
  quantity: number;
  average_open_price?: number;
  current_price?: number;
  market_value?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  days_to_expiration?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  implied_volatility?: number;
  underlying_price?: number;
  cost_basis?: number;
  realized_pnl?: number;
  commission?: number;
  currency?: string;
  account_id?: number;
};

const EXPIRING_SOON_DAYS = 7;

type TabId = 'positions' | 'chain' | 'pnl';
type PosView = 'card' | 'table';

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function moneyness(pos: OptionPos): 'ITM' | 'OTM' | 'ATM' | null {
  const u = Number(pos.underlying_price ?? 0);
  if (!u || !pos.strike_price) return null;
  const pct = Math.abs(u - pos.strike_price) / pos.strike_price;
  if (pct <= 0.02) return 'ATM';
  const isCall = (pos.option_type || '').toUpperCase() === 'CALL';
  if (isCall) return u > pos.strike_price ? 'ITM' : 'OTM';
  return u < pos.strike_price ? 'ITM' : 'OTM';
}

function moneynessPct(pos: OptionPos): number | null {
  const u = Number(pos.underlying_price ?? 0);
  if (!u || !pos.strike_price) return null;
  return ((u - pos.strike_price) / pos.strike_price) * 100;
}

const MONEYNESS_COLOR: Record<string, string> = {
  ITM: 'green',
  OTM: 'red',
  ATM: 'yellow',
};

type StrategyLabel = 'Vertical Spread' | 'Straddle' | 'Strangle' | 'Iron Condor' | 'Iron Butterfly' | null;

interface StrategyGroup {
  label: StrategyLabel;
  positions: OptionPos[];
  netPnl: number;
  netDelta: number;
}

function detectStrategies(positions: OptionPos[]): StrategyGroup[] {
  const groups: StrategyGroup[] = [];
  const used = new Set<number>();

  const byUnderlying = new Map<string, OptionPos[]>();
  for (const p of positions) {
    const sym = p.underlying_symbol;
    if (!byUnderlying.has(sym)) byUnderlying.set(sym, []);
    byUnderlying.get(sym)!.push(p);
  }

  for (const [, symPositions] of byUnderlying) {
    const byExpiry = new Map<string, OptionPos[]>();
    for (const p of symPositions) {
      const exp = p.expiration_date?.slice(0, 10) ?? 'none';
      if (!byExpiry.has(exp)) byExpiry.set(exp, []);
      byExpiry.get(exp)!.push(p);
    }

    for (const [, expPositions] of byExpiry) {
      if (expPositions.length < 2) continue;
      const calls = expPositions.filter(p => (p.option_type || '').toUpperCase() === 'CALL');
      const puts = expPositions.filter(p => (p.option_type || '').toUpperCase() === 'PUT');

      // Iron Condor: 2 calls + 2 puts, different strikes
      if (calls.length >= 2 && puts.length >= 2) {
        const legs = [...calls.slice(0, 2), ...puts.slice(0, 2)];
        const strikes = new Set(legs.map(l => l.strike_price));
        if (strikes.size >= 3) {
          for (const l of legs) used.add(l.id);
          groups.push({
            label: 'Iron Condor',
            positions: legs,
            netPnl: legs.reduce((s, p) => s + Number(p.unrealized_pnl ?? 0), 0),
            netDelta: legs.reduce((s, p) => s + Number(p.delta ?? 0) * p.quantity, 0),
          });
          continue;
        }
      }

      // Straddle: 1 call + 1 put, same strike
      if (calls.length >= 1 && puts.length >= 1) {
        for (const c of calls) {
          const match = puts.find(p => p.strike_price === c.strike_price && !used.has(p.id));
          if (match && !used.has(c.id)) {
            used.add(c.id);
            used.add(match.id);
            groups.push({
              label: 'Straddle',
              positions: [c, match],
              netPnl: Number(c.unrealized_pnl ?? 0) + Number(match.unrealized_pnl ?? 0),
              netDelta: Number(c.delta ?? 0) * c.quantity + Number(match.delta ?? 0) * match.quantity,
            });
          }
        }
        // Strangle: 1 call + 1 put, different strikes
        for (const c of calls) {
          if (used.has(c.id)) continue;
          const match = puts.find(p => p.strike_price !== c.strike_price && !used.has(p.id));
          if (match) {
            used.add(c.id);
            used.add(match.id);
            groups.push({
              label: 'Strangle',
              positions: [c, match],
              netPnl: Number(c.unrealized_pnl ?? 0) + Number(match.unrealized_pnl ?? 0),
              netDelta: Number(c.delta ?? 0) * c.quantity + Number(match.delta ?? 0) * match.quantity,
            });
          }
        }
      }

      // Vertical Spread: same type, different strikes
      const remaining = expPositions.filter(p => !used.has(p.id));
      const remCalls = remaining.filter(p => (p.option_type || '').toUpperCase() === 'CALL');
      const remPuts = remaining.filter(p => (p.option_type || '').toUpperCase() === 'PUT');
      for (const bucket of [remCalls, remPuts]) {
        if (bucket.length >= 2) {
          const sorted = bucket.slice().sort((a, b) => a.strike_price - b.strike_price);
          for (let i = 0; i < sorted.length - 1; i += 2) {
            const a = sorted[i], b = sorted[i + 1];
            if (!used.has(a.id) && !used.has(b.id) && a.strike_price !== b.strike_price) {
              used.add(a.id);
              used.add(b.id);
              groups.push({
                label: 'Vertical Spread',
                positions: [a, b],
                netPnl: Number(a.unrealized_pnl ?? 0) + Number(b.unrealized_pnl ?? 0),
                netDelta: Number(a.delta ?? 0) * a.quantity + Number(b.delta ?? 0) * b.quantity,
              });
            }
          }
        }
      }
    }
  }

  return groups;
}

/* ------------------------------------------------------------------ */
/* Main Component                                                      */
/* ------------------------------------------------------------------ */

const PortfolioOptions: React.FC = () => {
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('positions');
  const [posView, setPosView] = useState<PosView>('card');
  const [chainSymbol, setChainSymbol] = useState('');
  const { selected } = useAccountContext();
  const { currency } = useUserPreferences();
  const optionsQuery = useOptions(selected === 'all' ? undefined : selected);
  const accountsQuery = usePortfolioAccounts();
  const syncMutation = usePortfolioSync();

  const gatewayQuery = useQuery(
    ['ibGatewayStatus'],
    async () => {
      const res = await api.get('/portfolio/options/gateway-status');
      return res.data?.data ?? { connected: false, available: false };
    },
    { staleTime: 30000, refetchInterval: 60000 },
  );
  const gwConnected = gatewayQuery.data?.connected ?? false;

  const rawAccounts = accountsQuery.data ?? [];
  const accounts: AccountData[] = useMemo(
    () => buildAccountsFromBroker(rawAccounts as import('../../utils/portfolio').BrokerAccountLike[]),
    [rawAccounts],
  );

  const data = optionsQuery.data as { positions?: OptionPos[]; underlyings?: Record<string, { calls: OptionPos[]; puts: OptionPos[]; total_value: number; total_pnl: number }> } | undefined;
  const summaryData = optionsQuery.summaryData as { summary?: { total_market_value?: number; total_unrealized_pnl?: number; total_positions?: number; calls_count?: number; puts_count?: number; expiring_this_week?: number; avg_days_to_expiration?: number; net_delta?: number; net_theta?: number } } | undefined;

  const positions = data?.positions ?? [];
  const underlyings = data?.underlyings ?? {};
  const summary = summaryData?.summary ?? {};
  const totalValue = Number(summary.total_market_value ?? 0);
  const totalPnl = Number(summary.total_unrealized_pnl ?? 0);
  const totalPnlPct = totalValue ? (totalPnl / totalValue) * 100 : 0;
  const callsCount = Number(summary.calls_count ?? 0);
  const putsCount = Number(summary.puts_count ?? 0);
  const expiringSoon = Number(summary.expiring_this_week ?? 0);
  const avgDte = Number(summary.avg_days_to_expiration ?? 0);
  const netDelta = Number(summary.net_delta ?? 0);
  const netTheta = Number(summary.net_theta ?? 0);

  const netGamma = useMemo(() => positions.reduce((s, p) => s + Number(p.gamma ?? 0) * p.quantity, 0), [positions]);
  const netVega = useMemo(() => positions.reduce((s, p) => s + Number(p.vega ?? 0) * p.quantity, 0), [positions]);
  const totalRealizedPnl = useMemo(() => positions.reduce((s, p) => s + Number(p.realized_pnl ?? 0), 0), [positions]);
  const totalCommission = useMemo(() => positions.reduce((s, p) => s + Number(p.commission ?? 0), 0), [positions]);

  const openChart = (symbol: string) => setChartSymbol(symbol);

  const uniqueUnderlyings = useMemo(() => Object.keys(underlyings).sort(), [underlyings]);

  const strategies = useMemo(() => detectStrategies(positions), [positions]);

  return (
    <ChartContext.Provider value={openChart}>
      <Box p={4}>
        <Stack gap={4}>
          <PageHeader
            title="Options"
            subtitle="Positions, chains, and P&L analysis"
            rightContent={
              <HStack gap={3}>
                <GatewayStatusBadge connected={gwConnected} loading={gatewayQuery.isLoading} />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => syncMutation.mutate()}
                  loading={syncMutation.isLoading}
                >
                  <HStack gap={2}><FiRefreshCw /> Sync</HStack>
                </Button>
              </HStack>
            }
          />

          {/* Summary strip */}
          <Box display="flex" gap={3} flexWrap="wrap">
            <StatCard
              label="Total Value"
              value={formatMoney(totalValue, currency, { maximumFractionDigits: 0 })}
            />
            <StatCard label="Calls" value={callsCount} />
            <StatCard label="Puts" value={putsCount} />
            <StatCard
              label="Expiring Soon"
              value={expiringSoon}
              sub={expiringSoon > 0 ? `within ${EXPIRING_SOON_DAYS} days` : undefined}
              color={expiringSoon > 0 ? 'status.warning' : undefined}
            />
            <StatCard label="Avg DTE" value={avgDte} sub="days" />
            <StatCard
              label="Total P&L"
              value={formatMoney(totalPnl, currency)}
              sub={totalPnlPct !== 0 ? `${totalPnlPct >= 0 ? '+' : ''}${totalPnlPct.toFixed(1)}%` : undefined}
              color={totalPnl >= 0 ? 'status.success' : 'status.danger'}
            />
            <StatCard
              label="Realized P&L"
              value={formatMoney(totalRealizedPnl, currency)}
              color={totalRealizedPnl >= 0 ? 'status.success' : 'status.danger'}
            />
            <StatCard
              label="Commission"
              value={formatMoney(Math.abs(totalCommission), currency)}
              color="status.danger"
            />
            <StatCard label="Net Delta" value={netDelta.toFixed(2)} />
            <StatCard
              label="Daily Theta"
              value={formatMoney(netTheta, currency)}
              color={netTheta < 0 ? 'status.danger' : 'status.success'}
            />
            <StatCard label="Net Gamma" value={netGamma.toFixed(3)} />
            <StatCard label="Net Vega" value={netVega.toFixed(2)} />
          </Box>

          {/* Tabs */}
          <HStack gap={1} borderBottomWidth="1px" borderColor="border.subtle" pb={0} justifyContent="space-between">
            <HStack gap={1}>
              {(['positions', 'chain', 'pnl'] as TabId[]).map(tab => (
                <Button
                  key={tab}
                  size="sm"
                  variant={activeTab === tab ? 'solid' : 'ghost'}
                  onClick={() => setActiveTab(tab)}
                  borderBottomRadius={0}
                  textTransform="capitalize"
                >
                  {tab === 'pnl' ? 'P&L' : tab === 'chain' ? 'Option Chain' : 'Positions'}
                </Button>
              ))}
            </HStack>
            {activeTab === 'positions' && (
              <HStack gap={1}>
                <Button
                  size="xs"
                  variant={posView === 'card' ? 'solid' : 'ghost'}
                  onClick={() => setPosView('card')}
                  aria-label="Card view"
                >
                  <FiGrid />
                </Button>
                <Button
                  size="xs"
                  variant={posView === 'table' ? 'solid' : 'ghost'}
                  onClick={() => setPosView('table')}
                  aria-label="Table view"
                >
                  <FiList />
                </Button>
              </HStack>
            )}
          </HStack>

          {/* Tab content */}
          {activeTab === 'positions' && (
            <AccountFilterWrapper
              data={positions as FilterableItem[]}
              accounts={accounts}
              config={{ showAllOption: true, showSummary: false, variant: 'simple' }}
              loading={optionsQuery.isLoading || accountsQuery.isLoading}
              error={optionsQuery.error || accountsQuery.error ? 'Failed to load options' : null}
              loadingComponent={<TableSkeleton rows={5} cols={4} />}
            >
              {(filteredPositions) => {
                const typed = filteredPositions as OptionPos[];
                const filteredSet = new Set(typed.map(p => p.id));
                const filteredUnderlyings: Record<string, { calls: OptionPos[]; puts: OptionPos[]; total_value: number; total_pnl: number }> = {};
                for (const [sym, grp] of Object.entries(underlyings)) {
                  const fc = grp.calls.filter(p => filteredSet.has(p.id));
                  const fp = grp.puts.filter(p => filteredSet.has(p.id));
                  if (fc.length + fp.length > 0) {
                    filteredUnderlyings[sym] = {
                      calls: fc,
                      puts: fp,
                      total_value: [...fc, ...fp].reduce((s, p) => s + Number(p.market_value ?? 0), 0),
                      total_pnl: [...fc, ...fp].reduce((s, p) => s + Number(p.unrealized_pnl ?? 0), 0),
                    };
                  }
                }

                if (posView === 'table') {
                  return (
                    <PositionsTableView
                      positions={typed}
                      currency={currency}
                      gwConnected={gwConnected}
                    />
                  );
                }

                return (
                  <>
                    {/* Strategy groups */}
                    {strategies.length > 0 && (
                      <VStack align="stretch" gap={3} mb={3}>
                        <Text fontSize="sm" fontWeight="bold" color="fg.muted">Detected Strategies</Text>
                        {strategies.map((sg, idx) => (
                          <CardRoot key={idx} bg="bg.card" borderWidth="1px" borderColor="border.emphasis" borderRadius="xl">
                            <CardBody py={3}>
                              <HStack justify="space-between" mb={2}>
                                <HStack gap={2}>
                                  <Badge colorPalette="purple" variant="subtle">{sg.label}</Badge>
                                  <Text fontSize="xs" color="fg.muted">
                                    {sg.positions[0]?.underlying_symbol} {sg.positions[0]?.expiration_date?.slice(0, 10)}
                                  </Text>
                                </HStack>
                                <HStack gap={3}>
                                  <Text fontSize="xs" color="fg.muted">Delta {sg.netDelta.toFixed(2)}</Text>
                                  <PnlText value={sg.netPnl} format="currency" fontSize="sm" currency={currency} />
                                </HStack>
                              </HStack>
                              <VStack align="stretch" gap={1}>
                                {sg.positions.map(pos => (
                                  <PositionRow key={pos.id} pos={pos} currency={currency} gwConnected={gwConnected} />
                                ))}
                              </VStack>
                            </CardBody>
                          </CardRoot>
                        ))}
                      </VStack>
                    )}

                    {Object.keys(filteredUnderlyings).length === 0 ? (
                      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                        <CardBody>
                          <Text color="fg.muted">
                            {optionsQuery.isLoading ? 'Loading...' : 'No options positions.'}
                          </Text>
                        </CardBody>
                      </CardRoot>
                    ) : (
                      <VStack align="stretch" gap={3}>
                        {Object.entries(filteredUnderlyings).map(([sym, group]) => (
                          <UnderlyingGroup
                            key={sym}
                            symbol={sym}
                            group={group}
                            currency={currency}
                            openChart={openChart}
                            gwConnected={gwConnected}
                          />
                        ))}
                      </VStack>
                    )}
                  </>
                );
              }}
            </AccountFilterWrapper>
          )}

          {activeTab === 'chain' && (
            <OptionChainTab
              gwConnected={gwConnected}
              chainSymbol={chainSymbol}
              setChainSymbol={setChainSymbol}
              underlyingOptions={uniqueUnderlyings}
              positions={positions}
            />
          )}

          {activeTab === 'pnl' && (
            <PnlTab underlyings={underlyings} currency={currency} />
          )}
        </Stack>
      </Box>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
};

/* ------------------------------------------------------------------ */
/* Gateway Status Badge                                                */
/* ------------------------------------------------------------------ */
const GatewayStatusBadge: React.FC<{ connected: boolean; loading: boolean }> = ({ connected, loading }) => (
  <Badge
    colorPalette={loading ? 'gray' : connected ? 'green' : 'gray'}
    variant="subtle"
    display="flex"
    alignItems="center"
    gap={1}
    px={2}
    py={1}
  >
    {connected ? <FiWifi /> : <FiWifiOff />}
    {loading ? 'Checking...' : connected ? 'Gateway Connected' : 'Gateway Offline'}
  </Badge>
);

/* ------------------------------------------------------------------ */
/* Positions Table View (SortableTable-based)                          */
/* ------------------------------------------------------------------ */
const positionColumns: Column<OptionPos>[] = [
  {
    key: 'underlying',
    header: 'Underlying',
    accessor: (p) => p.underlying_symbol,
    sortable: true,
    sortType: 'string',
    filterable: true,
    filterType: 'text',
    render: (_v, p) => (
      <HStack gap={2}>
        <SymbolLink symbol={p.underlying_symbol} />
        {(() => {
          const m = moneyness(p);
          return m ? <Badge size="sm" colorPalette={MONEYNESS_COLOR[m]} variant="subtle">{m}</Badge> : null;
        })()}
      </HStack>
    ),
  },
  {
    key: 'type',
    header: 'Type',
    accessor: (p) => (p.option_type || '').toUpperCase(),
    sortable: true,
    sortType: 'string',
    filterable: true,
    filterType: 'select',
    filterOptions: [{ label: 'Call', value: 'CALL' }, { label: 'Put', value: 'PUT' }],
    render: (v) => <Badge size="sm" colorPalette={v === 'CALL' ? 'green' : 'red'} variant="subtle">{v}</Badge>,
    width: '70px',
  },
  {
    key: 'strike',
    header: 'Strike',
    accessor: (p) => p.strike_price,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <Text fontFamily="mono">{Number(v).toFixed(2)}</Text>,
    width: '80px',
  },
  {
    key: 'expiry',
    header: 'Expiry',
    accessor: (p) => p.expiration_date?.slice(0, 10) ?? '',
    sortable: true,
    sortType: 'date',
    render: (v) => <Text fontSize="xs">{v || '—'}</Text>,
    width: '95px',
  },
  {
    key: 'dte',
    header: 'DTE',
    accessor: (p) => p.days_to_expiration ?? 0,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const dte = Number(v);
      const color = dte <= 3 ? 'red.400' : dte <= 7 ? 'orange.400' : dte <= 30 ? 'yellow.400' : 'fg.muted';
      return (
        <HStack gap={1}>
          {dte <= 3 && <Box w="6px" h="6px" borderRadius="full" bg="red.500" className="pulse-dot" />}
          <Text fontFamily="mono" color={color} fontWeight={dte <= 7 ? 'bold' : 'normal'}>{dte}d</Text>
        </HStack>
      );
    },
    width: '70px',
  },
  {
    key: 'qty',
    header: 'Qty',
    accessor: (p) => p.quantity,
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const q = Number(v);
      return <Text fontFamily="mono" color={q < 0 ? 'fg.error' : 'fg.default'}>{q}</Text>;
    },
    width: '55px',
  },
  {
    key: 'avgPrice',
    header: 'Avg Price',
    accessor: (p) => Number(p.average_open_price ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <Text fontFamily="mono">{Number(v) ? Number(v).toFixed(2) : '—'}</Text>,
    width: '80px',
  },
  {
    key: 'current',
    header: 'Current',
    accessor: (p) => Number(p.current_price ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <Text fontFamily="mono">{Number(v) ? Number(v).toFixed(2) : '—'}</Text>,
    width: '75px',
  },
  {
    key: 'value',
    header: 'Value',
    accessor: (p) => Number(p.market_value ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    width: '90px',
  },
  {
    key: 'pnl',
    header: 'P&L',
    accessor: (p) => Number(p.unrealized_pnl ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <PnlText value={Number(v)} format="currency" fontSize="xs" />,
    width: '80px',
  },
  {
    key: 'pnlPct',
    header: 'P&L%',
    accessor: (p) => Number(p.unrealized_pnl_pct ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const pct = Number(v);
      return <Text fontSize="xs" color={pct >= 0 ? 'fg.success' : 'fg.error'}>{pct >= 0 ? '+' : ''}{pct.toFixed(1)}%</Text>;
    },
    width: '65px',
  },
  {
    key: 'delta',
    header: 'Delta',
    accessor: (p) => Number(p.delta ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <Text fontFamily="mono" fontSize="xs">{Number(v) ? Number(v).toFixed(2) : '—'}</Text>,
    width: '60px',
  },
  {
    key: 'theta',
    header: 'Theta',
    accessor: (p) => Number(p.theta ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <Text fontFamily="mono" fontSize="xs" color={Number(v) < 0 ? 'fg.error' : 'fg.success'}>{Number(v) ? Number(v).toFixed(2) : '—'}</Text>,
    width: '60px',
  },
  {
    key: 'iv',
    header: 'IV',
    accessor: (p) => Number(p.implied_volatility ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => <Text fontFamily="mono" fontSize="xs">{Number(v) > 0 ? `${(Number(v) * 100).toFixed(0)}%` : '—'}</Text>,
    width: '50px',
  },
  {
    key: 'realizedPnl',
    header: 'Realized',
    accessor: (p) => Number(p.realized_pnl ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const val = Number(v);
      if (!val) return <Text fontSize="xs" color="fg.muted">—</Text>;
      return <Text fontSize="xs" color={val >= 0 ? 'fg.success' : 'fg.error'}>{val >= 0 ? '+' : ''}{val.toFixed(0)}</Text>;
    },
    width: '70px',
  },
  {
    key: 'commission',
    header: 'Comm.',
    accessor: (p) => Number(p.commission ?? 0),
    sortable: true,
    sortType: 'number',
    isNumeric: true,
    render: (v) => {
      const val = Number(v);
      if (!val) return <Text fontSize="xs" color="fg.muted">—</Text>;
      return <Text fontSize="xs" color="fg.error">{Math.abs(val).toFixed(2)}</Text>;
    },
    width: '65px',
  },
];

const tableFilterPresets: Array<{ label: string; filters: FilterGroup }> = [
  {
    label: 'Expiring This Week',
    filters: {
      conjunction: 'AND',
      rules: [{ id: 'dte-soon', columnKey: 'dte', operator: 'lte', value: '7' }],
    },
  },
  {
    label: 'ITM Only',
    filters: {
      conjunction: 'AND',
      rules: [{ id: 'itm', columnKey: 'moneyness', operator: 'equals', value: 'ITM' }],
    },
  },
  {
    label: 'High Theta (>$5/day)',
    filters: {
      conjunction: 'AND',
      rules: [{ id: 'theta-high', columnKey: 'theta', operator: 'lt', value: '-5' }],
    },
  },
];

const PositionsTableView: React.FC<{ positions: OptionPos[]; currency: string; gwConnected: boolean }> = ({ positions, currency }) => {
  const fmtCols = useMemo(() => {
    return positionColumns.map(col => {
      if (col.key === 'value' && !col.render) {
        return {
          ...col,
          render: (v: any) => <Text fontFamily="mono" fontSize="xs">{formatMoney(Number(v), currency, { maximumFractionDigits: 0 })}</Text>,
        };
      }
      if (col.key === 'pnl' && col.render) {
        return {
          ...col,
          render: (v: any) => <PnlText value={Number(v)} format="currency" fontSize="xs" currency={currency} />,
        };
      }
      return col;
    });
  }, [currency]);

  return (
    <SortableTable
      data={positions}
      columns={fmtCols}
      defaultSortBy="dte"
      defaultSortOrder="asc"
      size="sm"
      maxHeight="70vh"
      filtersEnabled
      filterPresets={tableFilterPresets}
      emptyMessage="No options positions."
    />
  );
};

/* ------------------------------------------------------------------ */
/* Underlying Group (Card View)                                        */
/* ------------------------------------------------------------------ */
const UnderlyingGroup: React.FC<{
  symbol: string;
  group: { calls: OptionPos[]; puts: OptionPos[]; total_value: number; total_pnl: number };
  currency: string;
  openChart: (s: string) => void;
  gwConnected: boolean;
}> = ({ symbol, group, currency, gwConnected }) => {
  const [open, setOpen] = useState(true);
  const allPositions = [...group.calls, ...group.puts];
  const totalPnl = group.total_pnl ?? 0;

  const grpDelta = allPositions.reduce((s, p) => s + Number(p.delta ?? 0) * p.quantity, 0);
  const grpRealizedPnl = allPositions.reduce((s, p) => s + Number(p.realized_pnl ?? 0), 0);

  return (
    <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
      <CardBody>
        <HStack
          justify="space-between"
          cursor="pointer"
          onClick={() => setOpen(o => !o)}
          _hover={{ bg: 'bg.subtle' }}
          p={1}
          borderRadius="md"
        >
          <HStack gap={2}>
            {open ? <FiChevronDown /> : <FiChevronRight />}
            <SymbolLink symbol={symbol} />
            <Badge colorPalette="gray" size="sm">{allPositions.length} pos</Badge>
            {grpRealizedPnl !== 0 && (
              <Badge size="sm" colorPalette={grpRealizedPnl >= 0 ? 'green' : 'red'} variant="outline">
                Realized {grpRealizedPnl >= 0 ? '+' : ''}{grpRealizedPnl.toFixed(0)}
              </Badge>
            )}
          </HStack>
          <HStack gap={3}>
            <Text fontSize="xs" color="fg.muted">D {grpDelta.toFixed(2)}</Text>
            <Text fontSize="sm" color="fg.muted">{formatMoney(group.total_value, currency)}</Text>
            <PnlText value={totalPnl} format="currency" currency={currency} />
          </HStack>
        </HStack>
        <Collapsible.Root open={open}>
          <Collapsible.Content>
            <VStack align="stretch" gap={1} mt={3}>
              {allPositions.map(pos => (
                <PositionRow key={pos.id} pos={pos} currency={currency} gwConnected={gwConnected} />
              ))}
            </VStack>
          </Collapsible.Content>
        </Collapsible.Root>
      </CardBody>
    </CardRoot>
  );
};

/* ------------------------------------------------------------------ */
/* Position Row (enhanced)                                             */
/* ------------------------------------------------------------------ */
const PositionRow: React.FC<{ pos: OptionPos; currency: string; gwConnected: boolean }> = ({ pos, currency, gwConnected }) => {
  const isShort = pos.quantity < 0;
  const qty = Math.abs(pos.quantity);
  const hasGreeks = pos.delta != null || pos.theta != null;
  const dte = pos.days_to_expiration ?? 0;
  const dtePct = Math.min(100, Math.max(0, (dte / 90) * 100));
  const dteColor = dte <= 3 ? 'red.500' : dte <= 7 ? 'orange.500' : dte > 30 ? 'green.500' : 'yellow.500';
  const m = moneyness(pos);
  const mPct = moneynessPct(pos);

  return (
    <Box py={2} px={2} borderRadius="md" _hover={{ bg: 'bg.subtle' }} borderBottomWidth="1px" borderColor="border.subtle" _last={{ borderBottom: 'none' }}>
      <HStack justify="space-between" fontSize="sm" gap={3} flexWrap="wrap">
        <HStack gap={2} flex={1} minW="0">
          <Badge colorPalette={isShort ? 'red' : 'green'} size="sm" variant="subtle" flexShrink={0}>
            {isShort ? 'SHORT' : 'LONG'}
          </Badge>
          {m && (
            <Badge size="sm" colorPalette={MONEYNESS_COLOR[m]} variant="outline" flexShrink={0}>
              {m}
            </Badge>
          )}
          <Text fontFamily="mono" fontWeight="medium" truncate>
            {qty} x {pos.strike_price}{(pos.option_type || '').toUpperCase() === 'CALL' ? 'C' : 'P'} {pos.expiration_date?.slice(0, 10) ?? '—'}
          </Text>
          {mPct !== null && (
            <Text fontSize="xs" color="fg.muted" flexShrink={0}>
              {mPct >= 0 ? '+' : ''}{mPct.toFixed(1)}%
            </Text>
          )}
        </HStack>

        {/* DTE progress bar */}
        <HStack gap={2} flexShrink={0}>
          <Box w="60px" h="6px" bg="bg.muted" borderRadius="full" overflow="hidden">
            <Box h="full" bg={dteColor} w={`${dtePct}%`} borderRadius="full" transition="width 0.3s" />
          </Box>
          <HStack gap={1}>
            {dte <= 3 && <Box w="6px" h="6px" borderRadius="full" bg="red.500" />}
            <Text fontSize="xs" color={dte <= 3 ? 'red.400' : dte <= 7 ? 'orange.400' : 'fg.muted'} fontWeight={dte <= 7 ? 'bold' : 'normal'} w="35px" textAlign="right">{dte}d</Text>
          </HStack>
        </HStack>

        {/* Greeks inline */}
        {hasGreeks ? (
          <HStack gap={2} fontSize="xs" color="fg.muted" flexShrink={0}>
            {pos.delta != null && <Text>D<Text as="span" fontFamily="mono" ml={0.5}>{pos.delta.toFixed(2)}</Text></Text>}
            {pos.gamma != null && <Text>G<Text as="span" fontFamily="mono" ml={0.5}>{pos.gamma.toFixed(3)}</Text></Text>}
            {pos.theta != null && <Text>T<Text as="span" fontFamily="mono" ml={0.5} color={pos.theta < 0 ? 'fg.error' : 'fg.success'}>{pos.theta.toFixed(2)}</Text></Text>}
            {pos.vega != null && <Text>V<Text as="span" fontFamily="mono" ml={0.5}>{pos.vega.toFixed(2)}</Text></Text>}
          </HStack>
        ) : (
          <Badge size="sm" variant="outline" colorPalette={gwConnected ? 'yellow' : 'gray'} flexShrink={0}>
            {gwConnected ? 'Syncing...' : 'No Greeks'}
          </Badge>
        )}

        <PnlText value={Number(pos.unrealized_pnl ?? 0)} format="currency" fontSize="sm" currency={currency} />
      </HStack>

      {/* Extra details row */}
      <HStack gap={4} fontSize="xs" color="fg.muted" mt={1} flexWrap="wrap" pl={1}>
        <Text>Price {formatMoney(Number(pos.current_price ?? 0), currency)}</Text>
        {pos.cost_basis != null && Number(pos.cost_basis) !== 0 && (
          <Text>Cost {formatMoney(Math.abs(Number(pos.cost_basis)), currency)}</Text>
        )}
        {pos.realized_pnl != null && Number(pos.realized_pnl) !== 0 && (
          <Text color={Number(pos.realized_pnl) >= 0 ? 'fg.success' : 'fg.error'}>
            Realized {Number(pos.realized_pnl) >= 0 ? '+' : ''}{formatMoney(Number(pos.realized_pnl), currency)}
          </Text>
        )}
        {pos.commission != null && Number(pos.commission) !== 0 && (
          <Text color="fg.error">Comm. {formatMoney(Math.abs(Number(pos.commission)), currency)}</Text>
        )}
        {pos.implied_volatility != null && pos.implied_volatility > 0 && (
          <Text>IV {(pos.implied_volatility * 100).toFixed(1)}%</Text>
        )}
        {pos.underlying_price != null && Number(pos.underlying_price) > 0 && (
          <Text>Underlying {formatMoney(Number(pos.underlying_price), currency)}</Text>
        )}
      </HStack>
    </Box>
  );
};

/* ------------------------------------------------------------------ */
/* Option Chain Tab (enhanced with ATM highlight + position indicators) */
/* ------------------------------------------------------------------ */
const OptionChainTab: React.FC<{
  gwConnected: boolean;
  chainSymbol: string;
  setChainSymbol: (s: string) => void;
  underlyingOptions: string[];
  positions: OptionPos[];
}> = ({ gwConnected, chainSymbol, setChainSymbol, underlyingOptions, positions }) => {
  const [selectedExp, setSelectedExp] = useState<string | null>(null);

  const chainQuery = useQuery(
    ['optionChain', chainSymbol],
    async () => {
      const res = await api.get(`/portfolio/options/chain/${encodeURIComponent(chainSymbol)}`);
      return res.data?.data ?? { expirations: [], chains: {} };
    },
    { enabled: !!chainSymbol && gwConnected, staleTime: 30000 },
  );

  const chainData = chainQuery.data as { expirations: string[]; chains: Record<string, { calls: ChainEntry[]; puts: ChainEntry[] }> } | undefined;

  type ChainEntry = {
    strike: number;
    last?: number;
    bid?: number;
    ask?: number;
    iv?: number;
    delta?: number;
    gamma?: number;
    theta?: number;
    vega?: number;
    volume?: number;
    open_interest?: number;
  };

  const expirations = chainData?.expirations ?? [];
  const activeExp = selectedExp ?? expirations[0] ?? null;
  const activeChain = activeExp ? chainData?.chains?.[activeExp] : null;

  const heldStrikes = useMemo(() => {
    const set = new Set<string>();
    for (const p of positions) {
      if (p.underlying_symbol === chainSymbol) {
        set.add(`${p.strike_price}-${(p.option_type || '').toUpperCase()}`);
      }
    }
    return set;
  }, [positions, chainSymbol]);

  const underlyingPrice = useMemo(() => {
    const match = positions.find(p => p.underlying_symbol === chainSymbol && p.underlying_price);
    return Number(match?.underlying_price ?? 0);
  }, [positions, chainSymbol]);

  if (!gwConnected) {
    return (
      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
        <CardBody>
          <VStack gap={3} py={8}>
            <FiWifiOff size={32} />
            <Text fontWeight="bold">IB Gateway Required</Text>
            <Text color="fg.muted" textAlign="center" maxW="md">
              Option chain data requires a live connection to IB Gateway.
              Start it with <Text as="span" fontFamily="mono">make ib-up</Text> and
              configure your IBKR credentials in <Text as="span" fontFamily="mono">infra/env.dev</Text>.
            </Text>
          </VStack>
        </CardBody>
      </CardRoot>
    );
  }

  return (
    <VStack align="stretch" gap={3}>
      <HStack gap={2} flexWrap="wrap">
        <Input
          placeholder="Enter symbol..."
          value={chainSymbol}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setChainSymbol(e.target.value.toUpperCase())}
          maxW="200px"
          size="sm"
        />
        {underlyingOptions.slice(0, 8).map(sym => (
          <Button
            key={sym}
            size="xs"
            variant={chainSymbol === sym ? 'solid' : 'outline'}
            onClick={() => setChainSymbol(sym)}
          >
            {sym}
          </Button>
        ))}
      </HStack>

      {chainQuery.isLoading && <Text color="fg.muted">Loading chain...</Text>}

      {activeChain && (
        <>
          <HStack gap={1} flexWrap="wrap">
            {expirations.map(exp => (
              <Button
                key={exp}
                size="xs"
                variant={activeExp === exp ? 'solid' : 'outline'}
                onClick={() => setSelectedExp(exp)}
              >
                {exp}
              </Button>
            ))}
          </HStack>

          <Box overflowX="auto">
            <Box display="grid" gridTemplateColumns="1fr auto 1fr" gap={0} fontSize="xs">
              {/* Header */}
              <HStack bg="bg.subtle" px={2} py={1} justify="space-between">
                <Text fontWeight="bold">CALLS</Text>
                <HStack gap={3}>
                  <Text w="40px" textAlign="right">Vol</Text>
                  <Text w="40px" textAlign="right">OI</Text>
                  <Text w="50px" textAlign="right">Bid</Text>
                  <Text w="50px" textAlign="right">Ask</Text>
                  <Text w="45px" textAlign="right">Delta</Text>
                  <Text w="40px" textAlign="right">IV</Text>
                </HStack>
              </HStack>
              <Box bg="bg.emphasis" px={2} py={1} textAlign="center">
                <Text fontWeight="bold" color="fg.inverted">Strike</Text>
              </Box>
              <HStack bg="bg.subtle" px={2} py={1} justify="space-between">
                <HStack gap={3}>
                  <Text w="40px">IV</Text>
                  <Text w="45px">Delta</Text>
                  <Text w="50px">Bid</Text>
                  <Text w="50px">Ask</Text>
                  <Text w="40px">OI</Text>
                  <Text w="40px">Vol</Text>
                </HStack>
                <Text fontWeight="bold">PUTS</Text>
              </HStack>

              {/* Build merged strike list */}
              {(() => {
                const allStrikes = new Set<number>();
                activeChain.calls.forEach(c => allStrikes.add(c.strike));
                activeChain.puts.forEach(p => allStrikes.add(p.strike));
                const strikes = [...allStrikes].sort((a, b) => a - b);
                const callMap = new Map(activeChain.calls.map(c => [c.strike, c]));
                const putMap = new Map(activeChain.puts.map(p => [p.strike, p]));

                let closestAtmStrike = strikes[0] ?? 0;
                if (underlyingPrice > 0) {
                  let minDist = Infinity;
                  for (const s of strikes) {
                    const dist = Math.abs(s - underlyingPrice);
                    if (dist < minDist) { minDist = dist; closestAtmStrike = s; }
                  }
                }

                return strikes.map(strike => {
                  const call = callMap.get(strike);
                  const put = putMap.get(strike);
                  const isAtm = strike === closestAtmStrike && underlyingPrice > 0;
                  const hasCallPos = heldStrikes.has(`${strike}-CALL`);
                  const hasPutPos = heldStrikes.has(`${strike}-PUT`);

                  const rowBg = isAtm ? 'yellow.950' : undefined;

                  return (
                    <React.Fragment key={strike}>
                      <HStack px={2} py={1} borderBottomWidth="1px" borderColor="border.subtle" justify="space-between" bg={rowBg}>
                        <HStack gap={1}>
                          {hasCallPos && <Box w="6px" h="6px" borderRadius="full" bg="blue.400" />}
                          <Text fontFamily="mono">{call?.last?.toFixed(2) ?? '—'}</Text>
                        </HStack>
                        <HStack gap={3}>
                          <Text w="40px" textAlign="right" fontFamily="mono" color="fg.muted">{call?.volume ?? '—'}</Text>
                          <Text w="40px" textAlign="right" fontFamily="mono" color="fg.muted">{call?.open_interest ?? '—'}</Text>
                          <Text w="50px" textAlign="right" fontFamily="mono">{call?.bid?.toFixed(2) ?? '—'}</Text>
                          <Text w="50px" textAlign="right" fontFamily="mono">{call?.ask?.toFixed(2) ?? '—'}</Text>
                          <Text w="45px" textAlign="right" fontFamily="mono">{call?.delta?.toFixed(2) ?? '—'}</Text>
                          <Text w="40px" textAlign="right" fontFamily="mono">{call?.iv ? (call.iv * 100).toFixed(0) + '%' : '—'}</Text>
                        </HStack>
                      </HStack>
                      <Box bg={isAtm ? 'yellow.700' : 'bg.emphasis'} px={2} py={1} textAlign="center" borderBottomWidth="1px" borderColor="border.subtle">
                        <Text fontFamily="mono" fontWeight="bold" color={isAtm ? 'yellow.100' : 'fg.inverted'}>
                          {strike}
                          {isAtm && <Text as="span" fontSize="2xs" ml={1}>ATM</Text>}
                        </Text>
                      </Box>
                      <HStack px={2} py={1} borderBottomWidth="1px" borderColor="border.subtle" justify="space-between" bg={rowBg}>
                        <HStack gap={3}>
                          <Text w="40px" fontFamily="mono">{put?.iv ? (put.iv * 100).toFixed(0) + '%' : '—'}</Text>
                          <Text w="45px" fontFamily="mono">{put?.delta?.toFixed(2) ?? '—'}</Text>
                          <Text w="50px" fontFamily="mono">{put?.bid?.toFixed(2) ?? '—'}</Text>
                          <Text w="50px" fontFamily="mono">{put?.ask?.toFixed(2) ?? '—'}</Text>
                          <Text w="40px" fontFamily="mono" color="fg.muted">{put?.open_interest ?? '—'}</Text>
                          <Text w="40px" fontFamily="mono" color="fg.muted">{put?.volume ?? '—'}</Text>
                        </HStack>
                        <HStack gap={1}>
                          <Text fontFamily="mono">{put?.last?.toFixed(2) ?? '—'}</Text>
                          {hasPutPos && <Box w="6px" h="6px" borderRadius="full" bg="blue.400" />}
                        </HStack>
                      </HStack>
                    </React.Fragment>
                  );
                });
              })()}
            </Box>
          </Box>
        </>
      )}

      {!chainQuery.isLoading && !activeChain && chainSymbol && (
        <Text color="fg.muted">No chain data available for {chainSymbol}.</Text>
      )}
    </VStack>
  );
};

/* ------------------------------------------------------------------ */
/* P&L Tab (detailed table)                                            */
/* ------------------------------------------------------------------ */
const PnlTab: React.FC<{
  underlyings: Record<string, { calls: OptionPos[]; puts: OptionPos[]; total_value: number; total_pnl: number }>;
  currency: string;
}> = ({ underlyings, currency }) => {
  const rows = useMemo(() => {
    return Object.entries(underlyings).map(([sym, grp]) => {
      const callsPnl = grp.calls.reduce((s, p) => s + Number(p.unrealized_pnl ?? 0), 0);
      const putsPnl = grp.puts.reduce((s, p) => s + Number(p.unrealized_pnl ?? 0), 0);
      const totalPnl = callsPnl + putsPnl;
      const realizedPnl = [...grp.calls, ...grp.puts].reduce((s, p) => s + Number(p.realized_pnl ?? 0), 0);
      const deltaExposure = [...grp.calls, ...grp.puts].reduce((s, p) => s + Number(p.delta ?? 0) * p.quantity, 0);
      const totalValue = grp.total_value;
      const totalCost = [...grp.calls, ...grp.puts].reduce((s, p) => s + Math.abs(Number(p.cost_basis ?? 0)), 0);
      const pnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
      return { sym, callsPnl, putsPnl, totalPnl, realizedPnl, deltaExposure, totalValue, pnlPct, posCount: grp.calls.length + grp.puts.length };
    }).sort((a, b) => Math.abs(b.totalPnl) - Math.abs(a.totalPnl));
  }, [underlyings]);

  if (rows.length === 0) {
    return (
      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
        <CardBody>
          <Text color="fg.muted">No positions to analyze.</Text>
        </CardBody>
      </CardRoot>
    );
  }

  const totals = rows.reduce(
    (acc, r) => ({
      callsPnl: acc.callsPnl + r.callsPnl,
      putsPnl: acc.putsPnl + r.putsPnl,
      totalPnl: acc.totalPnl + r.totalPnl,
      realizedPnl: acc.realizedPnl + r.realizedPnl,
      deltaExposure: acc.deltaExposure + r.deltaExposure,
    }),
    { callsPnl: 0, putsPnl: 0, totalPnl: 0, realizedPnl: 0, deltaExposure: 0 },
  );

  return (
    <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
      <CardBody>
        <Text fontWeight="bold" mb={3}>P&L by Underlying</Text>
        <TableScrollArea maxH="60vh">
          <TableRoot size="sm">
            <TableHeader>
              <TableRow>
                <TableColumnHeader>Underlying</TableColumnHeader>
                <TableColumnHeader textAlign="end">Pos</TableColumnHeader>
                <TableColumnHeader textAlign="end">Value</TableColumnHeader>
                <TableColumnHeader textAlign="end">Calls P&L</TableColumnHeader>
                <TableColumnHeader textAlign="end">Puts P&L</TableColumnHeader>
                <TableColumnHeader textAlign="end">Total P&L</TableColumnHeader>
                <TableColumnHeader textAlign="end">P&L%</TableColumnHeader>
                <TableColumnHeader textAlign="end">Realized</TableColumnHeader>
                <TableColumnHeader textAlign="end">Delta Exp.</TableColumnHeader>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(r => (
                <TableRow key={r.sym}>
                  <TableCell>
                    <SymbolLink symbol={r.sym} />
                  </TableCell>
                  <TableCell textAlign="end">{r.posCount}</TableCell>
                  <TableCell textAlign="end">
                    <Text fontFamily="mono" fontSize="xs">{formatMoney(r.totalValue, currency, { maximumFractionDigits: 0 })}</Text>
                  </TableCell>
                  <TableCell textAlign="end">
                    <Text fontFamily="mono" fontSize="xs" color={r.callsPnl >= 0 ? 'fg.success' : 'fg.error'}>
                      {r.callsPnl >= 0 ? '+' : ''}{formatMoney(r.callsPnl, currency, { maximumFractionDigits: 0 })}
                    </Text>
                  </TableCell>
                  <TableCell textAlign="end">
                    <Text fontFamily="mono" fontSize="xs" color={r.putsPnl >= 0 ? 'fg.success' : 'fg.error'}>
                      {r.putsPnl >= 0 ? '+' : ''}{formatMoney(r.putsPnl, currency, { maximumFractionDigits: 0 })}
                    </Text>
                  </TableCell>
                  <TableCell textAlign="end">
                    <PnlText value={r.totalPnl} format="currency" fontSize="xs" currency={currency} />
                  </TableCell>
                  <TableCell textAlign="end">
                    <Text fontFamily="mono" fontSize="xs" color={r.pnlPct >= 0 ? 'fg.success' : 'fg.error'}>
                      {r.pnlPct >= 0 ? '+' : ''}{r.pnlPct.toFixed(1)}%
                    </Text>
                  </TableCell>
                  <TableCell textAlign="end">
                    <Text fontFamily="mono" fontSize="xs" color={r.realizedPnl >= 0 ? 'fg.success' : 'fg.error'}>
                      {r.realizedPnl !== 0 ? `${r.realizedPnl >= 0 ? '+' : ''}${formatMoney(r.realizedPnl, currency, { maximumFractionDigits: 0 })}` : '—'}
                    </Text>
                  </TableCell>
                  <TableCell textAlign="end">
                    <Text fontFamily="mono" fontSize="xs">{r.deltaExposure.toFixed(2)}</Text>
                  </TableCell>
                </TableRow>
              ))}
              {/* Totals row */}
              <TableRow bg="bg.subtle">
                <TableCell><Text fontWeight="bold">Total</Text></TableCell>
                <TableCell textAlign="end"><Text fontWeight="bold">{rows.reduce((s, r) => s + r.posCount, 0)}</Text></TableCell>
                <TableCell textAlign="end">
                  <Text fontWeight="bold" fontFamily="mono" fontSize="xs">
                    {formatMoney(rows.reduce((s, r) => s + r.totalValue, 0), currency, { maximumFractionDigits: 0 })}
                  </Text>
                </TableCell>
                <TableCell textAlign="end">
                  <Text fontWeight="bold" fontFamily="mono" fontSize="xs" color={totals.callsPnl >= 0 ? 'fg.success' : 'fg.error'}>
                    {totals.callsPnl >= 0 ? '+' : ''}{formatMoney(totals.callsPnl, currency, { maximumFractionDigits: 0 })}
                  </Text>
                </TableCell>
                <TableCell textAlign="end">
                  <Text fontWeight="bold" fontFamily="mono" fontSize="xs" color={totals.putsPnl >= 0 ? 'fg.success' : 'fg.error'}>
                    {totals.putsPnl >= 0 ? '+' : ''}{formatMoney(totals.putsPnl, currency, { maximumFractionDigits: 0 })}
                  </Text>
                </TableCell>
                <TableCell textAlign="end">
                  <PnlText value={totals.totalPnl} format="currency" fontSize="xs" currency={currency} fontWeight="bold" />
                </TableCell>
                <TableCell textAlign="end" />
                <TableCell textAlign="end">
                  <Text fontWeight="bold" fontFamily="mono" fontSize="xs" color={totals.realizedPnl >= 0 ? 'fg.success' : 'fg.error'}>
                    {totals.realizedPnl !== 0 ? `${totals.realizedPnl >= 0 ? '+' : ''}${formatMoney(totals.realizedPnl, currency, { maximumFractionDigits: 0 })}` : '—'}
                  </Text>
                </TableCell>
                <TableCell textAlign="end">
                  <Text fontWeight="bold" fontFamily="mono" fontSize="xs">{totals.deltaExposure.toFixed(2)}</Text>
                </TableCell>
              </TableRow>
            </TableBody>
          </TableRoot>
        </TableScrollArea>
      </CardBody>
    </CardRoot>
  );
};

export default PortfolioOptions;
