import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Flex,
  Text,
  Badge,
  VStack,
  HStack,
  Button,
  Collapsible,
  Skeleton,
  SimpleGrid,
  Separator,
  Input,
  Progress,
  Spinner,
} from '@chakra-ui/react';
import {
  FiChevronDown,
  FiChevronUp,
  FiRefreshCw,
  FiCheckCircle,
  FiAlertTriangle,
  FiXCircle,
  FiClock,
  FiZap,
} from 'react-icons/fi';
import toast from 'react-hot-toast';
import useAdminHealth from '../hooks/useAdminHealth';
import useCoverageSnapshot from '../hooks/useCoverageSnapshot';
import { useUserPreferences } from '../hooks/useUserPreferences';
import CoverageHealthStrip from '../components/coverage/CoverageHealthStrip';
import AdminDomainCards from '../components/admin/AdminDomainCards';
import AdminRunbook from '../components/admin/AdminRunbook';
import AdminOperatorActions from '../components/admin/AdminOperatorActions';
import { marketDataApi } from '../services/api';
import api from '../services/api';
import { REGIME_HEX } from '../constants/chart';
import { formatDate, formatRelativeTime } from '../utils/format';
import type { AdminHealthResponse, AutoFixStatusResponse, AutoFixTask } from '../types/adminHealth';

const TASK_LABELS: Record<string, string> = {
  'tasks.market_data_tasks.bootstrap_daily_coverage_tracked': 'Nightly Pipeline',
  'tasks.market_data_tasks.admin_indicators_recompute_universe': 'Indicator Recompute',
  'tasks.market_data_tasks.compute_daily_regime': 'Regime Computation',
  'tasks.market_data_tasks.admin_coverage_backfill_stale': 'Stale Coverage Repair',
  'tasks.reconciliation_tasks.reconcile_all_accounts': 'Account Reconciliation',
  'tasks.account_sync.sync_all_ibkr_accounts': 'IBKR Account Sync',
  'tasks.account_sync.sync_all_schwab_accounts': 'Schwab Account Sync',
  'tasks.strategy_tasks.evaluate_strategies': 'Strategy Evaluation',
  'tasks.intelligence_tasks.generate_daily_brief': 'Daily Brief Generation',
  'tasks.auto_ops_tasks.auto_remediate_health': 'Auto-Ops Health Remediation',
};

const friendlyTaskName = (name: string): string =>
  TASK_LABELS[name] ??
  name
    .replace(/^tasks\./, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull',
  R2: 'Cautious',
  R3: 'Chop',
  R4: 'Bear Rally',
  R5: 'Bear',
};

const STATUS_ICON: Record<string, React.ElementType> = {
  green: FiCheckCircle,
  yellow: FiAlertTriangle,
  red: FiXCircle,
};

const STATUS_COLOR: Record<string, string> = {
  green: 'status.success',
  yellow: 'status.warning',
  red: 'status.danger',
};

const estimateTradingDays = (sinceDate: string): number => {
  const from = new Date(sinceDate);
  const now = new Date();
  const years = (now.getTime() - from.getTime()) / (365.25 * 24 * 60 * 60 * 1000);
  return Math.round(years * 252);
};

interface PipelineRowProps {
  label: string;
  detail: string;
  pct: number | null;
  statusColor?: string;
  badge?: { text: string; bg: string };
}

const PipelineRow: React.FC<PipelineRowProps> = ({ label, detail, pct, statusColor, badge }) => (
  <Box>
    <HStack justify="space-between" mb={1}>
      <HStack gap={2}>
        <Text fontSize="sm" fontWeight="medium" color="fg.default">{label}</Text>
        {badge && (
          <Badge size="sm" variant="solid" style={{ backgroundColor: badge.bg, color: '#fff' }}>
            {badge.text}
          </Badge>
        )}
      </HStack>
      <Text fontSize="xs" color="fg.muted" fontFamily="mono">{detail}</Text>
    </HStack>
    {pct !== null && (
      <Progress.Root value={pct} size="xs" borderRadius="full">
        <Progress.Track bg="bg.subtle" borderRadius="full">
          <Progress.Range
            bg={statusColor || (pct >= 95 ? 'status.success' : pct >= 70 ? 'status.warning' : 'status.danger')}
            borderRadius="full"
            transition="width 500ms ease"
          />
        </Progress.Track>
      </Progress.Root>
    )}
  </Box>
);

