import React from 'react';
import { Badge, Box, Heading, HStack, Spinner, Stack, Text } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';
import { marketDataApi } from '../services/api';

type DashboardPayload = {
  generated_at?: string;
  tracked_count?: number;
  snapshot_count?: number;
  coverage?: {
    status?: string;
    daily_pct?: number | null;
    m5_pct?: number | null;
    daily_stale?: number | null;
    m5_stale?: number | null;
  } | null;
  regime?: {
    up_1d_count?: number;
    down_1d_count?: number;
    flat_1d_count?: number;
    above_sma50_count?: number;
    above_sma200_count?: number;
    stage_counts?: Record<string, number>;
  };
  leaders?: Array<any>;
  setups?: {
    breakout_candidates?: Array<any>;
    pullback_candidates?: Array<any>;
    rs_leaders?: Array<any>;
  };
  sector_momentum?: Array<any>;
  action_queue?: Array<any>;
};

const asNumber = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

const coverageStatusLabel = (status: unknown): string => {
  if (!status) return 'unknown';
  if (typeof status === 'string') return status;
  if (typeof status === 'object' && status !== null) {
    const s = status as Record<string, unknown>;
    if (typeof s.label === 'string' && s.label.trim()) return s.label;
    if (typeof s.summary === 'string' && s.summary.trim()) return s.summary;
  }
  return 'unknown';
};

const MiniList: React.FC<{
  title: string;
  items: Array<any>;
  onOpenTracked?: () => void;
  onViewAll?: () => void;
  openTrackedTestId?: string;
  viewAllTestId?: string;
}> = ({ title, items, onOpenTracked, onViewAll, openTrackedTestId, viewAllTestId }) => (
  <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
    <HStack justify="space-between" mb={2}>
      <HStack gap={2}>
        <Text fontSize="sm" fontWeight="semibold">{title}</Text>
        {items.length > 6 ? (
          <Badge variant="subtle" fontSize="10px">{`Top 6 of ${items.length}`}</Badge>
        ) : null}
      </HStack>
      <HStack gap={3}>
        {onOpenTracked ? (
          <Text fontSize="xs" color="blue.400" cursor="pointer" onClick={onOpenTracked}>
            <span data-testid={openTrackedTestId || undefined}>Open Tracked</span>
          </Text>
        ) : null}
        {onViewAll ? (
          <Text fontSize="xs" color="blue.300" cursor="pointer" onClick={onViewAll}>
            <span data-testid={viewAllTestId || undefined}>{`View all ${items.length}`}</span>
          </Text>
        ) : null}
      </HStack>
    </HStack>
    <Stack gap={1}>
      {(items || []).slice(0, 6).map((it, idx) => (
        <HStack key={`${it?.symbol || it?.sector || idx}`} justify="space-between" fontSize="xs">
          <Text>{it?.symbol || it?.sector || '—'}</Text>
          <HStack gap={2}>
            {typeof it?.momentum_score === 'number' ? <Badge variant="subtle">Score {it.momentum_score}</Badge> : null}
            {typeof it?.perf_20d === 'number' ? <Badge variant="subtle">{it.perf_20d.toFixed(1)}% 20d</Badge> : null}
            {typeof it?.rs_mansfield_pct === 'number' ? <Badge variant="subtle">RS {it.rs_mansfield_pct.toFixed(1)}%</Badge> : null}
          </HStack>
        </HStack>
      ))}
      {(!items || items.length === 0) ? <Text fontSize="xs" color="fg.muted">No items yet.</Text> : null}
    </Stack>
  </Box>
);

const StatCard: React.FC<{ label: string; value: string; help?: string }> = ({ label, value, help }) => (
  <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
    <Text fontSize="xs" color="fg.muted">{label}</Text>
    <Text fontSize="lg" fontWeight="bold">{value}</Text>
    {help ? <Text fontSize="xs" color="fg.muted">{help}</Text> : null}
  </Box>
);

