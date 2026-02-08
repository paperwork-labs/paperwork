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
  TooltipRoot,
  TooltipTrigger,
  TooltipPositioner,
  TooltipContent,
} from '@chakra-ui/react';
import toast from 'react-hot-toast';
import api from '../services/api';
import { FiInfo } from 'react-icons/fi';
import Pagination from '../components/ui/Pagination';
import SortableTable, { type Column } from '../components/SortableTable';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { formatDateTime } from '../utils/format';

const AdminJobs: React.FC = () => {
  const { timezone } = useUserPreferences();
  const [loading, setLoading] = React.useState(false);
  const [data, setData] = React.useState<{ jobs: any[]; total?: number; limit?: number; offset?: number } | null>(null);
  const [selectedJob, setSelectedJob] = React.useState<any | null>(null);
  const [detailsOpen, setDetailsOpen] = React.useState(false);
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(25);

  const statusPalette = (raw: any) => {
    const s = String(raw || '').toLowerCase();
    if (['success', 'ok', 'completed', 'done'].includes(s)) return 'green';
    if (['running', 'started', 'in_progress'].includes(s)) return 'blue';
    if (['warning', 'degraded'].includes(s)) return 'yellow';
    if (['skipped', 'idle', 'noop'].includes(s)) return 'gray';
    return 'red';
  };

  const summarizeJob = (j: any): string => {
    const counters = (j?.counters && typeof j.counters === 'object') ? j.counters : {};
    const params = (j?.params && typeof j.params === 'object') ? j.params : {};
    const status = String(j?.status || '');
    const task = String(j?.task_name || '').toLowerCase();

    // Prefer meaningful counters if present
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

    // Task-specific mappings (derived from task_name + params/counters; never hardcoded)
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
    if (task.includes('admin_coverage_restore')) return 'Restore Daily Coverage (Tracked)';
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

    // If no counters, try params
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
      const r = await api.get('/market-data/admin/jobs', { params: { limit: pageSize, offset } });
      setData(r.data || null);
    } catch (err: any) {
      toast.error(err?.message || 'Failed to load admin jobs');
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    load();
  }, [page, pageSize]);

  return (
    <Box p={0}>
      <HStack justify="space-between" mb={3}>
        <Box>
          <Heading size="md">Admin Jobs</Heading>
          <Text fontSize="sm" color="fg.muted">
            Recent job runs recorded by the backend (task name, status, timings, and errors).
          </Text>
        </Box>
        <Button size="sm" onClick={load} loading={loading}>
          Reload
        </Button>
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
          data={data?.jobs || []}
          columns={
            [
              {
                key: 'status',
                header: 'Status',
                accessor: (j: any) => j.status,
                sortable: true,
                sortType: 'string',
                render: (v, j) => (
                  <Badge colorPalette={statusPalette(v)}>{String(v || 'unknown')}</Badge>
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
                  <Text fontFamily="mono" fontSize="12px">{String(v || '')}</Text>
                ),
              },
              {
                key: 'summary',
                header: 'Summary',
                accessor: (j: any) => summarizeJob(j),
                sortable: true,
                sortType: 'string',
                render: (_v, j) => (
                  <Box display="flex" alignItems="center" gap={2}>
                    <Text fontSize="12px" color="fg.muted">
                      {summarizeJob(j)}
                    </Text>
                    <TooltipRoot>
                      <TooltipTrigger asChild>
                        <IconButton aria-label="Info" size="xs" variant="ghost">
                          <FiInfo />
                        </IconButton>
                      </TooltipTrigger>
                      <TooltipPositioner>
                        <TooltipContent>
                          <Box>
                            <Text fontSize="xs" fontWeight="semibold">Params</Text>
                            <Box as="pre" fontSize="11px" lineHeight="1.35" maxH="120px" overflow="auto">
                              {JSON.stringify(j?.params ?? {}, null, 2)}
                            </Box>
                            <Text mt={2} fontSize="xs" fontWeight="semibold">Counters</Text>
                            <Box as="pre" fontSize="11px" lineHeight="1.35" maxH="120px" overflow="auto">
                              {JSON.stringify(j?.counters ?? {}, null, 2)}
                            </Box>
                          </Box>
                        </TooltipContent>
                      </TooltipPositioner>
                    </TooltipRoot>
                  </Box>
                ),
              },
              {
                key: 'started_at',
                header: 'Started',
                accessor: (j: any) => j.started_at,
                sortable: true,
                sortType: 'date',
                render: (v) => (
                  <Text fontSize="12px" color="fg.muted">
                    {formatDateTime(v, timezone)}
                  </Text>
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
                  <Text fontSize="12px" color="fg.muted">
                    {formatDateTime(v, timezone)}
                  </Text>
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
                  <Box display="flex" justifyContent="flex-end">
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => {
                        setSelectedJob(j);
                        setDetailsOpen(true);
                      }}
                    >
                      {j.error ? 'Error log' : 'Details'}
                    </Button>
                  </Box>
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
      </Box>

      <Box mt={2}>
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
      </Box>

      <DialogRoot open={detailsOpen} onOpenChange={(d) => setDetailsOpen(Boolean(d.open))}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent maxW="min(760px, calc(100vw - 32px))" w="full">
            <DialogHeader>
              <DialogTitle>{selectedJob?.error ? 'Job error log' : 'Job details'}</DialogTitle>
            </DialogHeader>
            <DialogBody>
              <Box display="flex" flexDirection="column" gap={3}>
                <Box>
                  <Text fontSize="xs" color="fg.muted">
                    Task
                  </Text>
                  <Text fontFamily="mono" fontSize="12px">
                    {String(selectedJob?.task_name || '—')}
                  </Text>
                </Box>
                <HStack gap={3} flexWrap="wrap">
                  <Badge colorPalette={statusPalette(selectedJob?.status)}>
                    {String(selectedJob?.status || 'unknown')}
                  </Badge>
                  <Text fontSize="xs" color="fg.muted">
                    id: {selectedJob?.id ?? '—'}
                  </Text>
                  <Text fontSize="xs" color="fg.muted">
                    started: {formatDateTime(selectedJob?.started_at, timezone)}
                  </Text>
                  <Text fontSize="xs" color="fg.muted">
                    finished: {formatDateTime(selectedJob?.finished_at, timezone)}
                  </Text>
                </HStack>

                {selectedJob?.error ? null : (
                  <>
                    <Box>
                      <Text fontSize="xs" color="fg.muted" mb={1}>
                        Params
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
                        maxH="200px"
                      >
                        {JSON.stringify(selectedJob?.params ?? {}, null, 2)}
                      </Box>
                    </Box>

                    <Box>
                      <Text fontSize="xs" color="fg.muted" mb={1}>
                        Counters
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
                        maxH="200px"
                      >
                        {JSON.stringify(selectedJob?.counters ?? {}, null, 2)}
                      </Box>
                    </Box>
                  </>
                )}

                <Box>
                  <Text fontSize="xs" color="fg.muted" mb={1}>
                    Error
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
                    maxH="280px"
                  >
                    {selectedJob?.error ? String(selectedJob.error) : '—'}
                  </Box>
                </Box>
              </Box>
            </DialogBody>
            <DialogFooter>
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

export default AdminJobs;


