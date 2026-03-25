import React from 'react';
import {
  Box,
  Button,
  Heading,
  HStack,
  Text,
  Badge,
  DialogRoot,
  DialogBackdrop,
  DialogPositioner,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogTitle,
  IconButton,
  Tabs,
  Textarea,
} from '@chakra-ui/react';
import toast from 'react-hot-toast';
import api from '../services/api';
import { FiCheck, FiX, FiPlay, FiEye } from 'react-icons/fi';
import SortableTable, { type Column } from '../components/SortableTable';
import StatCard from '@/components/admin/StatCard';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { formatDateTime } from '../utils/format';

interface AgentAction {
  id: number;
  action_type: string;
  action_name: string;
  payload: Record<string, unknown> | null;
  risk_level: string;
  status: string;
  reasoning: string | null;
  context_summary: string | null;
  task_id: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  approved_at: string | null;
  executed_at: string | null;
  completed_at: string | null;
  auto_approved: boolean;
  session_id: string | null;
}

interface AgentStats {
  total_actions: number;
  pending_approval: number;
  completed: number;
  failed: number;
  auto_approved_rate: number;
  by_risk_level: Record<string, number>;
  top_actions: Record<string, number>;
}

const riskPalette = (risk: string) => {
  switch (risk) {
    case 'safe':
      return 'green';
    case 'moderate':
      return 'blue';
    case 'risky':
      return 'yellow';
    case 'critical':
      return 'red';
    default:
      return 'gray';
  }
};

const statusPalette = (status: string) => {
  switch (status) {
    case 'completed':
      return 'green';
    case 'executing':
      return 'blue';
    case 'pending_approval':
      return 'yellow';
    case 'approved':
      return 'teal';
    case 'rejected':
    case 'failed':
      return 'red';
    default:
      return 'gray';
  }
};

