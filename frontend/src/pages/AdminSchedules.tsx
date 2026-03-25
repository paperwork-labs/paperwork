import React from 'react';
import {
  Box,
  Button,
  Heading,
  HStack,
  Text,
  Badge,
  Input,
  IconButton,
  TooltipRoot,
  TooltipTrigger,
  TooltipPositioner,
  TooltipContent,
  DialogRoot,
  DialogBackdrop,
  DialogPositioner,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogTitle,
  Textarea,
} from '@chakra-ui/react';
import toast from 'react-hot-toast';
import api from '../services/api';
import FormField from '../components/ui/FormField';
import {
  FiPlay,
  FiPause,
  FiTrash2,
  FiRotateCw,
  FiEdit2,
  FiCheck,
  FiX,
  FiUploadCloud,
  FiClock,
} from 'react-icons/fi';
import SortableTable, { type Column } from '../components/SortableTable';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { formatDateTime, formatRelativeTime } from '../utils/format';

interface Schedule {
  id: string;
  display_name: string;
  group: string;
  task: string;
  description?: string;
  cron: string;
  timezone: string;
  args: any[];
  kwargs: Record<string, any>;
  enabled: boolean;
  timeout_s: number;
  singleflight: boolean;
  render_service_id?: string;
  render_synced_at?: string;
  render_sync_error?: string;
  created_at?: string;
  updated_at?: string;
  created_by?: string;
  last_run?: { task_name: string; status: string; started_at?: string; finished_at?: string };
}

interface AuditEntry {
  id: number;
  schedule_id: string;
  action: string;
  actor: string;
  changes: Record<string, any> | null;
  timestamp: string;
}

const shortTask = (task: string): string => {
  if (!task) return '—';
  const parts = task.split('.');
  return parts[parts.length - 1];
};

const formatCronFriendly = (cron: string, tz: string) => {
  const parts = String(cron || '').trim().split(/\s+/);
  if (parts.length !== 5) return cron || '—';
  const [min, hour, dom, mon, dow] = parts;
  const pad = (v: string) => v.padStart(2, '0');
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const parseDow = (value: string) => {
    if (value === '*') return 'daily';
    const list = value.split(',').map((d) => days[Number(d)] || d);
    return list.join(', ');
  };
  if (min !== '*' && hour === '*' && dom === '*' && mon === '*' && dow === '*')
    return `Every hour at :${pad(min)} ${tz}`;
  if (min !== '*' && hour !== '*' && dom === '*' && mon === '*' && dow === '*')
    return `Daily at ${pad(hour)}:${pad(min)} ${tz}`;
  if (min !== '*' && hour !== '*' && dom === '*' && mon === '*' && dow !== '*')
    return `${parseDow(dow)} at ${pad(hour)}:${pad(min)} ${tz}`;
  if (min !== '*' && hour !== '*' && dom !== '*' && mon === '*' && dow === '*')
    return `Monthly day ${dom} at ${pad(hour)}:${pad(min)} ${tz}`;
  return cron;
};

const ACTION_PALETTE: Record<string, string> = {
  created: 'green',
  updated: 'blue',
  paused: 'orange',
  resumed: 'teal',
  deleted: 'red',
};

const SyncDot: React.FC<{ s: Schedule }> = ({ s }) => {
  const color = s.render_sync_error ? 'status.danger' : s.render_synced_at ? 'status.success' : 'fg.subtle';
  const label = s.render_sync_error
    ? `Sync error: ${s.render_sync_error}`
    : s.render_synced_at
      ? `Synced ${formatRelativeTime(s.render_synced_at)}`
      : 'Not yet synced to Render';
  return (
    <TooltipRoot>
      <TooltipTrigger asChild>
        <Box as="span" w="7px" h="7px" borderRadius="full" bg={color} display="inline-block" flexShrink={0} />
      </TooltipTrigger>
      <TooltipPositioner>
        <TooltipContent maxW="300px">{label}</TooltipContent>
      </TooltipPositioner>
    </TooltipRoot>
  );
};

const GROUP_LABELS: Record<string, string> = {
  market_data: 'Market Data',
  accounts: 'Accounts',
  maintenance: 'Maintenance',
};

