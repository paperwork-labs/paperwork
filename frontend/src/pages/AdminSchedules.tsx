import React from 'react';
import {
  Check,
  Clock,
  Loader2,
  Pause,
  Pencil,
  Play,
  RotateCw,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../services/api';
import FormField from '../components/ui/FormField';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
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
  const colorClass = s.render_sync_error
    ? 'bg-destructive'
    : s.render_synced_at
      ? 'bg-emerald-500'
      : 'bg-muted-foreground/50';
  const label = s.render_sync_error
    ? `Sync error: ${s.render_sync_error}`
    : s.render_synced_at
      ? `Synced ${formatRelativeTime(s.render_synced_at)}`
      : 'Not yet synced to Render';
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn('inline-block size-[7px] shrink-0 rounded-full', colorClass)} />
      </TooltipTrigger>
      <TooltipContent className="max-w-[300px] text-background">{label}</TooltipContent>
    </Tooltip>
  );
};

const GROUP_LABELS: Record<string, string> = {
  market_data: 'Market Data',
  accounts: 'Accounts',
  maintenance: 'Maintenance',
};

const ChangeSummary: React.FC<{ changes: Record<string, any> | null; action: string }> = ({ changes, action }) => {
  if (!changes || typeof changes !== 'object') {
    return <p className="text-xs italic text-muted-foreground">{action}</p>;
  }
  if (action === 'created' || action === 'deleted') {
    const task = changes.task ? shortTask(changes.task) : '';
    const cron = changes.cron || '';
    return (
      <p className="max-w-[400px] truncate text-xs text-muted-foreground">
        {task}{cron ? ` (${cron})` : ''}
      </p>
    );
  }
  const fields = Object.entries(changes);
  if (fields.length === 0) return <p className="text-xs text-muted-foreground">no changes</p>;
  return (
    <div>
      {fields.map(([key, val]) => (
        <p key={key} className="max-w-[400px] truncate text-[11px] text-muted-foreground">
          <span className="font-medium text-foreground">{key}</span>
          {': '}
          <span className="line-through opacity-50">{String(val?.old ?? '—')}</span>
          {' → '}
          <span>{String(val?.new ?? '—')}</span>
        </p>
      ))}
    </div>
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
        const statusColor = s.enabled ? 'bg-emerald-500' : 'bg-amber-500';
        const statusLabel = s.enabled ? 'Enabled' : 'Paused';
        return (
          <div className="py-0.5">
            <div className="flex items-center gap-1.5">
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className={cn('size-2 shrink-0 rounded-full', statusColor)} />
                </TooltipTrigger>
                <TooltipContent className="text-background">{statusLabel}</TooltipContent>
              </Tooltip>
              <span className="text-[13px] font-semibold leading-snug text-foreground">{s.display_name || s.id}</span>
              <SyncDot s={s} />
            </div>
            {s.description && (
              <p className="mt-px max-w-[280px] truncate pl-3.5 text-[11px] text-muted-foreground">
                {s.description}
              </p>
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <p className="mt-px max-w-[220px] truncate pl-3.5 font-mono text-[10px] text-muted-foreground/80">
                  {shortTask(s.task)}
                </p>
              </TooltipTrigger>
              <TooltipContent className="max-w-md font-mono text-xs text-background">{s.task}</TooltipContent>
            </Tooltip>
          </div>
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
            <div className="flex items-center gap-1">
              <Input
                className="h-7 w-[140px] font-mono text-xs"
                value={editCron}
                onChange={(e) => setEditCron(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (e.metaKey || e.ctrlKey) {
                      void saveEditCron(s.id);
                    } else {
                      toast('Use Cmd/Ctrl + Enter to save');
                    }
                  }
                  if (e.key === 'Escape') setEditingId(null);
                }}
                autoFocus
              />
              <Button type="button" aria-label="Save" size="icon-xs" variant="ghost" onClick={() => void saveEditCron(s.id)}>
                <Check className="size-3.5" aria-hidden />
              </Button>
              <Button type="button" aria-label="Cancel" size="icon-xs" variant="ghost" onClick={() => setEditingId(null)}>
                <X className="size-3.5" aria-hidden />
              </Button>
            </div>
          );
        }
        const cron = s.cron || '';
        const tz = s.timezone || 'UTC';
        const friendly = cron ? formatCronFriendly(cron, tz) : '—';
        const nextUtc = nextRuns[s.id];
        const nextLocal = nextUtc ? formatDateTime(nextUtc, timezone) : null;
        return (
          <div
            role="button"
            tabIndex={0}
            className="cursor-pointer rounded-md px-1 hover:bg-muted/80"
            onClick={() => { setEditingId(s.id); setEditCron(s.cron); }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setEditingId(s.id);
                setEditCron(s.cron);
              }
            }}
          >
            <div className="flex items-center gap-1">
              <span className="text-xs font-medium text-foreground">{friendly}</span>
              <Pencil className="size-2.5 opacity-40" aria-hidden />
            </div>
            {cron ? <p className="font-mono text-[11px] text-muted-foreground">{cron}</p> : null}
            {nextLocal ? <p className="text-[11px] text-muted-foreground/80">Next: {nextLocal}</p> : null}
          </div>
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
        const runBadge =
          jobStatus === 'ok'
            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200'
            : jobStatus === 'error'
              ? 'border-destructive/40 bg-destructive/10 text-destructive'
              : 'border-border bg-muted text-muted-foreground';
        return (
          <div>
            {ts ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="text-xs text-foreground">{formatRelativeTime(ts)}</span>
                </TooltipTrigger>
                <TooltipContent className="text-background">{formatDateTime(ts, timezone)}</TooltipContent>
              </Tooltip>
            ) : (
              <span className="text-xs text-foreground">{formatRelativeTime(ts)}</span>
            )}
            {jobStatus ? (
              <Badge variant="outline" className={cn('mt-0.5 font-normal', runBadge)}>
                {jobStatus}
              </Badge>
            ) : null}
          </div>
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
        const groupCls =
          raw === 'accounts'
            ? 'border-violet-500/40 bg-violet-500/10 text-violet-800 dark:text-violet-200'
            : raw === 'maintenance'
              ? 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200'
              : 'border-blue-500/40 bg-blue-500/10 text-blue-800 dark:text-blue-200';
        return (
          <Badge variant="outline" className={cn('font-normal', groupCls)}>
            {label}
          </Badge>
        );
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
        <div className="flex justify-end gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                aria-label="Run now"
                size="icon-xs"
                variant="outline"
                onClick={() => void runNow(s.task)}
                disabled={!s.task}
              >
                <Play className="size-3.5" aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent className="text-background">Run now</TooltipContent>
          </Tooltip>
          {s.enabled ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button type="button" aria-label="Pause" size="icon-xs" variant="outline" onClick={() => void pause(s.id)}>
                  <Pause className="size-3.5" aria-hidden />
                </Button>
              </TooltipTrigger>
              <TooltipContent className="text-background">Pause</TooltipContent>
            </Tooltip>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button type="button" aria-label="Resume" size="icon-xs" variant="outline" onClick={() => void resume(s.id)}>
                  <RotateCw className="size-3.5" aria-hidden />
                </Button>
              </TooltipTrigger>
              <TooltipContent className="text-background">Resume</TooltipContent>
            </Tooltip>
          )}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                aria-label="Delete"
                size="icon-xs"
                variant="outline"
                className="text-destructive hover:bg-destructive/10"
                onClick={() => setDeleteTargetId(s.id)}
              >
                <Trash2 className="size-3.5" aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent className="text-background">Delete</TooltipContent>
          </Tooltip>
        </div>
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
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="text-xs text-foreground">{formatRelativeTime(e.timestamp)}</span>
          </TooltipTrigger>
          <TooltipContent className="text-background">{formatDateTime(e.timestamp, timezone)}</TooltipContent>
        </Tooltip>
      ),
      width: '100px',
    },
    {
      key: 'action',
      header: 'Action',
      accessor: (e) => e.action,
      sortable: true,
      sortType: 'string',
      render: (_v, e) => {
        const pal = ACTION_PALETTE[e.action] || 'gray';
        const cls =
          pal === 'green'
            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200'
            : pal === 'blue'
              ? 'border-blue-500/40 bg-blue-500/10 text-blue-800 dark:text-blue-200'
              : pal === 'orange'
                ? 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200'
                : pal === 'teal'
                  ? 'border-teal-500/40 bg-teal-500/10 text-teal-900 dark:text-teal-200'
                  : pal === 'red'
                    ? 'border-destructive/40 bg-destructive/10 text-destructive'
                    : 'border-border bg-muted text-muted-foreground';
        return (
          <Badge variant="outline" className={cn('font-normal', cls)}>
            {e.action}
          </Badge>
        );
      },
      width: '90px',
    },
    {
      key: 'schedule_id',
      header: 'Schedule',
      accessor: (e) => e.schedule_id,
      sortable: true,
      sortType: 'string',
      render: (v) => <span className="font-mono text-xs text-foreground">{String(v)}</span>,
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
      render: (v) => (
        <span className="max-w-[140px] truncate text-xs text-muted-foreground">{String(v)}</span>
      ),
      width: '140px',
    },
  ];

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <TooltipProvider delayDuration={200}>
      <div className="mx-auto max-w-[1600px] px-4 py-2 md:px-6 xl:px-8">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-heading text-lg font-semibold text-foreground">Schedules</h1>
              <Badge variant="outline" className="border-blue-500/40 bg-blue-500/10 font-normal text-blue-800 dark:text-blue-200">
                DB + Render
              </Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {view === 'schedules'
                ? 'Recurring background jobs. Click on a cron expression to edit it inline.'
                : 'Audit trail of all schedule changes.'}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <div className="flex overflow-hidden rounded-md border border-border">
              <Button
                type="button"
                size="sm"
                variant={view === 'schedules' ? 'default' : 'ghost'}
                className="rounded-none border-0 shadow-none"
                onClick={() => setView('schedules')}
              >
                Schedules
              </Button>
              <Button
                type="button"
                size="sm"
                variant={view === 'history' ? 'default' : 'ghost'}
                className="rounded-none border-0 shadow-none"
                onClick={() => setView('history')}
              >
                <Clock className="mr-1 size-3.5" aria-hidden />
                History
              </Button>
            </div>
            {view === 'schedules' && (
              <>
                {renderSyncEnabled && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={syncing}
                        onClick={() => void syncToRender()}
                      >
                        {syncing ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                        <UploadCloud className="mr-1 size-3.5" aria-hidden />
                        Sync to Render
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-background">
                      Push all schedules to Render cron jobs
                    </TooltipContent>
                  </Tooltip>
                )}
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    void loadCatalog();
                    setCreateOpen(true);
                  }}
                >
                  New schedule
                </Button>
                <Button type="button" size="sm" disabled={loading} onClick={() => void load()}>
                  {loading ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                  Reload
                </Button>
              </>
            )}
            {view === 'history' && (
              <Button type="button" size="sm" disabled={historyLoading} onClick={() => void loadHistory()}>
                {historyLoading ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                Reload
              </Button>
            )}
          </div>
        </div>

        <div className="mt-1 w-full overflow-hidden rounded-xl border border-border bg-card shadow-xs">
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
              emptyMessage={
                historyLoading
                  ? 'Loading...'
                  : 'No history yet. Changes are recorded when you create, edit, pause, or delete schedules.'
              }
            />
          )}
        </div>

        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent
            showCloseButton
            className="max-w-[min(720px,calc(100vw-2rem))] gap-4 sm:max-w-[min(720px,calc(100vw-2rem))]"
          >
            <DialogHeader>
              <DialogTitle>New Schedule</DialogTitle>
            </DialogHeader>
            <div className="flex flex-col gap-4">
              {catalog.length > 0 && (
                <FormField label="From catalog (optional)" helperText="Pick a template to pre-fill fields">
                  <div className="flex flex-wrap gap-2">
                    {catalog
                      .filter((c) => !schedules.some((s) => s.id === c.id))
                      .slice(0, 6)
                      .map((c) => (
                        <Button
                          key={c.id}
                          type="button"
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
                  </div>
                </FormField>
              )}
              <FormField label="ID" helperText="Unique identifier (e.g. admin_nightly_report)">
                <Input value={form.id} onChange={(e) => setForm((p) => ({ ...p, id: e.target.value }))} />
              </FormField>
              <FormField label="Display name">
                <Input value={form.display_name} onChange={(e) => setForm((p) => ({ ...p, display_name: e.target.value }))} />
              </FormField>
              <FormField
                label="Task (dotted path)"
                helperText="e.g. backend.tasks.market.coverage.health_check"
              >
                <Input value={form.task} onChange={(e) => setForm((p) => ({ ...p, task: e.target.value }))} />
              </FormField>
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField label="Cron" helperText="m h dom mon dow">
                  <Input value={form.cron} onChange={(e) => setForm((p) => ({ ...p, cron: e.target.value }))} />
                </FormField>
                <FormField label="Timezone">
                  <Input value={form.timezone} onChange={(e) => setForm((p) => ({ ...p, timezone: e.target.value }))} />
                </FormField>
              </div>
              <FormField label="Group">
                <Input value={form.group} onChange={(e) => setForm((p) => ({ ...p, group: e.target.value }))} />
              </FormField>
              <FormField label="Description">
                <Textarea
                  value={form.description}
                  onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                  rows={2}
                />
              </FormField>
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button type="button" disabled={creating} onClick={() => void create()}>
                {creating ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={Boolean(deleteTargetId)} onOpenChange={(open) => !open && setDeleteTargetId(null)}>
          <DialogContent showCloseButton className="max-w-[min(560px,calc(100vw-2rem))] sm:max-w-[min(560px,calc(100vw-2rem))]">
            <DialogHeader>
              <DialogTitle>Delete Schedule</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-foreground">
              Delete schedule <span className="font-mono">{deleteTargetId || '—'}</span>?
            </p>
            <p className="mt-2 text-sm text-muted-foreground">This also removes the linked Render cron job.</p>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setDeleteTargetId(null)}>
                Cancel
              </Button>
              <Button type="button" variant="destructive" onClick={() => void confirmDelete()}>
                Delete
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
};

export default AdminSchedules;
