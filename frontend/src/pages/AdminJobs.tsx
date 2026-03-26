import React from 'react';
import { Info, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../services/api';
import Pagination from '../components/ui/Pagination';
import SortableTable, { type Column } from '../components/SortableTable';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { formatDateTime } from '../utils/format';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

const AdminJobs: React.FC = () => {
  const { timezone } = useUserPreferences();
  const [loading, setLoading] = React.useState(false);
  const [data, setData] = React.useState<{ jobs: any[]; total?: number; limit?: number; offset?: number } | null>(null);
  const [selectedJob, setSelectedJob] = React.useState<any | null>(null);
  const [detailsOpen, setDetailsOpen] = React.useState(false);
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(25);
  const [hideCoverageRefresh, setHideCoverageRefresh] = React.useState(true);

  const statusBadgeClass = (raw: any) => {
    const s = String(raw || '').toLowerCase();
    if (['success', 'ok', 'completed', 'done'].includes(s)) return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300';
    if (['running', 'started', 'in_progress'].includes(s)) return 'border-blue-500/40 bg-blue-500/10 text-blue-700 dark:text-blue-300';
    if (['warning', 'degraded'].includes(s)) return 'border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200';
    if (['skipped', 'idle', 'noop'].includes(s)) return 'border-border bg-muted text-muted-foreground';
    return 'border-destructive/40 bg-destructive/10 text-destructive';
  };

  const summarizeJob = (j: any): string => {
    const counters = (j?.counters && typeof j.counters === 'object') ? j.counters : {};
    const params = (j?.params && typeof j.params === 'object') ? j.params : {};
    const status = String(j?.status || '');
    const task = String(j?.task_name || '').toLowerCase();

    const pick = (keys: string[]) => keys.find((k) => typeof counters?.[k] === 'number' && Number.isFinite(counters[k]));
    const kSymbols = pick(['symbols_processed', 'tickers_processed', 'symbols', 'tickers', 'symbols_total']);
    const kInserted = pick(['rows_inserted', 'bars_inserted', 'inserted', 'created', 'upserted']);
    const kUpdated = pick(['updated', 'rows_updated', 'bars_updated']);
    const durationS = typeof counters?.duration_s === 'number' ? Number(counters.duration_s) : undefined;

    const symbolsN =
      (kSymbols ? Number(counters[kSymbols]) : undefined) ??
      (Array.isArray(params?.symbols) ? params.symbols.length : undefined);
    const nDays = typeof params?.n_days === 'number' ? params.n_days : undefined;
    const maxDays5m = typeof params?.max_days_5m === 'number' ? params.max_days_5m : undefined;

    if (task.includes('admin_backfill_5m_symbols')) {
      const p = [];
      p.push('Backfilled 5m for selected symbols');
      if (typeof symbolsN === 'number') p.push(`(${symbolsN} symbols)`);
      if (typeof nDays === 'number') p.push(`(${nDays} days)`);
      return p.join(' ');
    }
    if (task.includes('admin_backfill_5m')) {
      const p = [];
      p.push('Backfilled 5m bars');
      if (typeof symbolsN === 'number') p.push(`for ${symbolsN} symbols`);
      if (typeof nDays === 'number') p.push(`(${nDays} days)`);
      return p.join(' ');
    }
    if (task.includes('admin_backfill_daily')) {
      const days = typeof counters?.days === 'number' ? Number(counters.days) : undefined;
      const label = typeof days === 'number' ? `Backfilled last ~${days} daily bars` : 'Backfilled last daily bars';
      return typeof symbolsN === 'number' ? `${label} (${symbolsN} symbols)` : label;
    }
    if (task.includes('admin_coverage_backfill')) return 'Backfill Daily Coverage (Tracked)';
    if (task.includes('market_indices_constituents_refresh')) return 'Refreshed index constituents';
    if (task.includes('market_universe_tracked_refresh')) return 'Updated tracked symbol universe';
    if (task.includes('admin_indicators_recompute_universe')) return 'Recomputed indicators for universe';
    if (task.includes('admin_snapshots_history_record')) return 'Recorded daily history snapshot';
    if (task.includes('admin_coverage_refresh')) return 'Computed coverage health snapshot';
    if (task.includes('admin_retention_enforce')) {
      return typeof maxDays5m === 'number' ? `Enforced price_data retention (5m max ${maxDays5m}d)` : 'Enforced price_data retention';
    }

    const parts: string[] = [];
    if (kSymbols) parts.push(`Processed ${counters[kSymbols]} symbols`);
    if (kInserted) parts.push(`Inserted ${counters[kInserted]}`);
    if (kUpdated) parts.push(`Updated ${counters[kUpdated]}`);
    if (typeof durationS === 'number') parts.push(`Duration ${Math.round(durationS)}s`);

    if (parts.length === 0) {
      if (typeof params?.n_days === 'number') parts.push(`n_days=${params.n_days}`);
      if (typeof params?.batch_size === 'number') parts.push(`batch=${params.batch_size}`);
      if (Array.isArray(params?.symbols) && params.symbols.length) parts.push(`${params.symbols.length} symbols`);
    }

    if (parts.length === 0) return status ? `Status: ${status}` : '—';
    return parts.join(' • ');
  };

  const load = async () => {
    setLoading(true);
    try {
      const offset = (page - 1) * pageSize;
      const params: Record<string, unknown> = { limit: pageSize, offset };
      if (hideCoverageRefresh) {
        params.exclude_task = 'admin_coverage_refresh';
      }
      const r = await api.get('/market-data/admin/jobs', { params });
      setData(r.data || null);
    } catch (err: unknown) {
      const axiosErr = err as { message?: string } | undefined;
      toast.error(axiosErr?.message || 'Failed to load admin jobs');
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    load();
  }, [page, pageSize, hideCoverageRefresh]);

  return (
    <div className="p-0">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-lg font-semibold text-foreground">Admin Jobs</h1>
          <p className="text-sm text-muted-foreground">
            Recent job runs recorded by the backend (task name, status, timings, and errors).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className={cn(
              'cursor-pointer rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors select-none',
              hideCoverageRefresh
                ? 'border-blue-500/40 bg-blue-500/10 text-blue-700 dark:text-blue-300'
                : 'border-border bg-muted text-muted-foreground hover:bg-muted/80',
            )}
            onClick={() => {
              setHideCoverageRefresh((v) => !v);
              setPage(1);
            }}
          >
            {hideCoverageRefresh ? 'Coverage refresh hidden' : 'Showing all jobs'}
          </button>
          <Button type="button" size="sm" disabled={loading} onClick={() => void load()}>
            {loading ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
            Reload
          </Button>
        </div>
      </div>
      <div className="w-full overflow-hidden rounded-xl border border-border bg-card shadow-xs">
        <SortableTable
          data={data?.jobs || []}
          columns={
            [
              {
                key: 'status',
                header: 'Status',
                accessor: (j: any) => j.status,
                sortable: true,
                sortType: 'string',
                render: (v) => (
                  <Badge variant="outline" className={cn('font-normal', statusBadgeClass(v))}>
                    {String(v || 'unknown')}
                  </Badge>
                ),
                width: '140px',
              },
              {
                key: 'task',
                header: 'Task',
                accessor: (j: any) => j.task_name,
                sortable: true,
                sortType: 'string',
                render: (v) => (
                  <span className="font-mono text-xs text-foreground">{String(v || '')}</span>
                ),
              },
              {
                key: 'summary',
                header: 'Summary',
                accessor: (j: any) => summarizeJob(j),
                sortable: true,
                sortType: 'string',
                render: (_v, j) => (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">{summarizeJob(j)}</span>
                    <TooltipProvider delayDuration={200}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button type="button" variant="ghost" size="icon-xs" aria-label="Info">
                            <Info className="size-3.5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-sm text-background">
                          <div className="space-y-2 text-xs">
                            <div>
                              <p className="font-semibold text-background">Params</p>
                              <pre className="mt-1 max-h-[120px] overflow-auto rounded-md bg-background/10 p-2 text-[11px] leading-snug">
                                {JSON.stringify(j?.params ?? {}, null, 2)}
                              </pre>
                            </div>
                            <div>
                              <p className="font-semibold text-background">Counters</p>
                              <pre className="mt-1 max-h-[120px] overflow-auto rounded-md bg-background/10 p-2 text-[11px] leading-snug">
                                {JSON.stringify(j?.counters ?? {}, null, 2)}
                              </pre>
                            </div>
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                ),
              },
              {
                key: 'started_at',
                header: 'Started',
                accessor: (j: any) => j.started_at,
                sortable: true,
                sortType: 'date',
                render: (v) => (
                  <span className="text-xs text-muted-foreground">{formatDateTime(v, timezone)}</span>
                ),
                width: '200px',
              },
              {
                key: 'finished_at',
                header: 'Finished',
                accessor: (j: any) => j.finished_at,
                sortable: true,
                sortType: 'date',
                render: (v) => (
                  <span className="text-xs text-muted-foreground">{formatDateTime(v, timezone)}</span>
                ),
                width: '200px',
              },
              {
                key: 'actions',
                header: 'Actions',
                accessor: () => null,
                sortable: false,
                isNumeric: true,
                width: '120px',
                render: (_v, j) => (
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      onClick={() => {
                        setSelectedJob(j);
                        setDetailsOpen(true);
                      }}
                    >
                      {j.error ? 'Error log' : 'Details'}
                    </Button>
                  </div>
                ),
              },
            ] as Column<any>[]
          }
          defaultSortBy="started_at"
          defaultSortOrder="desc"
          size="sm"
          maxHeight="70vh"
          emptyMessage={loading ? 'Loading…' : 'No jobs recorded yet.'}
        />
      </div>

      <div className="mt-2">
        <Pagination
          page={page}
          pageSize={pageSize}
          total={data?.total ?? (data?.jobs?.length ?? 0)}
          onPageChange={(p) => setPage(p)}
          onPageSizeChange={(s) => {
            setPageSize(s);
            setPage(1);
          }}
        />
      </div>

      <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
        <DialogContent
          showCloseButton
          className="max-h-[min(90vh,800px)] max-w-[min(760px,calc(100vw-2rem))] gap-4 overflow-y-auto"
        >
          <DialogHeader>
            <DialogTitle>{selectedJob?.error ? 'Job error log' : 'Job details'}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 text-sm">
            <div>
              <p className="text-xs text-muted-foreground">Task</p>
              <p className="font-mono text-xs text-foreground">{String(selectedJob?.task_name || '—')}</p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="outline" className={cn('font-normal', statusBadgeClass(selectedJob?.status))}>
                {String(selectedJob?.status || 'unknown')}
              </Badge>
              <span className="text-xs text-muted-foreground">id: {selectedJob?.id ?? '—'}</span>
              <span className="text-xs text-muted-foreground">
                started: {formatDateTime(selectedJob?.started_at, timezone)}
              </span>
              <span className="text-xs text-muted-foreground">
                finished: {formatDateTime(selectedJob?.finished_at, timezone)}
              </span>
            </div>

            {selectedJob?.error ? null : (
              <>
                <div>
                  <p className="mb-1 text-xs text-muted-foreground">Params</p>
                  <pre className="max-h-[200px] overflow-auto rounded-lg border border-border bg-muted/50 p-3 font-mono text-xs leading-relaxed">
                    {JSON.stringify(selectedJob?.params ?? {}, null, 2)}
                  </pre>
                </div>
                <div>
                  <p className="mb-1 text-xs text-muted-foreground">Counters</p>
                  <pre className="max-h-[200px] overflow-auto rounded-lg border border-border bg-muted/50 p-3 font-mono text-xs leading-relaxed">
                    {JSON.stringify(selectedJob?.counters ?? {}, null, 2)}
                  </pre>
                </div>
              </>
            )}

            <div>
              <p className="mb-1 text-xs text-muted-foreground">Error</p>
              <pre className="max-h-[280px] overflow-auto rounded-lg border border-border bg-muted/50 p-3 font-mono text-xs leading-relaxed">
                {selectedJob?.error ? String(selectedJob.error) : '—'}
              </pre>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setDetailsOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AdminJobs;