const ChangeSummary: React.FC<{ changes: Record<string, any> | null; action: string }> = ({ changes, action }) => {
  if (!changes || typeof changes !== 'object') {
    return <Text fontSize="12px" color="fg.muted" fontStyle="italic">{action}</Text>;
  }
  if (action === 'created' || action === 'deleted') {
    const task = changes.task ? shortTask(changes.task) : '';
    const cron = changes.cron || '';
    return (
      <Text fontSize="12px" color="fg.muted" truncate maxW="400px">
        {task}{cron ? ` (${cron})` : ''}
      </Text>
    );
  }
  const fields = Object.entries(changes);
  if (fields.length === 0) return <Text fontSize="12px" color="fg.muted">no changes</Text>;
  return (
    <Box>
      {fields.map(([key, val]) => (
        <Text key={key} fontSize="11px" color="fg.muted" truncate maxW="400px">
          <Text as="span" fontWeight="medium" color="fg.default">{key}</Text>
          {': '}
          <Text as="span" textDecoration="line-through" opacity={0.5}>{String(val?.old ?? '—')}</Text>
          {' → '}
          <Text as="span">{String(val?.new ?? '—')}</Text>
        </Text>
      ))}
    </Box>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const AdminSchedules: React.FC = () => {
  const { timezone } = useUserPreferences();
  const [loading, setLoading] = React.useState(false);
  const [syncing, setSyncing] = React.useState(false);
  const [schedules, setSchedules] = React.useState<Schedule[]>([]);
  const [renderSyncEnabled, setRenderSyncEnabled] = React.useState(false);
  const [nextRuns, setNextRuns] = React.useState<Record<string, string | null>>({});

  const [view, setView] = React.useState<'schedules' | 'history'>('schedules');
  const [history, setHistory] = React.useState<AuditEntry[]>([]);
  const [historyLoading, setHistoryLoading] = React.useState(false);

  const [createOpen, setCreateOpen] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [catalog, setCatalog] = React.useState<any[]>([]);
  const [form, setForm] = React.useState({
    id: '', display_name: '', task: '', cron: '0 * * * *', timezone: 'UTC',
    group: 'market_data', description: '',
  });

  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [editCron, setEditCron] = React.useState('');
  const [deleteTargetId, setDeleteTargetId] = React.useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get('/admin/schedules');
      const data = r.data || {};
      setSchedules(data.schedules || []);
      setRenderSyncEnabled(data.render_sync_enabled || false);

      const items = (data.schedules || []) as Schedule[];
      if (items.length) {
        const previews = await Promise.all(
          items.map(async (s) => {
            const cron = String(s?.cron || '').trim();
            const tz = String(s?.timezone || 'UTC').trim();
            if (!cron) return { id: s.id, next: null };
            try {
              const res = await api.get('/admin/schedules/preview', { params: { cron, timezone: tz, count: 1 } });
              const next = Array.isArray(res?.data?.next_runs_utc) ? res.data.next_runs_utc[0] : null;
              return { id: s.id, next: next || null };
            } catch {
              return { id: s.id, next: null };
            }
          }),
        );
        const mapped: Record<string, string | null> = {};
        previews.forEach((p) => { if (p.id) mapped[p.id] = p.next; });
        setNextRuns(mapped);
      } else {
        setNextRuns({});
      }
    } catch (err: any) {
      toast.error(err?.message || 'Failed to load schedules');
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const r = await api.get('/admin/schedules/history', { params: { limit: 100 } });
      setHistory(r.data?.history || []);
    } catch (err: any) {
      toast.error(err?.message || 'Failed to load history');
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadCatalog = async () => {
    try {
      const r = await api.get('/admin/tasks/catalog');
      const groups = r.data?.catalog || {};
      const flat: any[] = [];
      Object.values(groups).forEach((items: any) => {
        if (Array.isArray(items)) flat.push(...items);
      });
      setCatalog(flat);
    } catch { /* ignore */ }
  };

  const syncToRender = async () => {
    setSyncing(true);
    try {
      const r = await api.post('/admin/schedules/sync');
      const sync = r.data?.sync || {};
      toast.success(`Sync complete: ${sync.created || 0} created, ${sync.updated || 0} updated, ${sync.deleted || 0} deleted, ${sync.errors || 0} errors`);
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const create = async () => {
    if (creating) return;
    if (!form.id.trim() || !form.task.trim() || !form.cron.trim()) {
      toast.error('ID, task, and cron are required');
      return;
    }
    setCreating(true);
    try {
      await api.post('/admin/schedules', {
        id: form.id.trim(),
        display_name: form.display_name.trim() || form.id.trim(),
        task: form.task.trim(),
        cron: form.cron.trim(),
        timezone: form.timezone.trim(),
        group: form.group.trim(),
        description: form.description.trim() || undefined,
        args: [],
        kwargs: {},
        enabled: true,
      });
      toast.success('Schedule created');
      setCreateOpen(false);
      setForm({ id: '', display_name: '', task: '', cron: '0 * * * *', timezone: 'UTC', group: 'market_data', description: '' });
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to create');
    } finally {
      setCreating(false);
    }
  };

  const runNow = async (task: string) => {
    try {
      await api.post('/admin/schedules/run-now', null, { params: { task } });
      toast.success('Task enqueued');
      setTimeout(load, 2000);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to enqueue');
    }
  };

  const pause = async (id: string) => {
    try {
      await api.post(`/admin/schedules/${encodeURIComponent(id)}/pause`);
      toast.success('Paused');
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to pause');
    }
  };

  const resume = async (id: string) => {
    try {
      await api.post(`/admin/schedules/${encodeURIComponent(id)}/resume`);
      toast.success('Resumed');
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to resume');
    }
  };

  const confirmDelete = async () => {
    if (!deleteTargetId) return;
    const id = deleteTargetId;
    try {
      await api.delete(`/admin/schedules/${encodeURIComponent(id)}`);
      toast.success('Deleted');
      setDeleteTargetId(null);
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to delete');
    }
  };

  const saveEditCron = async (id: string) => {
    try {
      await api.put(`/admin/schedules/${encodeURIComponent(id)}`, { cron: editCron.trim() });
      toast.success('Schedule updated');
      setEditingId(null);
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to update');
    }
  };

  React.useEffect(() => { load(); loadCatalog(); }, []);

  React.useEffect(() => {
    if (view === 'history') loadHistory();
  }, [view]);

  // ---------------------------------------------------------------------------
  // Schedule columns
  // ---------------------------------------------------------------------------
  const columns: Column<Schedule>[] = [
    {
      key: 'name',
      header: 'Job',
      accessor: (s) => s.display_name || s.id,
      sortable: true,
      sortType: 'string',
      render: (_v, s) => {
        const statusColor = s.enabled ? 'status.success' : 'status.warning';
        const statusLabel = s.enabled ? 'Enabled' : 'Paused';
        return (
          <Box py="3px">
            <HStack gap="6px" align="center">
              <TooltipRoot>
                <TooltipTrigger asChild>
                  <Box as="span" w="8px" h="8px" borderRadius="full" bg={statusColor} flexShrink={0} />
                </TooltipTrigger>
                <TooltipPositioner><TooltipContent>{statusLabel}</TooltipContent></TooltipPositioner>
              </TooltipRoot>
              <Text fontWeight="semibold" fontSize="13px" lineHeight="1.3">{s.display_name || s.id}</Text>
              <SyncDot s={s} />
            </HStack>
            {s.description && (
              <Text fontSize="11px" color="fg.muted" pl="14px" mt="1px" truncate maxW="280px">
                {s.description}
              </Text>
            )}
            <TooltipRoot>
              <TooltipTrigger asChild>
                <Text fontFamily="mono" fontSize="10px" color="fg.subtle" pl="14px" mt="1px" truncate maxW="220px">
                  {shortTask(s.task)}
                </Text>
              </TooltipTrigger>
              <TooltipPositioner>
                <TooltipContent>{s.task}</TooltipContent>
              </TooltipPositioner>
            </TooltipRoot>
          </Box>
        );
      },
      width: '320px',
    },
    {
      key: 'schedule',
      header: 'Schedule',
      accessor: (s) => s.cron || '',
      sortable: true,
      sortType: 'string',
      render: (_v, s) => {
        const isEditing = editingId === s.id;
        if (isEditing) {
          return (
            <HStack gap={1}>
              <Input
                size="xs"
                fontFamily="mono"
                value={editCron}
                onChange={(e) => setEditCron(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (e.metaKey || e.ctrlKey) {
                      saveEditCron(s.id);
                    } else {
                      toast('Use Cmd/Ctrl + Enter to save');
                    }
                  }
                  if (e.key === 'Escape') setEditingId(null);
                }}
                w="140px"
                autoFocus
              />
              <IconButton aria-label="Save" size="xs" variant="ghost" onClick={() => saveEditCron(s.id)}><FiCheck /></IconButton>
              <IconButton aria-label="Cancel" size="xs" variant="ghost" onClick={() => setEditingId(null)}><FiX /></IconButton>
            </HStack>
          );
        }
        const cron = s.cron || '';
        const tz = s.timezone || 'UTC';
        const friendly = cron ? formatCronFriendly(cron, tz) : '—';
        const nextUtc = nextRuns[s.id];
        const nextLocal = nextUtc ? formatDateTime(nextUtc, timezone) : null;
        return (
          <Box
            cursor="pointer"
            onClick={() => { setEditingId(s.id); setEditCron(s.cron); }}
            _hover={{ bg: 'bg.subtle' }}
            borderRadius="md"
            px={1}
          >
            <HStack gap={1}>
              <Text fontSize="12px" fontWeight="medium">{friendly}</Text>
              <FiEdit2 size={10} style={{ opacity: 0.4 }} />
            </HStack>
            {cron && <Text fontFamily="mono" fontSize="11px" color="fg.muted">{cron}</Text>}
            {nextLocal && <Text fontSize="11px" color="fg.subtle">Next: {nextLocal}</Text>}
          </Box>
        );
      },
    },
    {
      key: 'last_run',
      header: 'Last Run',
      accessor: (s) => s.last_run?.started_at || '',
      sortable: true,
      sortType: 'string',
      render: (_v, s) => {
        const jobRun = s.last_run;
        const ts = jobRun?.started_at;
        const jobStatus = jobRun?.status;
        const statusPalette = jobStatus === 'ok' ? 'green' : jobStatus === 'error' ? 'red' : 'gray';
        return (
          <Box>
            <TooltipRoot>
              <TooltipTrigger asChild>
                <Text fontSize="12px" color="fg.default">{formatRelativeTime(ts)}</Text>
              </TooltipTrigger>
              {ts && (
                <TooltipPositioner>
                  <TooltipContent>{formatDateTime(ts, timezone)}</TooltipContent>
                </TooltipPositioner>
              )}
            </TooltipRoot>
            {jobStatus && (
              <Badge colorPalette={statusPalette} size="sm" variant="subtle" mt="2px">{jobStatus}</Badge>
            )}
          </Box>
        );
      },
      width: '120px',
    },
    {
      key: 'group',
      header: 'Group',
      accessor: (s) => s.group || '',
      sortable: true,
      sortType: 'string',
      render: (v) => {
        const raw = String(v);
        const label = GROUP_LABELS[raw] || raw;
        const palette = raw === 'accounts' ? 'purple' : raw === 'maintenance' ? 'orange' : 'blue';
        return <Badge size="sm" variant="subtle" colorPalette={palette}>{label}</Badge>;
      },
      width: '120px',
    },
    {
      key: 'actions',
      header: '',
      accessor: () => null,
      sortable: false,
      isNumeric: true,
      width: '130px',
      render: (_v, s) => (
        <HStack gap={1} justify="flex-end">
          <TooltipRoot>
            <TooltipTrigger asChild>
              <IconButton aria-label="Run now" size="xs" variant="outline" onClick={() => runNow(s.task)} disabled={!s.task}>
                <FiPlay />
              </IconButton>
            </TooltipTrigger>
            <TooltipPositioner><TooltipContent>Run now</TooltipContent></TooltipPositioner>
          </TooltipRoot>
          {s.enabled ? (
            <TooltipRoot>
              <TooltipTrigger asChild>
                <IconButton aria-label="Pause" size="xs" variant="outline" onClick={() => pause(s.id)}>
                  <FiPause />
                </IconButton>
              </TooltipTrigger>
              <TooltipPositioner><TooltipContent>Pause</TooltipContent></TooltipPositioner>
            </TooltipRoot>
          ) : (
            <TooltipRoot>
              <TooltipTrigger asChild>
                <IconButton aria-label="Resume" size="xs" variant="outline" onClick={() => resume(s.id)}>
                  <FiRotateCw />
                </IconButton>
              </TooltipTrigger>
              <TooltipPositioner><TooltipContent>Resume</TooltipContent></TooltipPositioner>
            </TooltipRoot>
          )}
          <TooltipRoot>
            <TooltipTrigger asChild>
                  <IconButton aria-label="Delete" size="xs" variant="outline" colorPalette="red" onClick={() => setDeleteTargetId(s.id)}>
                <FiTrash2 />
              </IconButton>
            </TooltipTrigger>
            <TooltipPositioner><TooltipContent>Delete</TooltipContent></TooltipPositioner>
          </TooltipRoot>
        </HStack>
      ),
    },
  ];

  // ---------------------------------------------------------------------------
  // History columns
  // ---------------------------------------------------------------------------
  const historyColumns: Column<AuditEntry>[] = [
    {
      key: 'timestamp',
      header: 'When',
      accessor: (e) => e.timestamp || '',
      sortable: true,
      sortType: 'string',
      render: (_v, e) => (
        <TooltipRoot>
          <TooltipTrigger asChild>
            <Text fontSize="12px">{formatRelativeTime(e.timestamp)}</Text>
          </TooltipTrigger>
          <TooltipPositioner>
            <TooltipContent>{formatDateTime(e.timestamp, timezone)}</TooltipContent>
          </TooltipPositioner>
        </TooltipRoot>
      ),
      width: '100px',
    },
    {
      key: 'action',
      header: 'Action',
      accessor: (e) => e.action,
      sortable: true,
      sortType: 'string',
      render: (_v, e) => (
        <Badge colorPalette={ACTION_PALETTE[e.action] || 'gray'} size="sm" variant="subtle">{e.action}</Badge>
      ),
      width: '90px',
    },
    {
      key: 'schedule_id',
      header: 'Schedule',
      accessor: (e) => e.schedule_id,
      sortable: true,
      sortType: 'string',
      render: (v) => <Text fontSize="12px" fontFamily="mono">{String(v)}</Text>,
      width: '200px',
    },
    {
      key: 'changes',
      header: 'Details',
      accessor: () => null,
      sortable: false,
      render: (_v, e) => <ChangeSummary changes={e.changes} action={e.action} />,
    },
    {
      key: 'actor',
      header: 'By',
      accessor: (e) => e.actor,
      sortable: true,
      sortType: 'string',
      render: (v) => <Text fontSize="12px" color="fg.muted" truncate maxW="140px">{String(v)}</Text>,
      width: '140px',
    },
  ];

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <Box px={{ base: 4, md: 6, xl: 8 }} py={2} maxW="1600px" mx="auto">
      {/* Header */}
      <HStack justify="space-between" mb={3} align="start">
        <Box>
          <HStack gap={2} align="center">
            <Heading size="md">Schedules</Heading>
            <Badge colorPalette="blue" size="sm">DB + Render</Badge>
          </HStack>
          <Text fontSize="sm" color="fg.muted" mt={1}>
            {view === 'schedules'
              ? 'Recurring background jobs. Click on a cron expression to edit it inline.'
              : 'Audit trail of all schedule changes.'}
          </Text>
        </Box>
        <HStack gap={2} flexShrink={0}>
          {/* View toggle */}
          <HStack gap={0} borderWidth="1px" borderColor="border.subtle" borderRadius="md" overflow="hidden">
            <Button
              size="sm"
              variant={view === 'schedules' ? 'solid' : 'ghost'}
              borderRadius={0}
              onClick={() => setView('schedules')}
            >
              Schedules
            </Button>
            <Button
              size="sm"
              variant={view === 'history' ? 'solid' : 'ghost'}
              borderRadius={0}
              onClick={() => setView('history')}
            >
              <FiClock style={{ marginRight: 4 }} />
              History
            </Button>
          </HStack>
          {view === 'schedules' && (
            <>
              {renderSyncEnabled && (
                <TooltipRoot>
                  <TooltipTrigger asChild>
                    <Button size="sm" variant="outline" onClick={syncToRender} loading={syncing}>
                      <FiUploadCloud style={{ marginRight: 4 }} />
                      Sync to Render
                    </Button>
                  </TooltipTrigger>
                  <TooltipPositioner>
                    <TooltipContent>Push all schedules to Render cron jobs</TooltipContent>
                  </TooltipPositioner>
                </TooltipRoot>
              )}
              <Button size="sm" variant="outline" onClick={() => { loadCatalog(); setCreateOpen(true); }}>
                New schedule
              </Button>
              <Button size="sm" onClick={load} loading={loading}>
                Reload
              </Button>
            </>
          )}
          {view === 'history' && (
            <Button size="sm" onClick={loadHistory} loading={historyLoading}>
              Reload
            </Button>
          )}
        </HStack>
      </HStack>

      {/* Content */}
      <Box w="full" borderWidth="1px" borderColor="border.subtle" borderRadius="lg" bg="bg.card" overflow="hidden" mt={1}>
        {view === 'schedules' && (
          <SortableTable
            data={schedules}
            columns={columns}
            defaultSortBy="name"
            defaultSortOrder="asc"
            size="sm"
            maxHeight="70vh"
            emptyMessage={loading ? 'Loading...' : 'No schedules found. Reload to auto-seed from catalog.'}
          />
        )}
        {view === 'history' && (
          <SortableTable
            data={history}
            columns={historyColumns}
            defaultSortBy="timestamp"
            defaultSortOrder="desc"
            size="sm"
            maxHeight="70vh"
            emptyMessage={historyLoading ? 'Loading...' : 'No history yet. Changes are recorded when you create, edit, pause, or delete schedules.'}
          />
        )}
      </Box>

      {/* Create dialog */}
      <DialogRoot open={createOpen} onOpenChange={(d) => setCreateOpen(Boolean(d.open))}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent maxW="min(720px, calc(100vw - 32px))" w="full">
            <DialogHeader>
              <DialogTitle>New Schedule</DialogTitle>
            </DialogHeader>
            <DialogBody>
              <Box display="flex" flexDirection="column" gap={4}>
                {catalog.length > 0 && (
                  <FormField label="From catalog (optional)" helperText="Pick a template to pre-fill fields">
                    <Box display="flex" gap={2} flexWrap="wrap">
                      {catalog
                        .filter((c) => !schedules.some((s) => s.id === c.id))
                        .slice(0, 6)
                        .map((c) => (
                          <Button
                            key={c.id}
                            size="xs"
                            variant="outline"
                            onClick={() =>
                              setForm({
                                id: c.id,
                                display_name: c.display_name || c.id,
                                task: c.task,
                                cron: c.default_cron || '0 * * * *',
                                timezone: c.default_tz || 'UTC',
                                group: c.group || 'market_data',
                                description: c.description || '',
                              })
                            }
                          >
                            {c.display_name || c.id}
                          </Button>
                        ))}
                    </Box>
                  </FormField>
                )}
                <FormField label="ID" helperText="Unique identifier (e.g. admin_nightly_report)">
                  <Input value={form.id} onChange={(e) => setForm((p) => ({ ...p, id: e.target.value }))} />
                </FormField>
                <FormField label="Display name">
                  <Input value={form.display_name} onChange={(e) => setForm((p) => ({ ...p, display_name: e.target.value }))} />
                </FormField>
                <FormField label="Task (dotted path)" helperText="e.g. backend.tasks.market_data_tasks.monitor_coverage_health">
                  <Input value={form.task} onChange={(e) => setForm((p) => ({ ...p, task: e.target.value }))} />
                </FormField>
                <HStack gap={4}>
                  <FormField label="Cron" helperText="m h dom mon dow">
                    <Input value={form.cron} onChange={(e) => setForm((p) => ({ ...p, cron: e.target.value }))} />
                  </FormField>
                  <FormField label="Timezone">
                    <Input value={form.timezone} onChange={(e) => setForm((p) => ({ ...p, timezone: e.target.value }))} />
                  </FormField>
                </HStack>
                <FormField label="Group">
                  <Input value={form.group} onChange={(e) => setForm((p) => ({ ...p, group: e.target.value }))} />
                </FormField>
                <FormField label="Description">
                  <Textarea value={form.description} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} rows={2} />
                </FormField>
              </Box>
            </DialogBody>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button colorScheme="brand" loading={creating} onClick={create}>Create</Button>
            </DialogFooter>
          </DialogContent>
        </DialogPositioner>
      </DialogRoot>

      {/* Delete confirmation dialog */}
      <DialogRoot open={Boolean(deleteTargetId)} onOpenChange={(d) => { if (!d.open) setDeleteTargetId(null); }}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent maxW="min(560px, calc(100vw - 32px))" w="full">
            <DialogHeader>
              <DialogTitle>Delete Schedule</DialogTitle>
            </DialogHeader>
            <DialogBody>
              <Text fontSize="sm" color="fg.default">
                Delete schedule <Text as="span" fontFamily="mono">{deleteTargetId || '—'}</Text>?
              </Text>
              <Text fontSize="sm" color="fg.muted" mt={2}>
                This also removes the linked Render cron job.
              </Text>
            </DialogBody>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setDeleteTargetId(null)}>Cancel</Button>
              <Button colorPalette="red" onClick={confirmDelete}>Delete</Button>
            </DialogFooter>
          </DialogContent>
        </DialogPositioner>
      </DialogRoot>
    </Box>
  );
};

export default AdminSchedules;
