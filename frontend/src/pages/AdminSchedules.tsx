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

/** Relative time string, e.g. "3 min ago", "2h ago", "5d ago". */
const timeAgo = (iso: string | null | undefined): string => {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 0) return 'just now';
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
};

/** Extract the short function name from a dotted task path. */
const shortTask = (task: string): string => {
  if (!task) return '—';
  const parts = task.split('.');
  return parts[parts.length - 1];
};

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
    if (min !== '*' && hour === '*' && dom === '*' && mon === '*' && dow === '*') {
      return `Every hour at :${pad(min)} ${tz}`;
    }
    if (min !== '*' && hour !== '*' && dom === '*' && mon === '*' && dow === '*') {
      return `Daily at ${pad(hour)}:${pad(min)} ${tz}`;
    }
    if (min !== '*' && hour !== '*' && dom === '*' && mon === '*' && dow !== '*') {
      return `${parseDow(dow)} at ${pad(hour)}:${pad(min)} ${tz}`;
    }
    if (min !== '*' && hour !== '*' && dom !== '*' && mon === '*' && dow === '*') {
      return `Monthly day ${dom} at ${pad(hour)}:${pad(min)} ${tz}`;
    }
    return cron;
  };

  const openPreset = (preset: { name: string; task: string; cron: string; timezone: string }) => {
    setForm(preset);
    setCreateOpen(true);
  };

  const mode = data?.mode || 'loading';

  return (
    <Box p={0}>
      <HStack justify="space-between" mb={3} align="start">
        <Box>
          <HStack gap={2} align="center">
            <Heading size="md">Schedules</Heading>
            <Badge colorPalette={mode === 'redbeat' ? 'green' : mode === 'static' ? 'orange' : 'gray'} size="sm">
              {mode === 'redbeat' ? 'RedBeat' : mode === 'static' ? 'Static' : '…'}
            </Badge>
          </HStack>
          <Text fontSize="sm" color="fg.muted" mt={1}>
            Recurring background jobs managed by Celery Beat. Create, pause, run, or delete schedules.
          </Text>
          <HStack mt={2} gap={2} flexWrap="wrap">
            <Button
              size="xs"
              variant="outline"
              onClick={() =>
                openPreset({
                  name: 'admin_coverage_backfill',
                  task: 'backend.tasks.market_data_tasks.bootstrap_daily_coverage_tracked',
                  cron: '0 3 * * *',
                  timezone: 'UTC',
                })
              }
            >
              Preset: Nightly Backfill (Tracked) + History (5d)
            </Button>
          </HStack>
        </Box>
        <HStack gap={2} flexShrink={0}>
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
                key: 'name',
                header: 'Job',
                accessor: (s: any) => s.name,
                sortable: true,
                sortType: 'string',
                render: (_v, s) => {
                  const status = String(s.status || (s.enabled ? 'active' : 'paused'));
                  const palette = status === 'active' ? 'green' : status === 'paused' ? 'orange' : 'gray';
                  return (
                    <Box>
                      <HStack gap={2} align="center">
                        <Badge colorPalette={palette} size="sm" variant="subtle">
                          {status}
                        </Badge>
                        <Text fontWeight="medium" fontSize="13px">{String(s.name || '')}</Text>
                      </HStack>
                      <TooltipRoot>
                        <TooltipTrigger asChild>
                          <Text fontFamily="mono" fontSize="11px" color="fg.muted" truncate maxW="280px">
                            {shortTask(String(s.task || ''))}
                          </Text>
                        </TooltipTrigger>
                        <TooltipPositioner>
                          <TooltipContent>{String(s.task || '')}</TooltipContent>
                        </TooltipPositioner>
                      </TooltipRoot>
                    </Box>
                  );
                },
                width: '260px',
              },
              {
                key: 'schedule',
                header: 'Schedule',
                accessor: (s: any) => s.cron || '',
                sortable: true,
                sortType: 'string',
                render: (_v, s) => {
                  const cron = String(s?.cron || '');
                  const tz = String(s?.timezone || 'UTC');
                  const friendly = cron ? formatCronFriendly(cron, tz) : '—';
                  const nextUtc = nextRuns[String(s?.name || '')];
                  const nextLocal = nextUtc ? formatDateTime(nextUtc, timezone) : null;
                  return (
                    <Box>
                      <Text fontSize="12px" fontWeight="medium">{friendly}</Text>
                      {cron && (
                        <Text fontFamily="mono" fontSize="11px" color="fg.muted">{cron}</Text>
                      )}
                      {nextLocal && (
                        <Text fontSize="11px" color="fg.subtle">Next: {nextLocal}</Text>
                      )}
                    </Box>
                  );
                },
              },
              {
                key: 'last_run',
                header: 'Last Run',
                accessor: (s: any) => s.last_run_at || s.last_run?.started_at || '',
                sortable: true,
                sortType: 'string',
                render: (_v, s) => {
                  const beatAt = s.last_run_at as string | undefined;
                  const jobRun = s.last_run as { status?: string; started_at?: string } | undefined;
                  const ts = beatAt || jobRun?.started_at;
                  const jobStatus = jobRun?.status;
                  const statusPalette = jobStatus === 'success' ? 'green' : jobStatus === 'failed' ? 'red' : 'gray';
                  return (
                    <Box>
                      <TooltipRoot>
                        <TooltipTrigger asChild>
                          <Text fontSize="12px" color="fg.default">{timeAgo(ts)}</Text>
                        </TooltipTrigger>
                        {ts && (
                          <TooltipPositioner>
                            <TooltipContent>{formatDateTime(ts, timezone)}</TooltipContent>
                          </TooltipPositioner>
                        )}
                      </TooltipRoot>
                      {jobStatus && (
                        <Badge colorPalette={statusPalette} size="sm" variant="subtle" mt="2px">
                          {jobStatus}
                        </Badge>
                      )}
                    </Box>
                  );
                },
                width: '120px',
              },
              {
                key: 'runs',
                header: 'Runs',
                accessor: (s: any) => s.total_run_count ?? 0,
                sortable: true,
                sortType: 'number',
                render: (v) => <Text fontSize="12px" color="fg.muted">{v != null ? String(v) : '—'}</Text>,
                width: '70px',
              },
              {
                key: 'actions',
                header: '',
                accessor: () => null,
                sortable: false,
                isNumeric: true,
                width: '120px',
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
