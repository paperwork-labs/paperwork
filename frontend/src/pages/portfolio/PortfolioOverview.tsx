import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Alert,
  Box,
  Text,
  Stack,
  Grid,
  CardRoot,
  CardBody,
  Badge,
  Button,
  HStack,
  VStack,
  SimpleGrid,
} from '@chakra-ui/react';
import { FiRefreshCw } from 'react-icons/fi';
import { ChartContext, ChartSlidePanel } from '../../components/market/SymbolChartUI';
import StatCard from '../../components/shared/StatCard';
import StageBar from '../../components/shared/StageBar';
import PnlText from '../../components/shared/PnlText';
import PageHeader from '../../components/ui/PageHeader';
import { useAccountFilter } from '../../hooks/useAccountFilter';
import { DashboardResponse } from '../../services/api';
import { usePortfolioOverview, usePositions, usePortfolioSync, usePortfolioPerformanceHistory, usePortfolioInsights, useAccountBalances, useMarginInterest, useDividendSummary, useLiveSummary, useRiskMetrics } from '../../hooks/usePortfolio';
import { useChartColors } from '../../hooks/useChartColors';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney } from '../../utils/format';
import {
  buildAccountsFromPositions,
  stageCountsFromPositions,
  sectorAllocationFromPositions,
  topMoversFromPositions,
  timeAgo,
} from '../../utils/portfolio';
import { StatCardSkeleton } from '../../components/shared/Skeleton';
import type { AccountData } from '../../hooks/useAccountFilter';
import type { EnrichedPosition } from '../../types/portfolio';
import { SECTOR_PALETTE } from '../../constants/chart';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, AreaChart, Area, XAxis, YAxis } from 'recharts';

const PERIODS = [{ key: '30d', label: '30d' }, { key: '90d', label: '90d' }, { key: '1y', label: '1Y' }, { key: 'all', label: 'All' }] as const;

