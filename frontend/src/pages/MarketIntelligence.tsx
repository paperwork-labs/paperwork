import React from 'react';
import {
  Box, HStack, Text, Badge, Stack, Heading, SimpleGrid, Button,
  Skeleton,
} from '@chakra-ui/react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FiRefreshCw, FiFileText, FiTrendingUp, FiCalendar } from 'react-icons/fi';
import { marketDataApi } from '../services/api';
import { REGIME_HEX, heatColor } from '../constants/chart';
import { formatDateTimeFriendly, formatDateFriendly } from '../utils/format';
import { useUserPreferences } from '../hooks/useUserPreferences';
import StatCard from '../components/shared/StatCard';
import StageBadge from '../components/shared/StageBadge';

const DATA_MONO = { fontFamily: 'mono', letterSpacing: '-0.02em' } as const;

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull', R2: 'Bull Extended', R3: 'Chop', R4: 'Bear Rally', R5: 'Bear',
};

type BriefType = 'daily' | 'weekly' | 'monthly';

const BRIEF_TABS: { key: BriefType; label: string; icon: React.ElementType }[] = [
  { key: 'daily', label: 'Daily Digest', icon: FiFileText },
  { key: 'weekly', label: 'Weekly Brief', icon: FiTrendingUp },
  { key: 'monthly', label: 'Monthly Review', icon: FiCalendar },
];

const fmtPct = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
};