const AdminAgent: React.FC = () => {
  const { timezone } = useUserPreferences();
  const [loading, setLoading] = React.useState(false);
  const [pendingActions, setPendingActions] = React.useState<AgentAction[]>([]);
  const [allActions, setAllActions] = React.useState<AgentAction[]>([]);
  const [stats, setStats] = React.useState<AgentStats | null>(null);
  const [selectedAction, setSelectedAction] = React.useState<AgentAction | null>(null);
  const [detailsOpen, setDetailsOpen] = React.useState(false);
  const [runContext, setRunContext] = React.useState('');
  const [running, setRunning] = React.useState(false);
  const [approving, setApproving] = React.useState<number | null>(null);

  const loadPending = async () => {
    try {
      const r = await api.get('/admin/agent/actions/pending');
      setPendingActions(r.data || []);
    } catch (err: unknown) {
      const axiosErr = err as { message?: string };
      toast.error(axiosErr?.message || 'Failed to load pending actions');
    }
  };

  const loadAll = async () => {
    try {
      const r = await api.get('/admin/agent/actions', { params: { limit: 100 } });
      setAllActions(r.data || []);
    } catch (err: unknown) {
      const axiosErr = err as { message?: string };
      toast.error(axiosErr?.message || 'Failed to load actions');
    }
  };

  const loadStats = async () => {
    try {
      const r = await api.get('/admin/agent/stats');
      setStats(r.data || null);
    } catch (err: unknown) {
      const axiosErr = err as { message?: string };
      toast.error(axiosErr?.message || 'Failed to load stats');
    }
  };

  const loadAll3 = async () => {
    setLoading(true);
    try {
      await Promise.all([loadPending(), loadAll(), loadStats()]);
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    loadAll3();
  }, []);

  const handleApprove = async (action: AgentAction, approved: boolean) => {
    setApproving(action.id);
    try {
      await api.post(`/admin/agent/actions/${action.id}/approve`, { approved });
      toast.success(approved ? 'Action approved and dispatched' : 'Action rejected');
      await loadAll3();
    } catch (err: unknown) {
      const axiosErr = err as { message?: string };
      toast.error(axiosErr?.message || 'Failed to process approval');
    } finally {
      setApproving(null);
    }
  };

  const handleRunAgent = async () => {
    setRunning(true);
    try {
      const r = await api.post('/admin/agent/run', null, {
        params: runContext ? { context: runContext } : {},
      });
      toast.success(`Agent run completed (session: ${r.data?.session_id || 'unknown'})`);
      setRunContext('');
      await loadAll3();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(axiosErr?.response?.data?.detail || axiosErr?.message || 'Agent run failed');
    } finally {
      setRunning(false);
    }
  };

  const actionColumns: Column<AgentAction>[] = [
    {
      key: 'status',
      header: 'Status',
      accessor: (a) => a.status,
      sortable: true,
      sortType: 'string',
      render: (v) => <Badge colorPalette={statusPalette(v as string)}>{String(v)}</Badge>,
      width: '130px',
    },
    {
      key: 'risk_level',
      header: 'Risk',
      accessor: (a) => a.risk_level,
      sortable: true,
      sortType: 'string',
      render: (v) => <Badge colorPalette={riskPalette(v as string)}>{String(v)}</Badge>,
      width: '100px',
    },
    {
      key: 'action_name',
      header: 'Action',
      accessor: (a) => a.action_name,
      sortable: true,
      sortType: 'string',
      render: (v) => <Text fontSize="13px">{String(v)}</Text>,
    },
    {
      key: 'reasoning',
      header: 'Reasoning',
      accessor: (a) => a.reasoning || '',
      sortable: false,
      render: (v) => (
        <Text fontSize="12px" color="fg.muted" lineClamp={2}>
          {String(v) || '—'}
        </Text>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      accessor: (a) => a.created_at,
      sortable: true,
      sortType: 'date',
      render: (v) => (
        <Text fontSize="12px" color="fg.muted">
          {formatDateTime(v as string, timezone)}
        </Text>
      ),
      width: '180px',
    },
    {
      key: 'actions',
      header: 'Actions',
      accessor: () => null,
      sortable: false,
      isNumeric: true,
      width: '150px',
      render: (_v, a) => (
        <HStack gap={1} justify="flex-end">
          {a.status === 'pending_approval' && (
            <>
              <IconButton
                aria-label="Approve"
                size="xs"
                colorPalette="green"
                variant="ghost"
                loading={approving === a.id}
                onClick={() => handleApprove(a, true)}
              >
                <FiCheck />
              </IconButton>
              <IconButton
                aria-label="Reject"
                size="xs"
                colorPalette="red"
                variant="ghost"
                loading={approving === a.id}
                onClick={() => handleApprove(a, false)}
              >
                <FiX />
              </IconButton>
            </>
          )}
          <IconButton
            aria-label="View Details"
            size="xs"
            variant="ghost"
            onClick={() => {
              setSelectedAction(a);
              setDetailsOpen(true);
            }}
          >
            <FiEye />
          </IconButton>
        </HStack>
      ),
    },
  ];

  return (
    <Box p={0}>
      <HStack justify="space-between" mb={4}>
        <Box>
          <Heading size="md">Agent Dashboard</Heading>
          <Text fontSize="sm" color="fg.muted">
            LLM-powered auto-ops agent for intelligent system monitoring and remediation.
          </Text>
        </Box>
        <HStack gap={2}>
          <Button size="sm" onClick={loadAll3} loading={loading}>
            Reload
          </Button>
        </HStack>
      </HStack>

      <HStack gap={4} mb={6} wrap="wrap">
        <StatCard
          label="Pending Approval"
          value={stats?.pending_approval ?? '—'}
          helpText="Actions requiring review"
          color={stats?.pending_approval ? 'yellow.500' : undefined}
          variant="full"
        />
        <StatCard
          label="Total Actions"
          value={stats?.total_actions ?? '—'}
          helpText="All time"
          variant="full"
        />
        <StatCard
          label="Auto-Approved Rate"
          value={`${stats?.auto_approved_rate?.toFixed(1) ?? '—'}%`}
          helpText="Safe/moderate actions"
          variant="full"
        />
        <StatCard
          label="Failed Actions"
          value={stats?.failed ?? '—'}
          helpText="Execution errors"
          color={stats?.failed ? 'red.500' : undefined}
          variant="full"
        />
      </HStack>

      <Box
        borderWidth="1px"
        borderColor="border.subtle"
        borderRadius="lg"
        p={4}
        bg="bg.card"
        mb={6}
      >
        <Text fontWeight="semibold" mb={2}>
          Manual Agent Run
        </Text>
        <Text fontSize="sm" color="fg.muted" mb={3}>
          Trigger the LLM agent to analyze system health and propose/execute remediation actions.
        </Text>
        <HStack gap={3}>
          <Textarea
            placeholder="Optional context for the agent (e.g., 'Focus on coverage issues')"
            size="sm"
            value={runContext}
            onChange={(e) => setRunContext(e.target.value)}
            rows={2}
            flex={1}
          />
          <Button
            colorPalette="blue"
            onClick={handleRunAgent}
            loading={running}
            disabled={running}
          >
            <FiPlay />
            Run Agent
          </Button>
        </HStack>
      </Box>

      <Tabs.Root defaultValue="pending" variant="line">
        <Tabs.List mb={3}>
          <Tabs.Trigger value="pending">
            Pending Approval
            {pendingActions.length > 0 && (
              <Badge ml={2} colorPalette="yellow">
                {pendingActions.length}
              </Badge>
            )}
          </Tabs.Trigger>
          <Tabs.Trigger value="all">All Actions</Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="pending">
          <Box
            borderWidth="1px"
            borderColor="border.subtle"
            borderRadius="lg"
            bg="bg.card"
            overflow="hidden"
          >
            <SortableTable
              data={pendingActions}
              columns={actionColumns}
              defaultSortBy="created_at"
              defaultSortOrder="desc"
              size="sm"
              maxHeight="50vh"
              emptyMessage={loading ? 'Loading…' : 'No actions pending approval.'}
            />
          </Box>
        </Tabs.Content>

        <Tabs.Content value="all">
          <Box
            borderWidth="1px"
            borderColor="border.subtle"
            borderRadius="lg"
            bg="bg.card"
            overflow="hidden"
          >
            <SortableTable
              data={allActions}
              columns={actionColumns}
              defaultSortBy="created_at"
              defaultSortOrder="desc"
              size="sm"
              maxHeight="60vh"
              emptyMessage={loading ? 'Loading…' : 'No agent actions recorded yet.'}
            />
          </Box>
        </Tabs.Content>
      </Tabs.Root>

      <DialogRoot open={detailsOpen} onOpenChange={(d) => setDetailsOpen(Boolean(d.open))}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent maxW="min(760px, calc(100vw - 32px))" w="full">
            <DialogHeader>
              <DialogTitle>Action Details</DialogTitle>
            </DialogHeader>
            <DialogBody>
              {selectedAction && (
                <Box display="flex" flexDirection="column" gap={3}>
                  <HStack gap={3} flexWrap="wrap">
                    <Badge colorPalette={statusPalette(selectedAction.status)}>
                      {selectedAction.status}
                    </Badge>
                    <Badge colorPalette={riskPalette(selectedAction.risk_level)}>
                      {selectedAction.risk_level}
                    </Badge>
                    {selectedAction.auto_approved && (
                      <Badge colorPalette="teal">Auto-approved</Badge>
                    )}
                    <Text fontSize="xs" color="fg.muted">
                      Session: {selectedAction.session_id || '—'}
                    </Text>
                  </HStack>

                  <Box>
                    <Text fontSize="xs" color="fg.muted">
                      Action
                    </Text>
                    <Text fontWeight="semibold">{selectedAction.action_name}</Text>
                    <Text fontFamily="mono" fontSize="12px" color="fg.muted">
                      {selectedAction.action_type}
                    </Text>
                  </Box>

                  {selectedAction.reasoning && (
                    <Box>
                      <Text fontSize="xs" color="fg.muted" mb={1}>
                        Reasoning
                      </Text>
                      <Text fontSize="sm">{selectedAction.reasoning}</Text>
                    </Box>
                  )}

                  <Box>
                    <Text fontSize="xs" color="fg.muted" mb={1}>
                      Payload
                    </Text>
                    <Box
                      as="pre"
                      p={3}
                      borderWidth="1px"
                      borderColor="border.subtle"
                      borderRadius="lg"
                      bg="bg.muted"
                      overflow="auto"
                      fontSize="12px"
                      lineHeight="1.45"
                      maxH="150px"
                    >
                      {JSON.stringify(selectedAction.payload ?? {}, null, 2)}
                    </Box>
                  </Box>

                  {selectedAction.result && (
                    <Box>
                      <Text fontSize="xs" color="fg.muted" mb={1}>
                        Result
                      </Text>
                      <Box
                        as="pre"
                        p={3}
                        borderWidth="1px"
                        borderColor="border.subtle"
                        borderRadius="lg"
                        bg="bg.muted"
                        overflow="auto"
                        fontSize="12px"
                        lineHeight="1.45"
                        maxH="150px"
                      >
                        {JSON.stringify(selectedAction.result, null, 2)}
                      </Box>
                    </Box>
                  )}

                  {selectedAction.error && (
                    <Box>
                      <Text fontSize="xs" color="fg.muted" mb={1}>
                        Error
                      </Text>
                      <Box
                        as="pre"
                        p={3}
                        borderWidth="1px"
                        borderColor="red.subtle"
                        borderRadius="lg"
                        bg="red.subtle"
                        overflow="auto"
                        fontSize="12px"
                        lineHeight="1.45"
                        maxH="150px"
                        color="red.fg"
                      >
                        {selectedAction.error}
                      </Box>
                    </Box>
                  )}

                  <HStack gap={4} flexWrap="wrap" fontSize="xs" color="fg.muted">
                    <Text>Created: {formatDateTime(selectedAction.created_at, timezone)}</Text>
                    {selectedAction.approved_at && (
                      <Text>Approved: {formatDateTime(selectedAction.approved_at, timezone)}</Text>
                    )}
                    {selectedAction.executed_at && (
                      <Text>Executed: {formatDateTime(selectedAction.executed_at, timezone)}</Text>
                    )}
                    {selectedAction.completed_at && (
                      <Text>Completed: {formatDateTime(selectedAction.completed_at, timezone)}</Text>
                    )}
                    {selectedAction.task_id && (
                      <Text>Task ID: {selectedAction.task_id}</Text>
                    )}
                  </HStack>
                </Box>
              )}
            </DialogBody>
            <DialogFooter>
              {selectedAction?.status === 'pending_approval' && (
                <HStack gap={2}>
                  <Button
                    colorPalette="red"
                    variant="ghost"
                    onClick={() => {
                      handleApprove(selectedAction, false);
                      setDetailsOpen(false);
                    }}
                    loading={approving === selectedAction.id}
                  >
                    Reject
                  </Button>
                  <Button
                    colorPalette="green"
                    onClick={() => {
                      handleApprove(selectedAction, true);
                      setDetailsOpen(false);
                    }}
                    loading={approving === selectedAction.id}
                  >
                    Approve
                  </Button>
                </HStack>
              )}
              <Button variant="ghost" onClick={() => setDetailsOpen(false)}>
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        </DialogPositioner>
      </DialogRoot>
    </Box>
  );
};

export default AdminAgent;