const PortfolioOverview: React.FC = () => {
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [historyPeriod, setHistoryPeriod] = useState<string>('1y');
  const { currency } = useUserPreferences();
  const colors = useChartColors();
  const overview = usePortfolioOverview();
  const positionsQuery = usePositions();
  const syncMutation = usePortfolioSync();
  const historyQuery = usePortfolioPerformanceHistory({ period: historyPeriod });
  const insightsQuery = usePortfolioInsights();
  const insights = insightsQuery.data;
  const balancesQuery = useAccountBalances();
  const marginQuery = useMarginInterest();
  const balances = (balancesQuery.data ?? []) as Array<Record<string, any>>;
  const marginItems = (marginQuery.data ?? []) as Array<Record<string, any>>;
  const dividendQuery = useDividendSummary();
  const dividendData = dividendQuery.data ?? {};
  const liveQuery = useLiveSummary();
  const liveData = liveQuery.data ?? {};
  const riskQuery = useRiskMetrics();
  const riskData = riskQuery.data ?? {};
  const positions = (positionsQuery.data ?? []) as EnrichedPosition[];
  const dashboard = overview.summary.data as DashboardResponse | undefined;
  const rawAccounts = overview.accountsData ?? [];
  const historySeries = (historyQuery.data ?? []) as Array<{ date: string; total_value: number }>;

  const accounts: AccountData[] = useMemo(
    () =>
      buildAccountsFromPositions(
        rawAccounts.map((a: { id?: number; account_number?: string; broker?: string; account_name?: string; account_type?: string; last_successful_sync?: string | null }) => ({
          id: a.id,
          account_number: a.account_number ?? String(a.id),
          broker: a.broker ?? 'Unknown',
          account_name: a.account_name,
          account_type: a.account_type,
          last_successful_sync: a.last_successful_sync,
        })),
        positions
      ),
    [rawAccounts, positions]
  );

  const filterState = useAccountFilter(positions as import('../../hooks/useAccountFilter').FilterableItem[], accounts);
  const filteredPositions = filterState.filteredData as EnrichedPosition[];
  const { counts: stageCounts, total: stageTotal } = useMemo(() => stageCountsFromPositions(positions), [positions]);
  const sectorData = useMemo(() => sectorAllocationFromPositions(positions), [positions]);
  const { contributors, detractors } = useMemo(() => topMoversFromPositions(positions), [positions]);

  const summary = (dashboard?.data?.summary ?? dashboard?.summary ?? dashboard) as import('../../services/api').DashboardSummary | undefined;
  const totalValue = Number(summary?.total_market_value ?? 0);
  const totalCost = Number(summary?.total_cost_basis ?? 0);
  const unrealizedPnl = Number(summary?.unrealized_pnl ?? totalValue - totalCost);
  const unrealizedPnlPct = totalCost ? (unrealizedPnl / totalCost) * 100 : 0;
  const dayChange = Number(summary?.day_change ?? 0);
  const dayChangePct = Number(summary?.day_change_pct ?? 0);

  const openChart = (symbol: string) => setChartSymbol(symbol);

  return (
    <ChartContext.Provider value={openChart}>
      <Box p={4}>
        <Stack gap={4}>
          <PageHeader
            title="Portfolio Overview"
            subtitle="KPIs, allocation, stage distribution, and account summary"
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

          {!liveQuery.isLoading && !liveData.is_live && (
            <Alert.Root colorPalette="yellow" status="warning" variant="subtle" size="sm">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Description fontSize="sm">
                  Live data disconnected. Portfolio values may be stale.{' '}
                  <Link to="/settings/connections" style={{ textDecoration: 'underline', fontWeight: 600 }}>Reconnect in Settings</Link>
                </Alert.Description>
              </Alert.Content>
            </Alert.Root>
          )}

          {(overview.isLoading || positionsQuery.isLoading) && (
            <SimpleGrid columns={{ base: 2, md: 4 }} gap={4}>
              {[1, 2, 3, 4].map((i) => <StatCardSkeleton key={i} />)}
            </SimpleGrid>
          )}
          {!(overview.isLoading || positionsQuery.isLoading) && (overview.error || positionsQuery.error) ? (
            <Text color="status.danger">Failed to load portfolio data</Text>
          ) : null}
          {((): React.ReactNode => {
            if (overview.isLoading || positionsQuery.isLoading) return null;
            if (overview.error || positionsQuery.error) return null;
            const pos = filteredPositions;
            const filteredStage = stageCountsFromPositions(pos);
            const filteredSector = sectorAllocationFromPositions(pos);
            const filteredMovers = topMoversFromPositions(pos);
            const filteredTotal = pos.reduce((s, p) => s + Number(p.market_value ?? 0), 0);
            const filteredCost = pos.reduce((s, p) => {
              const avg = (p as { average_cost?: number; shares?: number }).average_cost;
              const sh = (p as { shares?: number }).shares ?? 0;
              return s + Number(p.cost_basis ?? (avg != null ? avg * sh : 0));
            }, 0);
            const filteredPnl = pos.reduce((s, p) => s + Number(p.unrealized_pnl ?? 0), 0);
            const filteredPnlPct = filteredTotal ? (filteredPnl / filteredTotal) * 100 : 0;
            const filteredBalances = filterState.selectedAccount === 'all'
              ? balances
              : balances.filter((b) => {
                  const raw = rawAccounts.find((a: { id?: number }) => a.id === b.account_id);
                  return raw && (
                    (raw as any).account_number === filterState.selectedAccount ||
                    String(raw.id) === filterState.selectedAccount
                  );
                });
            const nlvTotal = filteredBalances.reduce((s, b) => s + Number(b.net_liquidation ?? 0), 0);
            const kpiValue = nlvTotal > 0 ? nlvTotal : filteredTotal;
            return (
              <>
                  {/* 1. KPI Hero Row */}
                  <Box display="flex" gap={3} flexWrap="wrap">
                    <StatCard
                      label="Total Value"
                      value={formatMoney(kpiValue, currency, { maximumFractionDigits: 0 })}
                      sub={nlvTotal > 0 ? `NLV (incl. cash)` : filteredCost ? `Cost basis ${formatMoney(filteredCost, currency, { maximumFractionDigits: 0 })}` : undefined}
                    />
                    <StatCard
                      label="Day P&L"
                      value={formatMoney(dayChange, currency)}
                      sub={dayChangePct !== 0 ? `${dayChangePct >= 0 ? '+' : ''}${dayChangePct.toFixed(2)}%` : undefined}
                      trend={dayChange >= 0 ? 'up' : 'down'}
                      color={dayChange >= 0 ? 'status.success' : 'status.danger'}
                    />
                    <StatCard
                      label="Unrealized P&L"
                      value={formatMoney(filteredPnl, currency)}
                      sub={filteredPnlPct !== 0 ? `${filteredPnlPct >= 0 ? '+' : ''}${filteredPnlPct.toFixed(2)}%` : undefined}
                      color={filteredPnl >= 0 ? 'status.success' : 'status.danger'}
                    />
                    <StatCard label="Positions" value={pos.length} />
                  </Box>

                  {/* 2. Data Freshness Indicator */}
                  {rawAccounts.length > 0 && (
                    <HStack gap={4} p={3} borderRadius="md" bg="bg.subtle" flexWrap="wrap" alignItems="center">
                      {rawAccounts.map((a: { id?: number; account_number?: string; broker?: string; last_successful_sync?: string | null }) => {
                        const syncTime = a.last_successful_sync ? new Date(a.last_successful_sync) : null;
                        const ageMs = syncTime ? Date.now() - syncTime.getTime() : Infinity;
                        const ageHours = ageMs / (1000 * 60 * 60);
                        const dotColor = ageHours < 1 ? 'green.500' : ageHours < 24 ? 'yellow.400' : 'red.400';
                        return (
                          <HStack key={a.id} gap={1}>
                            <Box w="8px" h="8px" borderRadius="full" bg={dotColor} />
                            <Text fontSize="xs" color="fg.muted">
                              {(a.broker || '').toUpperCase()} {(a.account_number || '').slice(-4)} · {syncTime ? timeAgo(a.last_successful_sync) : 'Never synced'}
                            </Text>
                          </HStack>
                        );
                      })}
                      <Button
                        size="xs"
                        variant="solid"
                        colorPalette="brand"
                        onClick={() => syncMutation.mutate()}
                        loading={syncMutation.isLoading}
                        ml="auto"
                      >
                        <HStack gap={1}><FiRefreshCw size={12} /> Sync All</HStack>
                      </Button>
                    </HStack>
                  )}

                  {/* 3. Equity Curve (full width, taller) */}
                  <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                    <CardBody>
                      <HStack justify="space-between" mb={3}>
                        <Text fontSize="sm" fontWeight="semibold" color="fg.muted">
                          Value over time
                        </Text>
                        <HStack gap={1}>
                          {PERIODS.map((p) => (
                            <Button
                              key={p.key}
                              size="xs"
                              variant={historyPeriod === p.key ? 'solid' : 'outline'}
                              colorPalette="brand"
                              onClick={() => setHistoryPeriod(p.key)}
                            >
                              {p.label}
                            </Button>
                          ))}
                        </HStack>
                      </HStack>
                      {historyQuery.isLoading ? (
                        <Text fontSize="sm" color="fg.muted">Loading…</Text>
                      ) : historySeries.length > 0 ? (
                        <ResponsiveContainer width="100%" height={300}>
                          <AreaChart data={historySeries} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                            <defs>
                              <linearGradient id="portfolioValueGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={colors.area1} stopOpacity={0.25} />
                                <stop offset="100%" stopColor={colors.area1} stopOpacity={0.02} />
                              </linearGradient>
                            </defs>
                            <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                            <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => formatMoney(v, currency, { maximumFractionDigits: 0 })} />
                            <Tooltip formatter={(v: number | undefined, _name?: string) => formatMoney(Number(v ?? 0), currency) as React.ReactNode} labelFormatter={(d) => String(d)} />
                            <Area type="monotone" dataKey="total_value" stroke={colors.area1} fill="url(#portfolioValueGradient)" strokeWidth={1.5} />
                          </AreaChart>
                        </ResponsiveContainer>
                      ) : (
                        <Text fontSize="sm" color="fg.muted">No performance history yet. Snapshots are recorded after sync.</Text>
                      )}
                    </CardBody>
                  </CardRoot>

                  {/* 3. Two-col: Sector pie + Account cards */}
                  <Grid templateColumns={{ base: '1fr', lg: '1fr 1fr' }} gap={4}>
                    <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                      <CardBody>
                        <Text fontSize="sm" fontWeight="semibold" color="fg.muted" mb={3}>
                          Allocation (by sector)
                        </Text>
                        {filteredSector.length > 0 ? (
                          <ResponsiveContainer width="100%" height={240}>
                            <PieChart>
                              <Pie
                                data={filteredSector}
                                dataKey="value"
                                nameKey="name"
                                cx="40%"
                                cy="50%"
                                innerRadius={55}
                                outerRadius={85}
                                paddingAngle={2}
                              >
                                {filteredSector.map((_, i) => (
                                  <Cell key={i} fill={SECTOR_PALETTE[i % SECTOR_PALETTE.length]} />
                                ))}
                              </Pie>
                              <Tooltip formatter={(v: number | undefined, _name?: string) => formatMoney(Number(v ?? 0), currency) as React.ReactNode} />
                              <Legend
                                layout="vertical"
                                align="right"
                                verticalAlign="middle"
                                iconType="circle"
                                iconSize={8}
                                formatter={(value: string, entry: any) => {
                                  const total = filteredSector.reduce((s, x) => s + x.value, 0);
                                  const item = filteredSector.find(s => s.name === value);
                                  const pct = item && total > 0 ? ((item.value / total) * 100).toFixed(0) : '0';
                                  return <span style={{ fontSize: '11px', color: 'var(--chakra-colors-fg-muted)' }}>{value} {pct}%</span>;
                                }}
                              />
                            </PieChart>
                          </ResponsiveContainer>
                        ) : (
                          <Text fontSize="sm" color="fg.muted">No sector data</Text>
                        )}
                      </CardBody>
                    </CardRoot>

                    {accounts.length > 0 ? (
                      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                        <CardBody>
                          <Text fontSize="sm" fontWeight="semibold" color="fg.muted" mb={3}>Accounts</Text>
                          <SimpleGrid columns={{ base: 1, md: accounts.length > 2 ? 2 : 1 }} gap={2}>
                            {accounts.map((acc) => {
                              const raw = rawAccounts.find((a: { account_number?: string; id?: unknown }) => (a.account_number ?? String(a.id)) === acc.account_id);
                              const bal = balances.find((b: { account_id?: number }) => b.account_id === raw?.id);
                              const nlv = Number(bal?.net_liquidation ?? 0);
                              const displayValue = nlv > 0 ? nlv : acc.total_value;
                              const isSelected = filterState.selectedAccount === acc.account_id;
                              return (
                                <Box
                                  key={acc.account_id}
                                  p={3}
                                  borderWidth={isSelected ? '2px' : '1px'}
                                  borderColor={isSelected ? 'brand.500' : 'border.subtle'}
                                  borderRadius="lg"
                                  cursor="pointer"
                                  transition="all 0.15s"
                                  _hover={{ bg: 'bg.muted', borderColor: 'brand.300' }}
                                  onClick={() => filterState.setSelectedAccount(isSelected ? 'all' : acc.account_id)}
                                >
                                  <HStack justify="space-between" mb={1}>
                                    <HStack gap={2}>
                                      <Text fontWeight="semibold" fontSize="sm">{acc.broker}</Text>
                                      <Badge size="sm" variant="subtle" colorPalette="gray">{(raw as any)?.account_type ?? 'TAXABLE'}</Badge>
                                    </HStack>
                                    <Text fontSize="xs" color="fg.muted" fontFamily="mono">···{(acc.account_id || '').slice(-4)}</Text>
                                  </HStack>
                                  <Text fontSize="lg" fontWeight="bold">{formatMoney(displayValue, currency, { maximumFractionDigits: 0 })}</Text>
                                  <Text fontSize="xs" color="fg.muted">
                                    {acc.positions_count} positions · {timeAgo(raw?.last_successful_sync)}
                                  </Text>
                                </Box>
                              );
                            })}
                          </SimpleGrid>
                        </CardBody>
                      </CardRoot>
                    ) : null}
                  </Grid>

                  {/* 4. Two-col: Stage bar + Top movers */}
                  <Grid templateColumns={{ base: '1fr', lg: '1fr 1fr' }} gap={4}>
                    <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                      <CardBody>
                        <Text fontSize="sm" fontWeight="semibold" color="fg.muted" mb={3}>
                          Stage distribution (portfolio)
                        </Text>
                        <StageBar counts={filteredStage.counts} total={filteredStage.total} />
                      </CardBody>
                    </CardRoot>

                    <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                      <CardBody>
                        <Text fontSize="sm" fontWeight="semibold" color="fg.muted" mb={3}>
                          Top movers
                        </Text>
                        <HStack gap={6} align="flex-start" flexWrap="wrap">
                          <VStack align="start" gap={1}>
                            <Text fontSize="xs" color="status.success">Top contributors</Text>
                            {filteredMovers.contributors.length === 0 ? (
                              <Text fontSize="xs" color="fg.muted">—</Text>
                            ) : (
                              filteredMovers.contributors.map((p) => (
                                <HStack key={p.symbol} gap={2}>
                                  <Text fontFamily="mono" fontSize="xs">{p.symbol}</Text>
                                  <PnlText value={Number(p.unrealized_pnl ?? 0)} format="currency" fontSize="xs" currency={currency} />
                                </HStack>
                              ))
                            )}
                          </VStack>
                          <VStack align="start" gap={1}>
                            <Text fontSize="xs" color="status.danger">Top detractors</Text>
                            {filteredMovers.detractors.length === 0 ? (
                              <Text fontSize="xs" color="fg.muted">—</Text>
                            ) : (
                              filteredMovers.detractors.map((p) => (
                                <HStack key={p.symbol} gap={2}>
                                  <Text fontFamily="mono" fontSize="xs">{p.symbol}</Text>
                                  <PnlText value={Number(p.unrealized_pnl ?? 0)} format="currency" fontSize="xs" currency={currency} />
                                </HStack>
                              ))
                            )}
                          </VStack>
                        </HStack>
                      </CardBody>
                    </CardRoot>
                  </Grid>

                  {/* 5. Insights */}
                  {insights && (
                    <Grid templateColumns={{ base: '1fr', lg: '1fr 1fr 1fr' }} gap={4}>
                      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                        <CardBody>
                          <HStack mb={3} gap={2}>
                            <Text fontSize="sm" fontWeight="semibold" color="fg.muted">Tax Loss Harvest</Text>
                            <Badge size="sm" colorPalette="red">{insights.harvest_candidates?.length ?? 0}</Badge>
                          </HStack>
                          {(insights.harvest_candidates?.length ?? 0) === 0 ? (
                            <Text fontSize="xs" color="fg.muted">No harvesting candidates right now</Text>
                          ) : (
                            <VStack align="stretch" gap={1}>
                              {insights.harvest_candidates.map((c) => (
                                <HStack key={c.symbol} justify="space-between">
                                  <Text fontFamily="mono" fontSize="xs">{c.symbol}</Text>
                                  <Text fontSize="xs" color="fg.error">{formatMoney(c.unrealized_pnl, currency, { maximumFractionDigits: 0 })}</Text>
                                </HStack>
                              ))}
                            </VStack>
                          )}
                        </CardBody>
                      </CardRoot>

                      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                        <CardBody>
                          <HStack mb={3} gap={2}>
                            <Text fontSize="sm" fontWeight="semibold" color="fg.muted">Approaching Long-Term</Text>
                            <Badge size="sm" colorPalette="yellow">{insights.approaching_lt?.length ?? 0}</Badge>
                          </HStack>
                          {(insights.approaching_lt?.length ?? 0) === 0 ? (
                            <Text fontSize="xs" color="fg.muted">No positions near the 365-day threshold</Text>
                          ) : (
                            <VStack align="stretch" gap={1}>
                              {insights.approaching_lt.map((p) => (
                                <HStack key={p.symbol} justify="space-between">
                                  <Text fontFamily="mono" fontSize="xs">{p.symbol}</Text>
                                  <Text fontSize="xs" color="yellow.400">{p.days_to_lt}d to LT</Text>
                                </HStack>
                              ))}
                            </VStack>
                          )}
                        </CardBody>
                      </CardRoot>

                      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                        <CardBody>
                          <HStack mb={3} gap={2}>
                            <Text fontSize="sm" fontWeight="semibold" color="fg.muted">Concentration Risk</Text>
                            <Badge size="sm" colorPalette="orange">{insights.concentration_warnings?.length ?? 0}</Badge>
                          </HStack>
                          {(insights.concentration_warnings?.length ?? 0) === 0 ? (
                            <Text fontSize="xs" color="fg.muted">Portfolio is well-diversified</Text>
                          ) : (
                            <VStack align="stretch" gap={1}>
                              {insights.concentration_warnings.map((w) => (
                                <HStack key={w.symbol} justify="space-between">
                                  <Text fontFamily="mono" fontSize="xs">{w.symbol}</Text>
                                  <Text fontSize="xs" color="orange.400">{w.pct_of_portfolio}%</Text>
                                </HStack>
                              ))}
                            </VStack>
                          )}
                        </CardBody>
                      </CardRoot>
                    </Grid>
                  )}

                  {/* 6. Collapsible: Dividends, Risk & Margin */}
                  {(dividendData.trailing_12m_income != null || riskData.beta != null || marginItems.length > 0) && (
                    <details>
                      <summary style={{ cursor: 'pointer', fontSize: '14px', fontWeight: 600, color: 'var(--chakra-colors-fg-muted)', padding: '8px 0' }}>
                        Dividends, Risk & Margin
                      </summary>
                      <Stack gap={4} mt={2}>
                        <Text fontSize="sm" fontWeight="semibold" color="fg.muted">Dividend Income</Text>
                        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} gap={3}>
                          <StatCard label="Trailing 12M Income" value={formatMoney(dividendData.trailing_12m_income ?? 0, currency, { maximumFractionDigits: 0 })} color="status.success" />
                          <StatCard label="Forward Yield" value={`${dividendData.estimated_forward_yield_pct ?? 0}%`} />
                          <StatCard label="Top Payer" value={dividendData.top_payers?.[0]?.symbol ?? '-'} sub={dividendData.top_payers?.[0] ? formatMoney(dividendData.top_payers[0].annual_income, currency, { maximumFractionDigits: 0 }) : ''} />
                          <StatCard label="Upcoming Ex-Date" value={dividendData.upcoming_ex_dates?.[0]?.symbol ?? 'None'} sub={dividendData.upcoming_ex_dates?.[0]?.est_ex_date ?? ''} />
                        </SimpleGrid>

                        <Text fontSize="sm" fontWeight="semibold" color="fg.muted">Risk Profile</Text>
                        <SimpleGrid columns={{ base: 1, md: 2, lg: 5 }} gap={3}>
                          <StatCard label="Beta" value={riskData.beta ?? 1.0} />
                          <StatCard label="Volatility (Ann.)" value={`${riskData.volatility ?? 0}%`} color={Number(riskData.volatility) > 30 ? 'status.danger' : undefined} />
                          <StatCard label="Sharpe Ratio" value={riskData.sharpe_ratio ?? 0} />
                          <StatCard label="Top 5 Weight" value={`${riskData.top5_weight ?? 0}%`} sub={riskData.concentration_label ?? ''} />
                          <StatCard label="HHI" value={riskData.hhi ?? 0} sub={riskData.concentration_label ?? ''} />
                        </SimpleGrid>

                        {marginItems.length > 0 && (
                          <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                            <CardBody>
                              <Text fontSize="sm" fontWeight="semibold" color="fg.muted" mb={3}>Margin & Interest</Text>
                              <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} gap={3}>
                                {marginItems.slice(0, 4).map((m) => (
                                  <Box key={m.id} p={2} borderWidth="1px" borderColor="border.subtle" borderRadius="md">
                                    <Text fontSize="xs" color="fg.muted">{m.from_date} – {m.to_date}</Text>
                                    <Text fontSize="sm" fontWeight="bold">{formatMoney(Number(m.interest_accrued ?? 0), currency)}</Text>
                                    {m.interest_rate != null && <Text fontSize="xs" color="fg.muted">Rate: {(Number(m.interest_rate) * 100).toFixed(2)}%</Text>}
                                    {m.ending_balance != null && <Text fontSize="xs" color="fg.muted">Balance: {formatMoney(Number(m.ending_balance), currency, { maximumFractionDigits: 0 })}</Text>}
                                  </Box>
                                ))}
                              </SimpleGrid>
                            </CardBody>
                          </CardRoot>
                        )}
                      </Stack>
                    </details>
                  )}

                  {/* 7. Account Health (only if margin accounts present) */}
                  {balances.some((b) => b.initial_margin_req != null) && (
                    <Box>
                      <HStack gap={2} mb={3}>
                        <Text fontSize="sm" fontWeight="semibold" color="fg.muted">Account Health</Text>
                        {liveData.is_live && <Badge size="sm" colorPalette="green">Live</Badge>}
                      </HStack>
                      <Box display="flex" gap={3} flexWrap="wrap">
                        {balances.map((b) => {
                          const marginUtil = Number(b.margin_utilization_pct ?? 0);
                          const marginColor = marginUtil > 60 ? 'status.danger' : marginUtil > 30 ? 'yellow.400' : 'status.success';
                          const netLiq = (liveData.is_live && liveData.net_liquidation != null && balances.length === 1) ? Number(liveData.net_liquidation) : Number(b.net_liquidation ?? 0);
                          return (
                            <React.Fragment key={b.account_id}>
                              <StatCard label={`Cash (${b.broker ?? ''})`} value={formatMoney(Number(b.cash_balance ?? b.total_cash_value ?? 0), currency, { maximumFractionDigits: 0 })} sub={b.available_funds != null ? `Avail ${formatMoney(b.available_funds, currency, { maximumFractionDigits: 0 })}` : undefined} />
                              <StatCard label="Net Liquidation" value={formatMoney(netLiq, currency, { maximumFractionDigits: 0 })} />
                              <StatCard label="Buying Power" value={formatMoney(Number(b.buying_power ?? 0), currency, { maximumFractionDigits: 0 })} />
                              {b.initial_margin_req != null && (
                                <StatCard label="Margin Used" value={`${marginUtil.toFixed(1)}%`} color={marginColor} sub={`Init ${formatMoney(Number(b.initial_margin_req), currency, { maximumFractionDigits: 0 })}`} />
                              )}
                              {b.leverage != null && <StatCard label="Leverage" value={`${Number(b.leverage).toFixed(2)}x`} />}
                              {b.cushion != null && <StatCard label="Cushion" value={`${(Number(b.cushion) * 100).toFixed(1)}%`} />}
                            </React.Fragment>
                          );
                        })}
                      </Box>
                    </Box>
                  )}
              </>
            ) as React.ReactNode;
          })()}
        </Stack>
      </Box>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
};

export default PortfolioOverview;
