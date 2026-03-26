import React from 'react';
import { useColorMode } from '../theme/colorMode';
import SortableTable, { type Column, type FilterGroup } from '../components/SortableTable';
import Pagination from '../components/ui/Pagination';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export default {
  title: 'DesignSystem/Tables',
};

type JobRow = {
  id: number;
  status: 'ok' | 'running' | 'error';
  task_name: string;
  started_at: string;
  finished_at?: string | null;
};

const sample: JobRow[] = [
  { id: 1, status: 'ok', task_name: 'admin_coverage_refresh', started_at: new Date().toISOString(), finished_at: new Date().toISOString() },
  { id: 2, status: 'running', task_name: 'admin_backfill_5m', started_at: new Date(Date.now() - 60_000).toISOString(), finished_at: null },
  { id: 3, status: 'error', task_name: 'market_universe_tracked_refresh', started_at: new Date(Date.now() - 3600_000).toISOString(), finished_at: new Date(Date.now() - 3500_000).toISOString() },
];

function statusBadgeClass(status: string) {
  if (status === 'ok') return 'border-emerald-500/40 text-emerald-800 dark:text-emerald-200';
  if (status === 'running') return 'border-blue-500/40 text-blue-800 dark:text-blue-200';
  return 'border-destructive/40 text-destructive';
}

export const Sortable_With_Pagination = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(25);
  const total = 4585;

  const columns: Column<JobRow>[] = [
    {
      key: 'status',
      header: 'Status',
      accessor: (r) => r.status,
      sortable: true,
      sortType: 'string',
      filterType: 'select',
      filterOptions: [
        { label: 'ok', value: 'ok' },
        { label: 'running', value: 'running' },
        { label: 'error', value: 'error' },
      ],
      render: (v) => (
        <Badge variant="outline" className={cn('font-normal', statusBadgeClass(String(v)))}>
          {String(v)}
        </Badge>
      ),
      width: '140px',
    },
    {
      key: 'task',
      header: 'Task',
      accessor: (r) => r.task_name,
      sortable: true,
      sortType: 'string',
      render: (v) => <span className="font-mono text-[12px]">{String(v)}</span>,
    },
    {
      key: 'started_at',
      header: 'Started',
      accessor: (r) => r.started_at,
      sortable: true,
      sortType: 'date',
      render: (v) => <span className="text-xs text-muted-foreground">{new Date(String(v)).toLocaleString()}</span>,
      width: '220px',
    },
  ];

  const filterPresets: Array<{ label: string; filters: FilterGroup }> = [
    {
      label: 'Only errors',
      filters: {
        conjunction: 'AND' as const,
        rules: [
          {
            id: 'preset_errors',
            columnKey: 'status',
            operator: 'equals' as const,
            value: 'error',
          },
        ],
      },
    },
  ];

  return (
    <div className="p-6">
      <div className="mb-4 flex flex-row items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-foreground">Standard Table</div>
          <div className="text-sm text-muted-foreground">Mode: {colorMode}</div>
        </div>
        <button
          type="button"
          onClick={toggleColorMode}
          className="rounded-[10px] border border-border px-3 py-2 text-sm"
        >
          Toggle mode
        </button>
      </div>

      <div className="rounded-xl border border-border bg-card">
        <SortableTable
          data={sample}
          columns={columns}
          defaultSortBy="started_at"
          defaultSortOrder="desc"
          size="sm"
          maxHeight="50vh"
          filtersEnabled
          filterPresets={filterPresets}
        />
      </div>

      <div className="mt-3">
        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={setPage}
          onPageSizeChange={(s) => {
            setPageSize(s);
            setPage(1);
          }}
        />
      </div>
    </div>
  );
};
