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
} from '@chakra-ui/react';
import toast from 'react-hot-toast';
import api from '../services/api';
import FormField from '../components/ui/FormField';
import { FiPlay, FiPause, FiTrash2, FiRotateCw } from 'react-icons/fi';
import SortableTable, { type Column } from '../components/SortableTable';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { formatDateTime } from '../utils/format';

const AdminSchedules: React.FC = () => {
  const { timezone } = useUserPreferences();
  const [loading, setLoading] = React.useState(false);
  const [data, setData] = React.useState<{ schedules: any[]; mode?: string } | null>(null);
  const [nextRuns, setNextRuns] = React.useState<Record<string, string | null>>({});
  const [creating, setCreating] = React.useState(false);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [form, setForm] = React.useState({ name: '', task: '', cron: '0 * * * *', timezone: 'UTC' });

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get('/admin/schedules');
      setData(r.data || null);
      const schedules = (r.data?.schedules || []) as any[];
      if (schedules.length) {
        const previews = await Promise.all(
          schedules.map(async (s) => {
            const cron = String(s?.cron || '').trim();
            const tz = String(s?.timezone || 'UTC').trim();
            if (!cron) {
              return { name: String(s?.name || ''), next: null };
            }
            try {
              const res = await api.get('/admin/schedules/preview', {
                params: { cron, timezone: tz, count: 1 },
              });
              const next = Array.isArray(res?.data?.next_runs_utc) ? res.data.next_runs_utc[0] : null;
              return { name: String(s?.name || ''), next: next || null };
            } catch {
              return { name: String(s?.name || ''), next: null };
            }
          }),
        );
        const mapped: Record<string, string | null> = {};
        previews.forEach((p) => {
          if (p.name) mapped[p.name] = p.next;
        });
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

  const create = async () => {
    if (creating) return;
    if (!form.name.trim() || !form.task.trim() || !form.cron.trim() || !form.timezone.trim()) {
      toast.error('Name, task, cron, and timezone are required');
      return;
    }
    setCreating(true);
    try {
      await api.post('/admin/schedules', {
        name: form.name.trim(),
        task: form.task.trim(),
        cron: form.cron.trim(),
        timezone: form.timezone.trim(),
        args: [],
        kwargs: {},
        enabled: true,
      });
      toast.success('Schedule created');
      setCreateOpen(false);
      setForm({ name: '', task: '', cron: '0 * * * *', timezone: 'UTC' });
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to create schedule');
    } finally {
      setCreating(false);
    }
  };

  const runNow = async (task: string) => {
    try {
      await api.post('/admin/schedules/run-now', null, { params: { task } });
      toast.success('Task enqueued');
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to enqueue task');
    }
  };

  const pause = async (name: string) => {
    try {
      await api.post('/admin/schedules/pause', null, { params: { name } });
      toast.success('Paused');
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to pause schedule');
    }
  };

  const resume = async (name: string) => {
    try {
      await api.post('/admin/schedules/resume', null, { params: { name } });
      toast.success('Resumed');
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to resume schedule');
    }
  };

  const remove = async (name: string) => {
    try {
      await api.delete(`/admin/schedules/${encodeURIComponent(name)}`);
      toast.success('Deleted');
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to delete schedule');
    }
  };

  React.useEffect(() => {
    load();
  }, []);

  const formatCronFriendly = (cron: string, tz: string, nextUtc?: string | null) => {
    const parts = String(cron || '').trim().split(/\s+/);
    if (parts.length !== 5) {
      return `Cron: ${cron || '—'}`;
    }
    const [min, hour, dom, mon, dow] = parts;
    const pad = (v: string) => v.padStart(2, '0');
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const parseDow = (value: string) => {
      if (value === '*') return 'daily';
      const list = value.split(',').map((d) => days[Number(d)] || d);
      return list.join(', ');
    };
    let base = `Cron: ${cron}`;
    if (min !== '*' && hour === '*' && dom === '*' && mon === '*' && dow === '*') {
      base = `Every hour at :${pad(min)} ${tz}`;
    } else if (min !== '*' && hour !== '*' && dom === '*' && mon === '*' && dow === '*') {
      base = `Every day at ${pad(hour)}:${pad(min)} ${tz}`;
    } else if (min !== '*' && hour !== '*' && dom === '*' && mon === '*' && dow !== '*') {
      base = `Weekly on ${parseDow(dow)} at ${pad(hour)}:${pad(min)} ${tz}`;
    } else if (min !== '*' && hour !== '*' && dom !== '*' && mon === '*' && dow === '*') {
      base = `Monthly on day ${dom} at ${pad(hour)}:${pad(min)} ${tz}`;
    }
    const nextLocal = nextUtc ? formatDateTime(nextUtc, timezone) : null;
    return nextLocal ? `${base} · Next: ${nextLocal}` : base;
  };

  const openPreset = (preset: { name: string; task: string; cron: string; timezone: string }) => {
    setForm(preset);
    setCreateOpen(true);
  };

  return (
    <Box p={0}>
      <HStack justify="space-between" mb={3}>
        <Box>
          <Heading size="md">Admin Schedules</Heading>
          <Text fontSize="sm" color="fg.muted">
            Manage Celery beat schedules (RedBeat). Create, pause/resume, run-now, and delete.
          </Text>
          <Text fontSize="xs" color="fg.muted">
            Times shown in your timezone; cron is stored in the schedule timezone.
          </Text>
          <HStack mt={2} gap={2} flexWrap="wrap">
            <Button
              size="xs"
              variant="outline"
              onClick={() =>
                openPreset({
                  name: 'admin_coverage_restore',
                  task: 'backend.tasks.market_data_tasks.bootstrap_daily_coverage_tracked',
                  cron: '0 3 * * *',
                  timezone: 'UTC',
                })
              }
            >
              Preset: Nightly Restore (Tracked) + History (5d)
            </Button>
          </HStack>
        </Box>
        <HStack gap={2}>
          <Button size="sm" variant="outline" onClick={() => setCreateOpen(true)}>
            New schedule
          </Button>
          <Button size="sm" onClick={load} loading={loading}>
            Reload
          </Button>
        </HStack>
      </HStack>

      <Box
        w="full"
        borderWidth="1px"
        borderColor="border.subtle"
        borderRadius="lg"
        bg="bg.card"
        overflow="hidden"
      >
        <SortableTable
          data={data?.schedules || []}
          columns={
            [
              {
                key: 'status',
                header: 'Status',
                accessor: (s: any) => String(s.status || (s.enabled ? 'active' : 'paused')),
                sortable: true,
                sortType: 'string',
                render: (v) => {
                  const status = String(v || '');
                  const palette = status === 'active' ? 'green' : status === 'paused' ? 'orange' : 'gray';
                  return <Badge colorPalette={palette}>{status}</Badge>;
                },
                width: '140px',
              },
              {
                key: 'name',
                header: 'Name',
                accessor: (s: any) => s.name,
                sortable: true,
                sortType: 'string',
                render: (v) => <Text fontWeight="medium">{String(v || '')}</Text>,
              },
              {
                key: 'task',
                header: 'Task',
                accessor: (s: any) => s.task,
                sortable: true,
                sortType: 'string',
                render: (v) => <Text fontFamily="mono" fontSize="12px">{String(v || '')}</Text>,
              },
              {
                key: 'cron',
                header: 'Cron',
                accessor: (s: any) => s.cron,
                sortable: true,
                sortType: 'string',
                render: (v) => <Text fontFamily="mono" fontSize="12px" color="fg.muted">{String(v || '—')}</Text>,
                width: '160px',
              },
              {
                key: 'friendly',
                header: 'Schedule (friendly)',
                accessor: (s: any) => s.cron,
                sortable: true,
                sortType: 'string',
                render: (_v, s) => (
                  <Text fontSize="12px" color="fg.muted">
                    {formatCronFriendly(String(s?.cron || ''), String(s?.timezone || 'UTC'), nextRuns[String(s?.name || '')])}
                  </Text>
                ),
              },
              {
                key: 'timezone',
                header: 'Timezone',
                accessor: (s: any) => s.timezone || 'UTC',
                sortable: true,
                sortType: 'string',
                render: (v) => <Text fontSize="12px" color="fg.muted">{String(v || 'UTC')}</Text>,
                width: '120px',
              },
              {
                key: 'actions',
                header: 'Actions',
                accessor: () => null,
                sortable: false,
                isNumeric: true,
                width: '140px',
                render: (_v, s) => {
                  const status = String(s.status || (s.enabled ? 'active' : 'paused'));
                  return (
                    <HStack gap={1} justify="flex-end">
                      <TooltipRoot>
                        <TooltipTrigger asChild>
                          <IconButton
                            aria-label="Run now"
                            size="xs"
                            variant="outline"
                            onClick={() => runNow(String(s.task || ''))}
                            disabled={!s.task}
                          >
                            <FiPlay />
                          </IconButton>
                        </TooltipTrigger>
                        <TooltipPositioner>
                          <TooltipContent>Run now</TooltipContent>
                        </TooltipPositioner>
                      </TooltipRoot>
                      {status === 'paused' ? (
                        <TooltipRoot>
                          <TooltipTrigger asChild>
                            <IconButton aria-label="Resume" size="xs" variant="outline" onClick={() => resume(String(s.name))}>
                              <FiRotateCw />
                            </IconButton>
                          </TooltipTrigger>
                          <TooltipPositioner>
                            <TooltipContent>Resume</TooltipContent>
                          </TooltipPositioner>
                        </TooltipRoot>
                      ) : (
                        <TooltipRoot>
                          <TooltipTrigger asChild>
                            <IconButton aria-label="Pause" size="xs" variant="outline" onClick={() => pause(String(s.name))}>
                              <FiPause />
                            </IconButton>
                          </TooltipTrigger>
                          <TooltipPositioner>
                            <TooltipContent>Pause</TooltipContent>
                          </TooltipPositioner>
                        </TooltipRoot>
                      )}
                      <TooltipRoot>
                        <TooltipTrigger asChild>
                          <IconButton aria-label="Delete" size="xs" variant="outline" colorPalette="red" onClick={() => remove(String(s.name))}>
                            <FiTrash2 />
                          </IconButton>
                        </TooltipTrigger>
                        <TooltipPositioner>
                          <TooltipContent>Delete</TooltipContent>
                        </TooltipPositioner>
                      </TooltipRoot>
                    </HStack>
                  );
                },
              },
            ] as Column<any>[]
          }
          defaultSortBy="name"
          defaultSortOrder="asc"
          size="sm"
          maxHeight="70vh"
          emptyMessage={loading ? 'Loading…' : 'No schedules found.'}
        />
      </Box>

      <DialogRoot open={createOpen} onOpenChange={(d) => setCreateOpen(Boolean(d.open))}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent maxW="min(720px, calc(100vw - 32px))" w="full">
            <DialogHeader>
              <DialogTitle>New schedule</DialogTitle>
            </DialogHeader>
            <DialogBody>
              <Box display="flex" flexDirection="column" gap={4}>
                <FormField label="Name" helperText="Unique identifier for the schedule.">
                  <Input value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
                </FormField>
                <FormField label="Task (dotted path)" helperText="Example: backend.tasks.market_data_tasks.monitor_coverage_health">
                  <Input value={form.task} onChange={(e) => setForm((p) => ({ ...p, task: e.target.value }))} />
                </FormField>
                <FormField label="Cron" helperText="Format: m h dom mon dow">
                  <Input value={form.cron} onChange={(e) => setForm((p) => ({ ...p, cron: e.target.value }))} />
                </FormField>
                <FormField label="Timezone">
                  <Input value={form.timezone} onChange={(e) => setForm((p) => ({ ...p, timezone: e.target.value }))} />
                </FormField>
              </Box>
            </DialogBody>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button colorScheme="brand" loading={creating} onClick={create}>
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </DialogPositioner>
      </DialogRoot>
    </Box>
  );
};

export default AdminSchedules;