const MarketDashboard: React.FC = () => {
  const navigate = useNavigate();

  const openTracked = () => {
    navigate('/market/tracked');
  };

  const openTrackedWithSymbols = (items: Array<any>, maxSymbols?: number) => {
    const symbols = (items || [])
      .map((it) => String(it?.symbol || '').trim().toUpperCase())
      .filter(Boolean)
      .slice(0, typeof maxSymbols === 'number' ? maxSymbols : items.length);
    if (!symbols.length) {
      navigate('/market/tracked');
      return;
    }
    const params = new URLSearchParams();
    params.set('symbols', symbols.join(','));
    navigate(`/market/tracked?${params.toString()}`);
  };

  const openTrackedMomentumPreset = () => {
    navigate('/market/tracked?preset=momentum');
  };
  const [payload, setPayload] = React.useState<DashboardPayload | null>(null);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await marketDataApi.getDashboard();
        setPayload((res as DashboardPayload) || null);
        setError(null);
      } catch (e: any) {
        setPayload(null);
        setError(e?.message || 'Failed to load market dashboard');
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  if (loading) {
    return (
      <Box p={4}>
        <HStack><Spinner size="sm" /><Text>Loading market dashboard…</Text></HStack>
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={4}>
        <Heading size="md" mb={2}>Market Dashboard</Heading>
        <Text color="red.400">{error}</Text>
      </Box>
    );
  }

  const coverage = payload?.coverage || {};
  const regime = payload?.regime || {};
  const leaders = payload?.leaders || [];
  const setups = payload?.setups || {};
  const sectors = payload?.sector_momentum || [];
  const actionQueue = payload?.action_queue || [];

  const dailyPct = asNumber((coverage as any)?.daily_pct);
  const m5Pct = asNumber((coverage as any)?.m5_pct);
  const dailyStale = asNumber((coverage as any)?.daily_stale) ?? asNumber((coverage as any)?.stale_daily);
  const m5Stale = asNumber((coverage as any)?.m5_stale) ?? asNumber((coverage as any)?.stale_m5);
  const statusLabel = coverageStatusLabel((coverage as any)?.status);

  return (
    <Box p={4}>
      <Stack gap={4}>
        <HStack justify="space-between" align="end" flexWrap="wrap">
          <Box>
            <Heading size="md">Market Dashboard</Heading>
            <Text color="fg.muted" fontSize="sm">
              Momentum-first overview for tracked symbols. Use this as the daily control panel.
            </Text>
          </Box>
          <HStack gap={2}>
            <Badge variant="subtle">Tracked {payload?.tracked_count || 0}</Badge>
            <Badge variant="subtle">Snapshots {payload?.snapshot_count || 0}</Badge>
            <Badge variant="subtle">Status {statusLabel}</Badge>
          </HStack>
        </HStack>

        <Box display="grid" gridTemplateColumns={{ base: '1fr', md: 'repeat(3, 1fr)' }} gap={3}>
          <StatCard label="Daily Coverage" value={typeof dailyPct === 'number' ? `${dailyPct}%` : '—'} help={`Stale: ${dailyStale ?? '—'}`} />
          <StatCard label="5m Coverage" value={typeof m5Pct === 'number' ? `${m5Pct}%` : '—'} help={`Stale: ${m5Stale ?? '—'}`} />
          <StatCard
            label="Breadth (1d)"
            value={`${regime?.up_1d_count ?? 0} / ${regime?.down_1d_count ?? 0}`}
            help="Up / Down symbols by 1d change"
          />
        </Box>

        <Box display="grid" gridTemplateColumns={{ base: '1fr', lg: '1fr 1fr' }} gap={3}>
          <MiniList
            title="Momentum Leaders"
            items={leaders}
            onOpenTracked={openTracked}
            onViewAll={() => openTrackedWithSymbols(leaders)}
            openTrackedTestId="open-tracked-momentum-leaders"
            viewAllTestId="view-all-momentum-leaders"
          />
          <MiniList
            title="Action Queue"
            items={actionQueue}
            onOpenTracked={openTracked}
            onViewAll={() => openTrackedWithSymbols(actionQueue)}
            openTrackedTestId="open-tracked-action-queue"
            viewAllTestId="view-all-action-queue"
          />
          <MiniList
            title="Breakout Candidates"
            items={setups?.breakout_candidates || []}
            onOpenTracked={openTracked}
            onViewAll={() => openTrackedWithSymbols(setups?.breakout_candidates || [])}
            openTrackedTestId="open-tracked-breakout"
            viewAllTestId="view-all-breakout"
          />
          <MiniList
            title="Pullback In Trend"
            items={setups?.pullback_candidates || []}
            onOpenTracked={openTracked}
            onViewAll={() => openTrackedWithSymbols(setups?.pullback_candidates || [])}
            openTrackedTestId="open-tracked-pullback"
            viewAllTestId="view-all-pullback"
          />
          <MiniList
            title="RS Leaders"
            items={setups?.rs_leaders || []}
            onOpenTracked={openTracked}
            onViewAll={() => openTrackedWithSymbols(setups?.rs_leaders || [])}
            openTrackedTestId="open-tracked-rs"
            viewAllTestId="view-all-rs"
          />
          <MiniList
            title="Sector Momentum"
            items={sectors}
            onOpenTracked={openTracked}
            onViewAll={openTrackedMomentumPreset}
            openTrackedTestId="open-tracked-sector"
            viewAllTestId="view-all-sector"
          />
        </Box>
      </Stack>
    </Box>
  );
};

export default MarketDashboard;