const MarketIntelligence: React.FC = () => {
  const { timezone } = useUserPreferences();
  const [activeType, setActiveType] = React.useState<BriefType>('daily');
  const [isPolling, setIsPolling] = React.useState(false);
  const queryClient = useQueryClient();

  React.useEffect(() => {
    if (!isPolling) return;
    const timer = setTimeout(() => setIsPolling(false), 30_000);
    return () => clearTimeout(timer);
  }, [isPolling]);

  const { data: briefData, isPending, isError, error } = useQuery({
    queryKey: ['intelligence-brief', activeType],
    queryFn: async () => {
      const resp = await marketDataApi.getLatestBrief(activeType);
      return resp?.data ?? resp ?? null;
    },
    staleTime: 2 * 60_000,
    refetchInterval: isPolling ? 3_000 : false,
  });

  const { data: briefList } = useQuery({
    queryKey: ['intelligence-list', activeType],
    queryFn: async () => {
      const resp = await marketDataApi.listBriefs(activeType, 10);
      return resp?.data?.briefs ?? resp?.briefs ?? [];
    },
    staleTime: 5 * 60_000,
    refetchInterval: isPolling ? 5_000 : false,
  });

  const generateMutation = useMutation({
    mutationFn: () => marketDataApi.triggerBrief(activeType),
    onSuccess: () => {
      setIsPolling(true);
      queryClient.invalidateQueries({ queryKey: ['intelligence-brief', activeType] });
      queryClient.invalidateQueries({ queryKey: ['intelligence-list', activeType] });
    },
    onError: (err: any) => {
      const status = err?.response?.status;
      if (status === 403) {
        setGenerateError('Admin access required to generate briefs.');
      } else {
        setGenerateError(err?.message || 'Failed to trigger brief generation.');
      }
    },
  });

  const [generateError, setGenerateError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (isPolling && briefData?.brief) {
      setIsPolling(false);
    }
  }, [isPolling, briefData]);

  React.useEffect(() => {
    setGenerateError(null);
  }, [activeType]);

  const brief = briefData?.brief;

  return (
    <Box p={4}>
      <Stack gap={4}>
        <HStack justify="space-between" flexWrap="wrap">
          <Heading size="md">Intelligence Briefs</Heading>
          <HStack gap={2}>
            {BRIEF_TABS.map(tab => {
              const Icon = tab.icon;
              const isActive = activeType === tab.key;
              return (
                <Button
                  key={tab.key}
                  size="xs"
                  variant={isActive ? 'solid' : 'ghost'}
                  bg={isActive ? 'amber.500' : undefined}
                  color={isActive ? 'white' : undefined}
                  _hover={isActive ? { bg: 'amber.400' } : undefined}
                  onClick={() => setActiveType(tab.key)}
                  transition="all 200ms ease"
                >
                  <Icon size={12} />
                  <Text ml={1}>{tab.label}</Text>
                </Button>
              );
            })}
            <Button
              size="xs"
              variant="outline"
              onClick={() => { setGenerateError(null); generateMutation.mutate(); }}
              disabled={generateMutation.isPending || isPolling}
            >
              <FiRefreshCw size={12} />
              <Text ml={1}>{isPolling ? 'Generating...' : 'Generate'}</Text>
            </Button>
          </HStack>
        </HStack>

        {generateError && (
          <Box p={3} borderRadius="lg" bg="red.500/10" borderWidth="1px" borderColor="red.500/30">
            <Text fontSize="sm" color="red.500">{generateError}</Text>
          </Box>
        )}

        {isError ? (
          <Box p={8} textAlign="center" borderWidth="1px" borderColor="red.500/30" borderRadius="lg" bg="bg.card">
            <Text fontSize="sm" color="red.500" mb={2}>Failed to load brief.</Text>
            <Text fontSize="xs" color="fg.muted">{(error as any)?.message || 'An unexpected error occurred.'}</Text>
          </Box>
        ) : isPending ? (
          <Stack gap={4} py={4}>
            <Skeleton height="80px" borderRadius="xl" />
            <SimpleGrid columns={{ base: 2, md: 4 }} gap={3}>
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} height="64px" borderRadius="lg" />
              ))}
            </SimpleGrid>
            <Skeleton height="120px" borderRadius="lg" />
          </Stack>
        ) : !brief ? (
          <Box p={8} textAlign="center" borderWidth="1px" borderColor="border.subtle" borderRadius="lg" bg="bg.card">
            <Text fontSize="sm" color="fg.muted" mb={3}>No {activeType} brief available yet.</Text>
            <Button
              size="sm"
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
            >
              Generate {activeType} brief
            </Button>
          </Box>
        ) : (
          <>
            {/* Brief header */}
            <HStack justify="space-between" flexWrap="wrap">
              <Text fontSize="xs" color="fg.muted">
                Generated: {formatDateTimeFriendly(briefData?.generated_at, timezone)}
                {' | '}{brief.snapshot_count ?? 0} symbols analyzed
              </Text>
            </HStack>

            {/* Render based on type */}
            {activeType === 'daily' && <DailyDigestView brief={brief} />}
            {activeType === 'weekly' && <WeeklyBriefView brief={brief} />}
            {activeType === 'monthly' && <MonthlyReviewView brief={brief} />}
          </>
        )}

        {/* Brief History */}
        {Array.isArray(briefList) && briefList.length > 0 && (
          <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
            <Text fontSize="sm" fontWeight="semibold" mb={2}>Previous Briefs</Text>
            <Stack gap={1}>
              {briefList.map((b: any) => (
                <HStack key={b.id} justify="space-between" fontSize="xs" py={1} px={2} borderRadius="md" transition="background 150ms ease" _hover={{ bg: 'bg.hover' }}>
                  <HStack gap={2}>
                    <Badge variant="subtle" size="sm">{b.type}</Badge>
                    <Text {...DATA_MONO}>{b.summary?.as_of ?? '—'}</Text>
                  </HStack>
                  <HStack gap={2}>
                    {b.summary?.regime_state && (
                      <Badge variant="subtle" size="sm" colorPalette={
                        b.summary.regime_state === 'R1' ? 'green' :
                        b.summary.regime_state === 'R5' ? 'red' : 'yellow'
                      }>{b.summary.regime_state}</Badge>
                    )}
                    <Text color="fg.muted">{formatDateFriendly(b.generated_at, timezone)}</Text>
                  </HStack>
                </HStack>
              ))}
            </Stack>
          </Box>
        )}
      </Stack>
    </Box>
  );
};