interface PipelineStatusProps {
  health: AdminHealthResponse | null;
  loading: boolean;
  sinceDate: string;
  timezone: string;
}

const PipelineStatus: React.FC<PipelineStatusProps> = ({ health, loading, sinceDate, timezone }) => {
  if (loading) {
    return (
      <VStack align="stretch" gap={4}>
        {[1, 2, 3, 4].map((i) => (
          <Box key={i}>
            <Skeleton height="16px" width="50%" mb={2} />
            <Skeleton height="6px" width="100%" borderRadius="full" />
          </Box>
        ))}
      </VStack>
    );
  }

  if (!health) {
    return (
      <Text fontSize="sm" color="fg.muted">
        Connecting to system health...
      </Text>
    );
  }

  const dims = health.dimensions;
  const coverage = dims.coverage;
  const audit = dims.audit;
  const regime = dims.regime;
  const stageQ = dims.stage_quality;
  const jobs = dims.jobs;

  const totalTradingDays = estimateTradingDays(sinceDate);
  const dailyPct = typeof coverage.daily_pct === 'number' ? coverage.daily_pct : 0;
  const snapshotPct = typeof audit.snapshot_fill_pct === 'number' ? audit.snapshot_fill_pct : 0;
  const unknownRate = typeof stageQ.unknown_rate === 'number' ? stageQ.unknown_rate : 0;
  const indicatorPct = Math.max(0, Math.min(100, (1 - unknownRate) * 100));

  const compositeOk = coverage.status === 'green' && regime.status === 'green' && jobs.error_count === 0;
  const statusText = compositeOk
    ? `All pipelines healthy. ${jobs.ok_count} tasks completed in the last ${jobs.window_hours}h.`
    : coverage.status !== 'green'
      ? `Coverage needs attention — ${coverage.stale_daily} symbols missing latest bars. Agent will retry automatically.`
      : jobs.error_count > 0
        ? `${jobs.error_count} task failure${jobs.error_count > 1 ? 's' : ''} detected. Check agent activity below.`
        : 'Some dimensions need attention. See details below.';

  return (
    <VStack align="stretch" gap={4}>
      <PipelineRow
        label="Daily Bars"
        detail={`${coverage.tracked_count} symbols · Latest: ${coverage.expected_date || '—'} · ${dailyPct.toFixed(1)}%`}
        pct={dailyPct}
      />
      <PipelineRow
        label="Indicators"
        detail={`${indicatorPct.toFixed(0)}% classified · Unknown rate: ${(unknownRate * 100).toFixed(1)}%`}
        pct={indicatorPct}
      />
      <PipelineRow
        label="Snapshot History"
        detail={`~${totalTradingDays} trading days from ${sinceDate} · ${snapshotPct.toFixed(1)}%`}
        pct={snapshotPct}
      />
      <PipelineRow
        label="Market Regime"
        detail={regime.regime_state
          ? `Score: ${regime.composite_score?.toFixed(1) ?? '—'} · ${regime.multiplier ?? '—'}x sizing · as of ${formatDate(regime.as_of_date, timezone)}`
          : 'Not yet computed'
        }
        pct={null}
        badge={regime.regime_state ? {
          text: `${regime.regime_state} ${REGIME_LABELS[regime.regime_state] || ''}`,
          bg: REGIME_HEX[regime.regime_state] || '#64748B',
        } : undefined}
      />

      <Box pt={1} borderTop="1px solid" borderColor="border.subtle">
        <HStack gap={2} align="flex-start">
          {compositeOk ? (
            <FiCheckCircle size={14} color="var(--chakra-colors-status-success)" style={{ marginTop: 2, flexShrink: 0 }} />
          ) : (
            <FiAlertTriangle size={14} color="var(--chakra-colors-status-warning)" style={{ marginTop: 2, flexShrink: 0 }} />
          )}
          <Text fontSize="sm" color="fg.muted">
            {statusText}
          </Text>
        </HStack>
      </Box>
    </VStack>
  );
};

interface AgentActivityProps {
  taskRuns: AdminHealthResponse['task_runs'] | undefined;
}

