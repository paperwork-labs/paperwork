import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Text,
  VStack,
  HStack,
  Badge,
  Button,
  Input,
  SimpleGrid,
  CardRoot,
  CardBody,
  Tabs,
} from '@chakra-ui/react';
import { FiPlay, FiPause, FiEdit2, FiSave, FiArrowLeft } from 'react-icons/fi';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Page, PageHeader } from '../components/ui/Page';
import { EntryExitRules } from '../components/strategy/RuleDisplay';
import BacktestResults from '../components/strategy/BacktestResults';
import api from '../services/api';
import { formatMoney } from '../utils/format';
import type {
  Strategy,
  StrategyStatus,
  BacktestResult,
  ConditionGroupData,
} from '../types/strategy';

function extractData<T>(resp: { data?: { data?: T } }): T {
  return (resp?.data as { data?: T })?.data ?? (resp?.data as T);
}

const STATUS_COLORS: Record<StrategyStatus, string> = {
  active: 'green',
  paused: 'yellow',
  draft: 'gray',
  stopped: 'red',
  archived: 'red',
};

export default function StrategyDetail() {
  const { strategyId } = useParams<{ strategyId: string }>();
  const navigate = useNavigate();
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [saving, setSaving] = useState(false);

  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [btStartDate, setBtStartDate] = useState('2024-01-01');
  const [btEndDate, setBtEndDate] = useState('2025-01-01');
  const [btCapital, setBtCapital] = useState(100000);

  const [signals, setSignals] = useState<any[]>([]);
  const [signalsLoading, setSignalsLoading] = useState(false);

  useEffect(() => {
    if (!strategyId) return;
    (async () => {
      try {
        const resp = await api.get(`/strategies/${strategyId}`);
        const data = extractData<Strategy>(resp);
        setStrategy(data);
        setEditName(data?.name ?? '');
        setEditDesc(data?.description ?? '');
      } catch {
        toast.error('Failed to load strategy');
      } finally {
        setLoading(false);
      }
    })();
  }, [strategyId]);

  const handleSave = useCallback(async () => {
    if (!strategy) return;
    setSaving(true);
    try {
      const resp = await api.put(`/strategies/${strategy.id}`, {
        name: editName,
        description: editDesc,
      });
      setStrategy(extractData<Strategy>(resp));
      setEditing(false);
      toast.success('Strategy updated');
    } catch {
      toast.error('Failed to update');
    } finally {
      setSaving(false);
    }
  }, [strategy, editName, editDesc]);

  const handleStatusChange = useCallback(async (newStatus: string) => {
    if (!strategy) return;
    try {
      const resp = await api.put(`/strategies/${strategy.id}`, { status: newStatus });
      setStrategy(extractData<Strategy>(resp));
      toast.success(`Strategy ${newStatus}`);
    } catch {
      toast.error('Failed to update status');
    }
  }, [strategy]);

  const runBacktest = useCallback(async () => {
    if (!strategy) return;
    setBacktestLoading(true);
    setBacktestResult(null);
    try {
      const resp = await api.post(`/strategies/${strategy.id}/backtest`, {
        start_date: btStartDate,
        end_date: btEndDate,
        initial_capital: btCapital,
        position_size_pct: Number(strategy.position_size_pct ?? 5),
      });
      setBacktestResult(extractData<BacktestResult>(resp));
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Backtest failed');
    } finally {
      setBacktestLoading(false);
    }
  }, [strategy, btStartDate, btEndDate, btCapital]);

  const runEvaluate = useCallback(async () => {
    if (!strategy) return;
    const params = strategy.parameters ?? {};
    const entryRules = params.entry_rules as ConditionGroupData | undefined;
    if (!entryRules) {
      toast.error('No entry rules configured');
      return;
    }
    setSignalsLoading(true);
    try {
      const resp = await api.post(`/strategies/${strategy.id}/evaluate`, {
        rules: entryRules,
      });
      const data = extractData<{ signals: any[] }>(resp);
      setSignals(data?.signals ?? []);
    } catch {
      toast.error('Evaluation failed');
    } finally {
      setSignalsLoading(false);
    }
  }, [strategy]);

  if (loading) {
    return (
      <Page>
        <Text color="fg.muted">Loading strategy...</Text>
      </Page>
    );
  }

  if (!strategy) {
    return (
      <Page>
        <Text color="fg.error">Strategy not found</Text>
        <Button mt={4} onClick={() => navigate('/strategies')}>Back to Strategies</Button>
      </Page>
    );
  }

  const params = strategy.parameters ?? {};
  const entryRules = params.entry_rules as ConditionGroupData | undefined;
  const exitRules = params.exit_rules as ConditionGroupData | undefined;

  return (
    <Page>
      <HStack mb={4}>
        <Button size="sm" variant="ghost" onClick={() => navigate('/strategies')}>
          <FiArrowLeft /> Back
        </Button>
      </HStack>

      <PageHeader
        title={editing ? '' : strategy.name}
        subtitle={editing ? '' : (strategy.description || 'No description')}
        actions={
          <HStack gap={2}>
            {strategy.status === 'draft' && (
              <Button size="sm" colorPalette="green" onClick={() => handleStatusChange('active')}>
                <FiPlay /> Activate
              </Button>
            )}
            {strategy.status === 'active' && (
              <Button size="sm" colorPalette="yellow" onClick={() => handleStatusChange('paused')}>
                <FiPause /> Pause
              </Button>
            )}
            {strategy.status === 'paused' && (
              <Button size="sm" colorPalette="green" onClick={() => handleStatusChange('active')}>
                <FiPlay /> Resume
              </Button>
            )}
            <Badge colorPalette={STATUS_COLORS[strategy.status] ?? 'gray'} variant="subtle" size="lg">
              {strategy.status}
            </Badge>
          </HStack>
        }
      />

      <Tabs.Root value={activeTab} onValueChange={(d) => setActiveTab(d.value)} mt={4}>
        <Tabs.List>
          <Tabs.Trigger value="overview">Overview</Tabs.Trigger>
          <Tabs.Trigger value="rules">Rules</Tabs.Trigger>
          <Tabs.Trigger value="backtest">Backtest</Tabs.Trigger>
          <Tabs.Trigger value="signals">Signals</Tabs.Trigger>
        </Tabs.List>

        <Box mt={4}>
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <VStack align="stretch" gap={4}>
              {editing ? (
                <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                  <CardBody>
                    <VStack align="stretch" gap={3}>
                      <Box>
                        <Text fontSize="sm" fontWeight="semibold" mb={1}>Name</Text>
                        <Input value={editName} onChange={(e) => setEditName(e.target.value)} />
                      </Box>
                      <Box>
                        <Text fontSize="sm" fontWeight="semibold" mb={1}>Description</Text>
                        <Input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
                      </Box>
                      <HStack>
                        <Button size="sm" colorPalette="blue" loading={saving} onClick={handleSave}>
                          <FiSave /> Save
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setEditing(false)}>Cancel</Button>
                      </HStack>
                    </VStack>
                  </CardBody>
                </CardRoot>
              ) : (
                <HStack>
                  <Button size="xs" variant="ghost" onClick={() => setEditing(true)}>
                    <FiEdit2 /> Edit
                  </Button>
                </HStack>
              )}

              <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={4}>
                <InfoCard label="Strategy Type" value={strategy.strategy_type} />
                <InfoCard label="Execution Mode" value={strategy.execution_mode ?? 'paper'} />
                <InfoCard label="Position Size" value={`${strategy.position_size_pct ?? '—'}%`} />
                <InfoCard label="Max Positions" value={String(strategy.max_positions ?? '—')} />
                <InfoCard label="Stop Loss" value={strategy.stop_loss_pct ? `${strategy.stop_loss_pct}%` : '—'} />
                <InfoCard label="Take Profit" value={strategy.take_profit_pct ? `${strategy.take_profit_pct}%` : '—'} />
                <InfoCard label="Run Frequency" value={strategy.run_frequency ?? 'on_demand'} />
                <InfoCard label="Created" value={new Date(strategy.created_at).toLocaleDateString()} />
                <InfoCard label="Updated" value={new Date(strategy.updated_at).toLocaleDateString()} />
              </SimpleGrid>
            </VStack>
          )}

          {/* Rules Tab */}
          {activeTab === 'rules' && (
            <VStack align="stretch" gap={4}>
              <EntryExitRules entryRules={entryRules} exitRules={exitRules} />
              {!entryRules && !exitRules && (
                <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                  <CardBody>
                    <Text color="fg.muted" fontSize="sm">
                      No rules configured yet. Rules are stored in the strategy parameters as entry_rules and exit_rules condition groups.
                    </Text>
                  </CardBody>
                </CardRoot>
              )}
            </VStack>
          )}

          {/* Backtest Tab */}
          {activeTab === 'backtest' && (
            <VStack align="stretch" gap={4}>
              <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                <CardBody>
                  <VStack align="stretch" gap={3}>
                    <Text fontWeight="semibold">Backtest Configuration</Text>
                    <SimpleGrid columns={{ base: 1, md: 3 }} gap={3}>
                      <Box>
                        <Text fontSize="xs" color="fg.muted" mb={1}>Start Date</Text>
                        <Input type="date" value={btStartDate} onChange={(e) => setBtStartDate(e.target.value)} />
                      </Box>
                      <Box>
                        <Text fontSize="xs" color="fg.muted" mb={1}>End Date</Text>
                        <Input type="date" value={btEndDate} onChange={(e) => setBtEndDate(e.target.value)} />
                      </Box>
                      <Box>
                        <Text fontSize="xs" color="fg.muted" mb={1}>Initial Capital</Text>
                        <Input
                          type="number"
                          value={btCapital}
                          onChange={(e) => setBtCapital(Number(e.target.value) || 100000)}
                        />
                      </Box>
                    </SimpleGrid>
                    <Button
                      size="sm"
                      colorPalette="blue"
                      loading={backtestLoading}
                      disabled={!entryRules || !exitRules}
                      onClick={runBacktest}
                    >
                      Run Backtest
                    </Button>
                    {(!entryRules || !exitRules) && (
                      <Text fontSize="xs" color="fg.warning">
                        Strategy must have both entry and exit rules to run a backtest.
                      </Text>
                    )}
                  </VStack>
                </CardBody>
              </CardRoot>
              {backtestResult && <BacktestResults result={backtestResult} />}
            </VStack>
          )}

          {/* Signals Tab */}
          {activeTab === 'signals' && (
            <VStack align="stretch" gap={4}>
              <HStack>
                <Button
                  size="sm"
                  colorPalette="blue"
                  loading={signalsLoading}
                  disabled={!entryRules}
                  onClick={runEvaluate}
                >
                  Evaluate Now
                </Button>
                <Text fontSize="xs" color="fg.muted">
                  Runs entry rules against current market snapshots
                </Text>
              </HStack>
              {signals.length > 0 ? (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={3}>
                  {signals.map((sig: any, i: number) => (
                    <CardRoot key={i} bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                      <CardBody p={3}>
                        <HStack justify="space-between" mb={1}>
                          <Text fontWeight="semibold">{sig.symbol}</Text>
                          <Badge colorPalette={sig.action === 'buy' ? 'green' : 'red'} variant="subtle">
                            {sig.action}
                          </Badge>
                        </HStack>
                        <Text fontSize="xs" color="fg.muted">
                          Strength: {sig.strength ?? '—'}
                        </Text>
                      </CardBody>
                    </CardRoot>
                  ))}
                </SimpleGrid>
              ) : (
                <Text color="fg.muted" fontSize="sm">
                  {signalsLoading ? 'Evaluating...' : 'No signals yet. Click "Evaluate Now" to scan the market.'}
                </Text>
              )}
            </VStack>
          )}
        </Box>
      </Tabs.Root>
    </Page>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
      <CardBody p={3}>
        <Text fontSize="xs" color="fg.muted">{label}</Text>
        <Text fontSize="md" fontWeight="semibold">{value}</Text>
      </CardBody>
    </CardRoot>
  );
}