const DailyDigestView: React.FC<{ brief: any }> = ({ brief }) => {
  const regime = brief.regime || {};
  const regimeColor = REGIME_HEX[regime.state] || '#64748B';

  return (
    <Stack gap={4}>
      {/* Regime */}
      <Box
        borderWidth="2px"
        borderColor={regimeColor}
        borderRadius="xl"
        p={4}
        bg="bg.card"
        position="relative"
        overflow="hidden"
      >
        <Box position="absolute" top={0} left={0} right={0} bottom={0} bg={regimeColor} opacity={0.06} />
        <HStack justify="space-between" flexWrap="wrap" gap={3} position="relative">
          <HStack gap={3}>
            <Box bg={regimeColor} color="white" px={3} py={1} borderRadius="md" fontWeight="bold" fontSize="lg">
              {regime.state}
            </Box>
            <Box>
              <Text fontWeight="semibold">{REGIME_LABELS[regime.state] || regime.state}</Text>
              <Text fontSize="xs" color="fg.muted" {...DATA_MONO}>Score: {regime.score?.toFixed(2)}</Text>
            </Box>
            {regime.changed && (
              <Badge variant="solid" colorPalette="orange" size="sm">
                Changed from {regime.previous_state}
              </Badge>
            )}
          </HStack>
          <SimpleGrid columns={3} gap={3}>
            <StatCard label="VIX" value={regime.vix_spot?.toFixed(1) ?? '—'} />
            <StatCard label="Sizing" value={`${regime.multiplier?.toFixed(2) ?? '—'}x`} />
            <StatCard label="Max Equity" value={`${regime.max_equity_pct ?? '—'}%`} />
          </SimpleGrid>
        </HStack>
      </Box>

      {/* Breadth */}
      <SimpleGrid columns={{ base: 2, md: 4 }} gap={3}>
        <StatCard label="Above 50 DMA" value={`${brief.breadth?.above_50d_pct ?? 0}%`} />
        <StatCard label="Above 200 DMA" value={`${brief.breadth?.above_200d_pct ?? 0}%`} />
        <StatCard label="Stage Transitions" value={String(brief.stage_transitions?.length ?? 0)} />
        <StatCard label="Exit Alerts" value={String(brief.exit_alerts?.length ?? 0)} />
      </SimpleGrid>

      {/* Stage Distribution */}
      {brief.stage_distribution && (
        <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Stage Distribution</Text>
          <HStack gap={2} flexWrap="wrap">
            {Object.entries(brief.stage_distribution).map(([stage, count]: [string, any]) => (
              <HStack key={stage} gap={1}>
                <StageBadge stage={stage} />
                <Text fontSize="xs">{count}</Text>
              </HStack>
            ))}
          </HStack>
        </Box>
      )}

      {/* Stage Transitions */}
      {brief.stage_transitions?.length > 0 && (
        <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Stage Transitions</Text>
          <Stack gap={1}>
            {brief.stage_transitions.map((t: any, i: number) => (
              <HStack key={`${t.symbol}-${i}`} justify="space-between" fontSize="xs">
                <Text fontWeight="semibold">{t.symbol}</Text>
                <HStack gap={1}>
                  <StageBadge stage={t.from_stage} />
                  <Text color="fg.muted">→</Text>
                  <StageBadge stage={t.to_stage} />
                  {t.days_in_stage != null && <Text color="fg.muted">{t.days_in_stage}d</Text>}
                </HStack>
              </HStack>
            ))}
          </Stack>
        </Box>
      )}

      {/* Exit Alerts */}
      {brief.exit_alerts?.length > 0 && (
        <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
          <Text fontSize="sm" fontWeight="semibold" color="red.500" mb={2}>Exit Alerts</Text>
          <Stack gap={1}>
            {brief.exit_alerts.map((a: any, i: number) => (
              <HStack key={`exit-${a.symbol}-${i}`} justify="space-between" fontSize="xs">
                <HStack gap={2}>
                  <Text fontWeight="semibold">{a.symbol}</Text>
                  <StageBadge stage={a.stage} />
                </HStack>
                {a.pnl_pct != null && (
                  <Text color={a.pnl_pct >= 0 ? 'green.500' : 'red.500'}>
                    {a.pnl_pct >= 0 ? '+' : ''}{a.pnl_pct}%
                  </Text>
                )}
              </HStack>
            ))}
          </Stack>
        </Box>
      )}
    </Stack>
  );
};


const WeeklyBriefView: React.FC<{ brief: any }> = ({ brief }) => (
  <Stack gap={4}>
    {/* Regime Trend */}
    {brief.regime_trend?.length > 0 && (
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
        <Text fontSize="sm" fontWeight="semibold" mb={2}>Regime Trend (7d)</Text>
        <HStack gap={1} flexWrap="wrap">
          {brief.regime_trend.map((r: any, i: number) => (
            <Box
              key={i}
              px={2}
              py={1}
              borderRadius="md"
              bg={REGIME_HEX[r.state] || '#64748B'}
              color="white"
              fontSize="xs"
              fontWeight="bold"
              title={`${r.date}: ${r.state} (${r.score})`}
            >
              {r.state}
            </Box>
          ))}
        </HStack>
      </Box>
    )}

    {/* Top Picks */}
    {brief.top_picks && (
      <SimpleGrid columns={{ base: 1, md: 3 }} gap={4}>
        <PickList title="Buy List" items={brief.top_picks.buy} colorPalette="green" />
        <PickList title="Watch List" items={brief.top_picks.watch} colorPalette="blue" />
        <PickList title="Short List" items={brief.top_picks.short} colorPalette="red" />
      </SimpleGrid>
    )}

    {/* Sector Analysis */}
    {brief.sector_analysis?.length > 0 && (
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
        <Text fontSize="sm" fontWeight="semibold" mb={2}>Sector Analysis</Text>
        <Stack gap={1}>
          {brief.sector_analysis.map((s: any) => (
            <HStack key={s.sector} justify="space-between" fontSize="xs" py={1} px={2} borderRadius="md" transition="background 150ms ease" _hover={{ bg: 'bg.hover' }}>
              <Text fontWeight="medium">{s.sector} ({s.count})</Text>
              <HStack gap={3}>
                <Text {...DATA_MONO} color={heatColor(s.avg_rs)}>RS {fmtPct(s.avg_rs)}</Text>
                <Text {...DATA_MONO} color="green.500">Stage 2: {s.stage2_pct}%</Text>
              </HStack>
            </HStack>
          ))}
        </Stack>
      </Box>
    )}

    {/* Stage Distribution */}
    {brief.stage_distribution && (
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
        <Text fontSize="sm" fontWeight="semibold" mb={2}>Stage Distribution</Text>
        <HStack gap={2} flexWrap="wrap">
          {Object.entries(brief.stage_distribution).map(([stage, count]: [string, any]) => (
            <HStack key={stage} gap={1}>
              <StageBadge stage={stage} />
              <Text fontSize="xs">{count}</Text>
            </HStack>
          ))}
        </HStack>
      </Box>
    )}
  </Stack>
);