const AgentActivity: React.FC<AgentActivityProps> = ({ taskRuns }) => {
  if (!taskRuns) return null;

  const entries = Object.entries(taskRuns)
    .filter(([, v]) => v !== null)
    .sort((a, b) => {
      const ta = a[1]?.ts ?? '';
      const tb = b[1]?.ts ?? '';
      return tb.localeCompare(ta);
    })
    .slice(0, 10);

  if (!entries.length) {
    return (
      <Text fontSize="sm" color="fg.muted">
        No recent agent activity recorded.
      </Text>
    );
  }

  return (
    <VStack align="stretch" gap={0}>
      {entries.map(([name, run]) => (
        <HStack
          key={name}
          justify="space-between"
          py={2}
          px={3}
          borderRadius="md"
          transition="background 150ms"
          _hover={{ bg: 'bg.hover' }}
        >
          <HStack gap={2.5} minW={0}>
            <FiCheckCircle size={12} color="var(--chakra-colors-status-success)" style={{ flexShrink: 0 }} />
            <Text fontSize="xs" color="fg.default" truncate>
              {friendlyTaskName(name)}
            </Text>
          </HStack>
          <Text fontSize="xs" color="fg.subtle" flexShrink={0} fontFamily="mono">
            {formatRelativeTime(run?.ts)}
          </Text>
        </HStack>
      ))}
    </VStack>
  );
};

const getDimensionHint = (key: string, dim: any): string | null => {
  if (dim.status === 'green') return null;
  switch (key) {
    case 'coverage':
      return `${dim.stale_daily} stale symbol${dim.stale_daily !== 1 ? 's' : ''} — agent retries hourly`;
    case 'stage_quality':
      return `${dim.invalid_count} invalid, ${dim.monotonicity_issues} monotonicity — recomputed nightly`;
    case 'audit':
      return 'Fill below threshold — backfill scheduled';
    case 'jobs':
      return `${dim.error_count} failure${dim.error_count !== 1 ? 's' : ''} — check activity log`;
    case 'regime':
      return dim.age_hours > 24 ? 'Regime stale — recomputed at market close' : null;
    default:
      return null;
  }
};

