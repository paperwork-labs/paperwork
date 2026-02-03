import React from 'react';
import { Box, Badge, HStack, Text } from '@chakra-ui/react';
import { useColorMode } from '../theme/colorMode';
import SortableTable, { type Column, type FilterGroup } from '../components/SortableTable';
import Pagination from '../components/ui/Pagination';

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
  { id: 1, status: 'ok', task_name: 'monitor_coverage_health', started_at: new Date().toISOString(), finished_at: new Date().toISOString() },
  { id: 2, status: 'running', task_name: 'backfill_5m_last_n_days', started_at: new Date(Date.now() - 60_000).toISOString(), finished_at: null },
  { id: 3, status: 'error', task_name: 'update_tracked_symbol_cache', started_at: new Date(Date.now() - 3600_000).toISOString(), finished_at: new Date(Date.now() - 3500_000).toISOString() },
];

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
        <Badge colorPalette={v === 'ok' ? 'green' : v === 'running' ? 'blue' : 'red'}>
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
      render: (v) => <Text fontFamily="mono" fontSize="12px">{String(v)}</Text>,
    },
    {
      key: 'started_at',
      header: 'Started',
      accessor: (r) => r.started_at,
      sortable: true,
      sortType: 'date',
      render: (v) => <Text fontSize="12px" color="fg.muted">{new Date(String(v)).toLocaleString()}</Text>,
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
    <Box p={6}>
      <HStack justify="space-between" mb={4}>
        <Box>
          <Text fontSize="lg" fontWeight="semibold" color="fg.default">Standard Table</Text>
          <Text fontSize="sm" color="fg.muted">Mode: {colorMode}</Text>
        </Box>
        <Text as="button" onClick={toggleColorMode} style={{ padding: '8px 12px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.12)' }}>
          Toggle mode
        </Text>
      </HStack>

      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="xl" bg="bg.card">
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
      </Box>

      <Box mt={3}>
        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={setPage}
          onPageSizeChange={(s) => { setPageSize(s); setPage(1); }}
        />
      </Box>
    </Box>
  );
};