const MonthlyReviewView: React.FC<{ brief: any }> = ({ brief }) => (
  <Stack gap={4}>
    <SimpleGrid columns={{ base: 2, md: 4 }} gap={3}>
      <StatCard label="Period" value={`${brief.period_start} to ${brief.as_of}`} />
      <StatCard label="Regime Transitions" value={String(brief.regime_transitions ?? 0)} />
      <StatCard label="Avg 20D Perf" value={fmtPct(brief.performance_summary?.avg_20d)} />
      <StatCard label="Median 20D Perf" value={fmtPct(brief.performance_summary?.median_20d)} />
    </SimpleGrid>

    {/* Regime History */}
    {brief.regime_history?.length > 0 && (
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
        <Text fontSize="sm" fontWeight="semibold" mb={2}>Regime History (30d)</Text>
        <HStack gap={0} flexWrap="wrap">
          {brief.regime_history.map((r: any, i: number) => (
            <Box
              key={i}
              w="8px"
              h="24px"
              bg={REGIME_HEX[r.state] || '#64748B'}
              title={`${r.date}: ${r.state} (${r.score})`}
              borderRadius="1px"
            />
          ))}
        </HStack>
      </Box>
    )}

    {/* Best / Worst */}
    {brief.performance_summary && (
      <SimpleGrid columns={{ base: 1, md: 2 }} gap={4}>
        <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
          <Text fontSize="sm" fontWeight="semibold" color="green.500" mb={2}>Top 5 Performers (20d)</Text>
          <Stack gap={1}>
            {(brief.performance_summary.best || []).map((s: any) => (
              <HStack key={s.symbol} justify="space-between" fontSize="xs" py={1}>
                <Text fontWeight="semibold">{s.symbol}</Text>
                <Text {...DATA_MONO} color="green.500">{fmtPct(s.perf_20d)}</Text>
              </HStack>
            ))}
          </Stack>
        </Box>
        <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
          <Text fontSize="sm" fontWeight="semibold" color="red.500" mb={2}>Bottom 5 Performers (20d)</Text>
          <Stack gap={1}>
            {(brief.performance_summary.worst || []).map((s: any) => (
              <HStack key={s.symbol} justify="space-between" fontSize="xs" py={1}>
                <Text fontWeight="semibold">{s.symbol}</Text>
                <Text {...DATA_MONO} color="red.500">{fmtPct(s.perf_20d)}</Text>
              </HStack>
            ))}
          </Stack>
        </Box>
      </SimpleGrid>
    )}
  </Stack>
);


const PickList: React.FC<{ title: string; items: any[]; colorPalette: string }> = ({ title, items, colorPalette }) => (
  <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
    <HStack justify="space-between" mb={2}>
      <Text fontSize="sm" fontWeight="semibold">{title}</Text>
      <Badge variant="subtle" colorPalette={colorPalette} size="sm">{items?.length ?? 0}</Badge>
    </HStack>
    {!items?.length ? (
      <Text fontSize="xs" color="fg.muted">None</Text>
    ) : (
      <Stack gap={1}>
        {items.map((p: any, i: number) => (
          <HStack key={`${p.symbol}-${i}`} justify="space-between" fontSize="xs">
            <Text fontWeight="semibold">{p.symbol}</Text>
            <HStack gap={1}>
              <StageBadge stage={p.stage || '—'} />
              {p.scan_tier && <Text color="fg.muted">{p.scan_tier}</Text>}
            </HStack>
          </HStack>
        ))}
      </Stack>
    )}
  </Box>
);


export default MarketIntelligence;