const SystemStatus: React.FC = () => {
  const { health, loading, refresh } = useAdminHealth();
  const { snapshot, hero: coverageHero } = useCoverageSnapshot({ fillTradingDaysWindow: 60 });
  const { timezone } = useUserPreferences();
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [sanityData, setSanityData] = useState<Record<string, unknown> | null>(null);
  const [sinceDate, setSinceDate] = useState('2021-01-01');
  const [sinceDateSaving, setSinceDateSaving] = useState(false);
  const [pollingUntil, setPollingUntil] = useState<number | null>(null);

  // Auto-fix state
  const [autoFixJobId, setAutoFixJobId] = useState<string | null>(null);
  const [autoFixStatus, setAutoFixStatus] = useState<AutoFixStatusResponse | null>(null);
  const [autoFixLoading, setAutoFixLoading] = useState(false);

  const compositeStatus = health?.composite_status ?? 'red';
  const StatusIcon = STATUS_ICON[compositeStatus] ?? FiXCircle;

  const triggerAggressivePolling = () => {
    setPollingUntil(Date.now() + 60000);
  };

  useEffect(() => {
    if (!pollingUntil) return;
    if (Date.now() > pollingUntil) {
      setPollingUntil(null);
      return;
    }
    const interval = setInterval(() => {
      if (Date.now() > pollingUntil) {
        setPollingUntil(null);
        clearInterval(interval);
      } else {
        void refresh();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [pollingUntil, refresh]);

  // Start auto-fix remediation
  const handleAutoFix = useCallback(async () => {
    setAutoFixLoading(true);
    try {
      const { data } = await marketDataApi.startAutoFix();
      if (data.status === 'healthy') {
        toast.success('All systems operational — nothing to fix!');
        setAutoFixLoading(false);
        return;
      }
      setAutoFixJobId(data.job_id);
      setAutoFixStatus({
        job_id: data.job_id,
        overall_status: 'running',
        completed_count: 0,
        total_count: data.plan.length,
        current_task: data.plan[0]?.label || null,
        plan: data.plan,
      });
      toast.success(`Agent started fixing ${data.plan.length} issue${data.plan.length !== 1 ? 's' : ''}`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to start auto-fix');
      setAutoFixLoading(false);
    }
  }, []);

  // Poll auto-fix status
  useEffect(() => {
    if (!autoFixJobId) return;

    const pollStatus = async () => {
      try {
        const { data } = await marketDataApi.getAutoFixStatus(autoFixJobId);
        setAutoFixStatus(data);

        if (data.overall_status === 'completed') {
          toast.success('Agent finished fixing all issues!');
          setAutoFixJobId(null);
          setAutoFixLoading(false);
          void refresh();
        } else if (data.overall_status === 'failed') {
          const failedTask = data.plan.find((t: AutoFixTask) => t.status === 'failed');
          toast.error(`Agent fix failed: ${failedTask?.label || 'Unknown task'}`);
          setAutoFixJobId(null);
          setAutoFixLoading(false);
          void refresh();
        }
      } catch (err) {
        console.error('Failed to poll auto-fix status:', err);
      }
    };

    void pollStatus();
    const interval = setInterval(pollStatus, 3000);
    return () => clearInterval(interval);
  }, [autoFixJobId, refresh]);

  const handleRefreshWithPolling = async () => {
    triggerAggressivePolling();
    await refresh();
  };

  const dailyFillSeries = (snapshot?.fill_by_date || []).map((r: any) => ({
    date: r.date,
    symbol_count: r.daily_filled || r.symbol_count || 0,
    pct_of_universe: r.daily_pct || r.pct_of_universe || 0,
  }));

  const snapshotFillSeries = (snapshot?.snapshot_fill_by_date || []).map((r: any) => ({
    date: r.date,
    symbol_count: r.snapshot_filled || r.symbol_count || 0,
    pct_of_universe: r.snapshot_pct || r.pct_of_universe || 0,
  }));

  const totalSymbols = coverageHero.totalSymbols || snapshot?.symbols || 0;

  const handleSinceDateUpdate = async () => {
    setSinceDateSaving(true);
    try {
      await api.post(`/market-data/admin/backfill/since-date?since_date=${encodeURIComponent(sinceDate)}`);
      toast.success(`Deep backfill queued from ${sinceDate}. This may take a while.`);
      setTimeout(() => void refresh(), 2000);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to queue backfill');
    } finally {
      setSinceDateSaving(false);
    }
  };

  const redDimCount = health
    ? Object.values(health.dimensions).filter((d) => d.status === 'red').length
    : 0;

  return (
    <VStack align="stretch" gap={6} maxW="960px" mx="auto">
      {/* Page Header */}
      <Flex align="center" justify="space-between" wrap="wrap" gap={3}>
        <HStack gap={3}>
          {loading ? (
            <Skeleton height="40px" width="280px" borderRadius="lg" />
          ) : (
            <>
              <Flex
                w={10}
                h={10}
                borderRadius="xl"
                bg="bg.subtle"
                align="center"
                justify="center"
                flexShrink={0}
              >
                <StatusIcon
                  size={20}
                  color={`var(--chakra-colors-${(STATUS_COLOR[compositeStatus] || 'fg-muted').replace('.', '-')})`}
                />
              </Flex>
              <Box>
                <Text fontWeight="semibold" fontSize="lg" fontFamily="heading" letterSpacing="-0.02em" color="fg.default">
                  System Status
                </Text>
                <Text fontSize="xs" color="fg.muted">
                  {compositeStatus === 'green'
                    ? 'All systems operational — agents are monitoring everything.'
                    : health?.composite_reason || 'Checking system health...'}
                </Text>
              </Box>
            </>
          )}
        </HStack>
        <HStack gap={2}>
          {health?.checked_at && (
            <HStack gap={1}>
              <FiClock size={12} />
              <Text fontSize="xs" color="fg.subtle">{formatRelativeTime(health.checked_at)}</Text>
            </HStack>
          )}
          {redDimCount > 0 && !autoFixJobId && (
            <Button
              size="xs"
              colorPalette="orange"
              onClick={handleAutoFix}
              disabled={autoFixLoading}
            >
              <FiZap size={12} />
              Fix All Issues ({redDimCount})
            </Button>
          )}
          <Button size="xs" variant="ghost" onClick={() => void refresh()} aria-label="Refresh" disabled={autoFixLoading}>
            <FiRefreshCw size={14} />
          </Button>
        </HStack>
      </Flex>

      {/* Agent Auto-Fix Progress */}
      {autoFixStatus && autoFixJobId && (
        <Box
          bg="linear-gradient(135deg, var(--chakra-colors-orange-900) 0%, var(--chakra-colors-bg-panel) 100%)"
          borderRadius="xl"
          border="1px solid"
          borderColor="orange.700"
          p={5}
        >
          <HStack justify="space-between" mb={4}>
            <HStack gap={3}>
              <Spinner size="sm" color="orange.400" />
              <Box>
                <Text fontSize="sm" fontWeight="semibold" color="orange.300">
                  Agent Fixing Issues
                </Text>
                <Text fontSize="xs" color="fg.muted">
                  {autoFixStatus.completed_count} of {autoFixStatus.total_count} tasks completed
                </Text>
              </Box>
            </HStack>
            <Badge colorPalette="orange" variant="subtle" size="sm">
              {Math.round((autoFixStatus.completed_count / autoFixStatus.total_count) * 100)}%
            </Badge>
          </HStack>

          <Progress.Root value={(autoFixStatus.completed_count / autoFixStatus.total_count) * 100} size="sm" borderRadius="full" mb={4}>
            <Progress.Track bg="whiteAlpha.200" borderRadius="full">
              <Progress.Range bg="orange.400" borderRadius="full" transition="width 300ms ease" />
            </Progress.Track>
          </Progress.Root>

          <VStack align="stretch" gap={2}>
            {autoFixStatus.plan.map((task, idx) => {
              const TaskIcon =
                task.status === 'completed' ? FiCheckCircle :
                task.status === 'running' ? Spinner :
                task.status === 'failed' ? FiXCircle : FiClock;
              const iconColor =
                task.status === 'completed' ? 'green.400' :
                task.status === 'running' ? 'orange.400' :
                task.status === 'failed' ? 'red.400' : 'fg.subtle';

              return (
                <HStack
                  key={task.task_name}
                  py={2}
                  px={3}
                  borderRadius="md"
                  bg={task.status === 'running' ? 'whiteAlpha.100' : 'transparent'}
                  gap={3}
                >
                  <Box color={iconColor} flexShrink={0}>
                    {task.status === 'running' ? (
                      <Spinner size="xs" color="orange.400" />
                    ) : (
                      <TaskIcon size={14} />
                    )}
                  </Box>
                  <Box flex={1} minW={0}>
                    <Text
                      fontSize="sm"
                      color={task.status === 'running' ? 'fg.default' : task.status === 'completed' ? 'fg.muted' : 'fg.subtle'}
                      fontWeight={task.status === 'running' ? 'medium' : 'normal'}
                    >
                      {task.label}
                    </Text>
                    {task.status === 'running' && (
                      <Text fontSize="2xs" color="fg.subtle">
                        {task.reason}
                      </Text>
                    )}
                    {task.error && (
                      <Text fontSize="2xs" color="red.400">
                        {task.error}
                      </Text>
                    )}
                  </Box>
                  {task.status === 'completed' && (
                    <Text fontSize="2xs" color="fg.subtle" fontFamily="mono">
                      Done
                    </Text>
                  )}
                </HStack>
              );
            })}
          </VStack>
        </Box>
      )}

      {/* Pipeline Status — the core of the page */}
      <Box bg="bg.panel" borderRadius="xl" border="1px solid" borderColor="border.subtle" p={6}>
        <HStack justify="space-between" mb={4}>
          <Text fontSize="xs" fontWeight="semibold" color="fg.subtle" letterSpacing="0.06em" textTransform="uppercase">
            Pipeline Status
          </Text>
          <HStack gap={2} align="center">
            <Text fontSize="xs" color="fg.muted">Data valid from</Text>
            <Input
              size="xs"
              type="date"
              value={sinceDate}
              onChange={(e) => setSinceDate(e.target.value)}
              w="140px"
              fontFamily="mono"
              borderColor="border.subtle"
            />
            <Button
              size="xs"
              variant="outline"
              onClick={handleSinceDateUpdate}
              disabled={sinceDateSaving}
              borderColor="border.subtle"
            >
              {sinceDateSaving ? 'Queuing...' : 'Update'}
            </Button>
          </HStack>
        </HStack>
        <PipelineStatus health={health} loading={loading} sinceDate={sinceDate} timezone={timezone} />
        <Text fontSize="xs" color="fg.subtle" mt={4}>
          Agents monitor all pipelines automatically. Coverage refreshes hourly, indicators recompute daily, regime scores at market close.
        </Text>
      </Box>

      {/* Coverage Strip */}
      {dailyFillSeries.length > 0 && (
        <Box bg="bg.panel" borderRadius="xl" border="1px solid" borderColor="border.subtle" p={6}>
          <Text fontSize="xs" fontWeight="semibold" color="fg.subtle" letterSpacing="0.06em" textTransform="uppercase" mb={2}>
            Data Coverage — Last 60 Trading Days
          </Text>
          <CoverageHealthStrip
            dailyFillSeries={dailyFillSeries}
            snapshotFillSeries={snapshotFillSeries}
            windowDays={60}
            totalSymbols={totalSymbols}
          />
        </Box>
      )}

      {/* Agent Activity + Quick Health */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} gap={4}>
        <Box bg="bg.panel" borderRadius="xl" border="1px solid" borderColor="border.subtle" p={5}>
          <Text fontSize="xs" fontWeight="semibold" color="fg.subtle" letterSpacing="0.06em" textTransform="uppercase" mb={3}>
            Agent Activity
          </Text>
          <Box maxH="280px" overflowY="auto">
            <AgentActivity taskRuns={health?.task_runs} />
          </Box>
        </Box>

        <Box bg="bg.panel" borderRadius="xl" border="1px solid" borderColor="border.subtle" p={5}>
          <Text fontSize="xs" fontWeight="semibold" color="fg.subtle" letterSpacing="0.06em" textTransform="uppercase" mb={3}>
            Health Dimensions
          </Text>
          {loading ? (
            <VStack gap={2}>
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} height="32px" width="100%" borderRadius="md" />
              ))}
            </VStack>
          ) : (
            <VStack align="stretch" gap={1.5}>
              {health &&
                Object.entries(health.dimensions).map(([key, dim]) => {
                  const status = dim.status;
                  const hint = getDimensionHint(key, dim);
                  return (
                    <Box
                      key={key}
                      py={2}
                      px={3}
                      borderRadius="lg"
                      bg="bg.muted"
                    >
                      <HStack justify="space-between">
                        <HStack gap={2}>
                          <Box
                            w="7px"
                            h="7px"
                            borderRadius="full"
                            bg={STATUS_COLOR[status] || 'fg.subtle'}
                            flexShrink={0}
                          />
                          <Text fontSize="sm" color="fg.default" fontWeight="medium">
                            {key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                          </Text>
                        </HStack>
                        <Badge
                          size="sm"
                          variant="subtle"
                          colorPalette={status === 'green' ? 'green' : 'red'}
                        >
                          {status.toUpperCase()}
                        </Badge>
                      </HStack>
                      {hint && (
                        <Text fontSize="2xs" color="fg.subtle" mt={1} ml={4}>
                          {hint}
                        </Text>
                      )}
                    </Box>
                  );
                })}
            </VStack>
          )}
        </Box>
      </SimpleGrid>

      {/* Runbook — auto-expands when red dimensions exist */}
      {redDimCount > 0 && <AdminRunbook health={health} />}

      {/* Detailed Domain Cards */}
      <Box>
        <Text fontSize="xs" fontWeight="semibold" color="fg.subtle" letterSpacing="0.06em" textTransform="uppercase" mb={2}>
          Detailed Diagnostics
        </Text>
        <AdminDomainCards health={health} />
      </Box>

      <Separator />

      {/* Operator Actions — rarely needed */}
      <Box>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setAdvancedOpen(!advancedOpen)}
          w="fit-content"
          color="fg.muted"
        >
          {advancedOpen ? <FiChevronUp /> : <FiChevronDown />}
          <Text ml={2} fontSize="sm">Operator Actions</Text>
        </Button>
        <Collapsible.Root open={advancedOpen}>
          <Collapsible.Content>
            <Box mt={3}>
              <AdminOperatorActions
                refreshCoverage={handleRefreshWithPolling}
                refreshHealth={handleRefreshWithPolling}
                sanityData={sanityData}
                setSanityData={setSanityData}
              />
            </Box>
          </Collapsible.Content>
        </Collapsible.Root>
      </Box>
    </VStack>
  );
};

export default SystemStatus;
