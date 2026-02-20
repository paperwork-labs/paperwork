import React, { useMemo, useState } from 'react';
import {
  Box,
  Text,
  Stack,
  Grid,
  CardRoot,
  CardBody,
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
import AccountFilterWrapper from '../../components/ui/AccountFilterWrapper';
import { usePortfolioOverview, usePositions, usePortfolioSync, usePortfolioPerformanceHistory } from '../../hooks/usePortfolio';
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
  const positions = (positionsQuery.data ?? []) as EnrichedPosition[];
  const dashboard = overview.summary.data as any;
  const rawAccounts = overview.accountsData ?? [];
  const historySeries = (historyQuery.data ?? []) as Array<{ date: string; total_value: number }>;

  const accounts: AccountData[] = useMemo(
    () =>
      buildAccountsFromPositions(
        rawAccounts.map((a: any) => ({
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

  const { counts: stageCounts, total: stageTotal } = useMemo(() => stageCountsFromPositions(positions), [positions]);
  const sectorData = useMemo(() => sectorAllocationFromPositions(positions), [positions]);
  const { contributors, detractors } = useMemo(() => topMoversFromPositions(positions), [positions]);

  const summary = dashboard?.data?.summary ?? dashboard?.summary ?? dashboard;
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
            return (
          <AccountFilterWrapper
            data={positions as import('../../hooks/useAccountFilter').FilterableItem[]}
            accounts={accounts}
            config={{ showAllOption: true, showSummary: true }}
            loading={false}
            error={null}
          >
            {(filteredPositions) => {
              const pos = filteredPositions as EnrichedPosition[];
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

              return (
                <>
                  <Box display="flex" gap={3} flexWrap="wrap">
                    <StatCard
                      label="Total Value"
                      value={formatMoney(filteredTotal, currency, { maximumFractionDigits: 0 })}
                      sub={filteredCost ? `Cost basis ${formatMoney(filteredCost, currency, { maximumFractionDigits: 0 })}` : undefined}
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

                  <Grid templateColumns={{ base: '1fr', lg: '1fr 1fr' }} gap={4}>
                    <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                      <CardBody>
                        <Text fontSize="sm" fontWeight="semibold" color="fg.muted" mb={3}>
                          Allocation (by sector)
                        </Text>
                        {filteredSector.length > 0 ? (
                          <ResponsiveContainer width="100%" height={220}>
                            <PieChart>
                              <Pie
                              data={filteredSector}
                              dataKey="value"
                              nameKey="name"
                              cx="50%"
                              cy="50%"
                              innerRadius={60}
                              outerRadius={90}
                              paddingAngle={2}
                              label={(props: { name?: string; percent?: number }) => `${props.name ?? ''} ${((props.percent ?? 0) * 100).toFixed(0)}%`}
                            >
                              {filteredSector.map((_, i) => (
                                <Cell key={i} fill={SECTOR_PALETTE[i % SECTOR_PALETTE.length]} />
                              ))}
                            </Pie>
                            <Tooltip formatter={(v: number | undefined) => formatMoney(Number(v ?? 0), currency)} />
                            <Legend />
                          </PieChart>
                        </ResponsiveContainer>
                        ) : (
                          <Text fontSize="sm" color="fg.muted">No sector data</Text>
                        )}
                      </CardBody>
                    </CardRoot>

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
                          <ResponsiveContainer width="100%" height={220}>
                            <AreaChart data={historySeries} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                              <defs>
                                <linearGradient id="portfolioValueGradient" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="0%" stopColor={colors.area1} stopOpacity={0.25} />
                                  <stop offset="100%" stopColor={colors.area1} stopOpacity={0.02} />
                                </linearGradient>
                              </defs>
                              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => formatMoney(v, currency, { maximumFractionDigits: 0 })} />
                              <Tooltip formatter={(v: number | undefined) => formatMoney(Number(v ?? 0), currency)} labelFormatter={(d) => String(d)} />
                              <Area type="monotone" dataKey="total_value" stroke={colors.area1} fill="url(#portfolioValueGradient)" strokeWidth={1.5} />
                            </AreaChart>
                          </ResponsiveContainer>
                        ) : (
                          <Text fontSize="sm" color="fg.muted">No performance history yet. Snapshots are recorded after sync.</Text>
                        )}
                      </CardBody>
                    </CardRoot>
                  </Grid>

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

                  {accounts.length > 0 && (
                    <Box>
                      <Text fontSize="sm" fontWeight="semibold" color="fg.muted" mb={3}>
                        Accounts
                      </Text>
                      <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={3}>
                        {accounts.map((acc) => (
                          <CardRoot key={acc.account_id} bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="lg">
                            <CardBody py={3} px={4}>
                              <HStack justify="space-between" mb={1}>
                                <Text fontWeight="semibold" fontSize="sm">{acc.broker}</Text>
                                <Text fontSize="xs" color="fg.muted">{acc.account_id}</Text>
                              </HStack>
                              <Text fontSize="lg" fontWeight="bold">{formatMoney(acc.total_value, currency, { maximumFractionDigits: 0 })}</Text>
                              <Text fontSize="xs" color="fg.muted">{acc.positions_count} positions · synced {timeAgo((rawAccounts.find((a: any) => (a.account_number ?? a.id) === acc.account_id) as any)?.last_successful_sync)}</Text>
                            </CardBody>
                          </CardRoot>
                        ))}
                      </SimpleGrid>
                    </Box>
                  )}
                </>
              );
            }}
          </AccountFilterWrapper>
            ) as React.ReactNode;
          })()}
        </Stack>
      </Box>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
};

export default PortfolioOverview;
