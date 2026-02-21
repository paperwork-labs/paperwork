import React, { useState } from 'react';
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
} from '@chakra-ui/react';
import { FiRefreshCw, FiChevronDown, FiChevronRight } from 'react-icons/fi';
import { ChartContext, SymbolLink, ChartSlidePanel } from '../../components/market/SymbolChartUI';
import StatCard from '../../components/shared/StatCard';
import { StatCardSkeleton, TableSkeleton } from '../../components/shared/Skeleton';
import PnlText from '../../components/shared/PnlText';
import PageHeader from '../../components/ui/PageHeader';
import AccountFilterWrapper from '../../components/ui/AccountFilterWrapper';
import { useOptions, usePortfolioSync, usePortfolioAccounts } from '../../hooks/usePortfolio';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { useAccountContext } from '../../context/AccountContext';
import { formatMoney } from '../../utils/format';
import { buildAccountsFromBroker } from '../../utils/portfolio';
import type { AccountData } from '../../hooks/useAccountFilter';

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
};

const EXPIRING_SOON_DAYS = 7;

const PortfolioOptions: React.FC = () => {
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const { selected } = useAccountContext();
  const { currency } = useUserPreferences();
  const optionsQuery = useOptions(selected === 'all' ? undefined : selected);
  const accountsQuery = usePortfolioAccounts();
  const syncMutation = usePortfolioSync();

  const rawAccounts = accountsQuery.data ?? [];
  const accounts: AccountData[] = React.useMemo(
    () => buildAccountsFromBroker(rawAccounts as import('../../utils/portfolio').BrokerAccountLike[]),
    [rawAccounts]
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

  const openChart = (symbol: string) => setChartSymbol(symbol);

  return (
    <ChartContext.Provider value={openChart}>
      <Box p={4}>
        <Stack gap={4}>
          <PageHeader
            title="Options"
            subtitle="Positions grouped by underlying"
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

          <AccountFilterWrapper
            data={positions}
            accounts={accounts}
            config={{ showAllOption: true, showSummary: false, variant: 'simple' }}
            loading={optionsQuery.isLoading || accountsQuery.isLoading}
            error={optionsQuery.error || accountsQuery.error ? 'Failed to load options' : null}
            loadingComponent={
              <>
                <Box display="flex" gap={3} flexWrap="wrap">
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                </Box>
                <TableSkeleton rows={5} cols={4} />
              </>
            }
          >
            {() => (
              <>
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
                  <StatCard label="Net Delta" value={netDelta.toFixed(2)} />
                  <StatCard
                    label="Daily Theta"
                    value={formatMoney(netTheta, currency)}
                    color={netTheta < 0 ? 'status.danger' : 'status.success'}
                  />
                </Box>

                {Object.keys(underlyings).length === 0 ? (
                  <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                    <CardBody>
                      <Text color="fg.muted">
                        {optionsQuery.isLoading ? 'Loading…' : 'No options positions.'}
                      </Text>
                    </CardBody>
                  </CardRoot>
                ) : (
                  <VStack align="stretch" gap={3}>
                    {Object.entries(underlyings).map(([underlyingSymbol, group]) => (
                      <UnderlyingGroup
                        key={underlyingSymbol}
                        symbol={underlyingSymbol}
                        group={group}
                        currency={currency}
                        openChart={openChart}
                      />
                    ))}
                  </VStack>
                )}
              </>
            )}
          </AccountFilterWrapper>
        </Stack>
      </Box>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
};

const UnderlyingGroup: React.FC<{
  symbol: string;
  group: { calls: OptionPos[]; puts: OptionPos[]; total_value: number; total_pnl: number };
  currency: string;
  openChart: (s: string) => void;
}> = ({ symbol, group, currency, openChart }) => {
  const [open, setOpen] = useState(true);
  const allPositions = [...group.calls, ...group.puts];
  const totalPnl = group.total_pnl ?? 0;

  return (
    <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
      <CardBody>
        <HStack
          justify="space-between"
          cursor="pointer"
          onClick={() => setOpen((o) => !o)}
          _hover={{ bg: 'bg.subtle' }}
          p={1}
          borderRadius="md"
        >
          <HStack gap={2}>
            {open ? <FiChevronDown /> : <FiChevronRight />}
            <SymbolLink symbol={symbol} />
            <Badge colorPalette="gray" size="sm">{allPositions.length} positions</Badge>
          </HStack>
          <PnlText value={totalPnl} format="currency" currency={currency} />
        </HStack>
        <Collapsible.Root open={open}>
          <Collapsible.Content>
            <VStack align="stretch" gap={2} mt={3} pl={6}>
              {allPositions.map((pos) => (
                <Box key={pos.id} py={1} borderBottomWidth="1px" borderColor="border.subtle" _last={{ borderBottom: 'none' }}>
                  <HStack justify="space-between" fontSize="sm" gap={4} flexWrap="wrap">
                    <Text fontFamily="mono" fontWeight="medium">
                      {pos.strike_price}{pos.option_type === 'call' ? 'C' : 'P'} {pos.expiration_date?.slice(0, 10) ?? '—'}
                    </Text>
                    <HStack gap={4}>
                      <Text color="fg.muted">{pos.quantity} ct</Text>
                      <Text>{formatMoney(Number(pos.current_price ?? 0), currency)}</Text>
                      <PnlText value={Number(pos.unrealized_pnl ?? 0)} format="currency" fontSize="sm" currency={currency} />
                      {pos.days_to_expiration != null && pos.days_to_expiration <= EXPIRING_SOON_DAYS && (
                        <Badge colorPalette="orange" size="sm">{pos.days_to_expiration}d</Badge>
                      )}
                    </HStack>
                  </HStack>
                  {(pos.delta != null || pos.theta != null) && (
                    <HStack gap={3} fontSize="xs" color="fg.muted" mt={0.5}>
                      {pos.delta != null && <Text>D {pos.delta.toFixed(3)}</Text>}
                      {pos.gamma != null && <Text>G {pos.gamma.toFixed(4)}</Text>}
                      {pos.theta != null && <Text>T {pos.theta.toFixed(3)}</Text>}
                      {pos.vega != null && <Text>V {pos.vega.toFixed(3)}</Text>}
                      {pos.days_to_expiration != null && <Text>{pos.days_to_expiration} DTE</Text>}
                    </HStack>
                  )}
                </Box>
              ))}
            </VStack>
          </Collapsible.Content>
        </Collapsible.Root>
      </CardBody>
    </CardRoot>
  );
};

export default PortfolioOptions;
