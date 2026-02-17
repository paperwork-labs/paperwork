import React from 'react';
import { Box, Badge, HStack, Text } from '@chakra-ui/react';
import type { AdminHealthResponse } from '../../types/adminHealth';

interface Props {
  health: AdminHealthResponse | null;
}

const DIM_PALETTE: Record<string, string> = {
  green: 'green',
  yellow: 'orange',
  red: 'red',
};

const DimBadge: React.FC<{ status: string }> = ({ status }) => (
  <Badge variant="subtle" colorPalette={DIM_PALETTE[status] ?? 'gray'}>
    {status.toUpperCase()}
  </Badge>
);

const AdminDomainCards: React.FC<Props> = ({ health }) => {
  if (!health) return null;
  const { coverage, stage_quality, jobs, audit } = health.dimensions;

  return (
    <Box
      mt={3}
      display="grid"
      gridTemplateColumns={{ base: '1fr', lg: 'repeat(2, minmax(0, 1fr))' }}
      gap={3}
    >
      {/* Coverage */}
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
        <HStack justify="space-between" align="center" mb={1}>
          <Text fontSize="sm" fontWeight="semibold">Coverage</Text>
          <DimBadge status={coverage.status} />
        </HStack>
        <Text fontSize="xs" color="fg.muted">
          Daily: {typeof coverage.daily_pct === 'number' ? `${coverage.daily_pct.toFixed(1)}%` : '—'}
        </Text>
        <Text fontSize="xs" color="fg.muted">
          Stale daily: {coverage.stale_daily ?? 0}
        </Text>
        <Text fontSize="xs" color="fg.muted">
          Tracked: {coverage.tracked_count ?? 0}
        </Text>
        {coverage.expected_date && (
          <Text fontSize="xs" color="fg.muted">Latest date: {coverage.expected_date}</Text>
        )}
      </Box>

      {/* Stage Quality */}
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
        <HStack justify="space-between" align="center" mb={1}>
          <Text fontSize="sm" fontWeight="semibold">Stage Quality</Text>
          <DimBadge status={stage_quality.status} />
        </HStack>
        <Text fontSize="xs" color="fg.muted">
          Unknown rate: {typeof stage_quality.unknown_rate === 'number'
            ? `${(stage_quality.unknown_rate * 100).toFixed(1)}%`
            : '—'}
        </Text>
        <Text fontSize="xs" color="fg.muted">
          Invalid rows: {stage_quality.invalid_count ?? 0}
        </Text>
        <Text fontSize="xs" color="fg.muted">
          Monotonicity issues: {stage_quality.monotonicity_issues ?? 0}
        </Text>
        <Text fontSize="xs" color="fg.muted">
          Stale stage rows: {stage_quality.stale_stage_count ?? 0}
        </Text>
      </Box>

      {/* Jobs Health */}
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
        <HStack justify="space-between" align="center" mb={1}>
          <Text fontSize="sm" fontWeight="semibold">Jobs ({jobs.window_hours ?? 24}h)</Text>
          <DimBadge status={jobs.status} />
        </HStack>
        <Text fontSize="xs" color="fg.muted">
          Success rate: {typeof jobs.success_rate === 'number'
            ? `${(jobs.success_rate * 100).toFixed(1)}%`
            : '—'}
        </Text>
        <Text fontSize="xs" color="fg.muted">
          Failed: {jobs.error_count ?? 0} / Completed: {jobs.completed_count ?? 0}
        </Text>
        <Text fontSize="xs" color="fg.muted">
          Running: {jobs.running_count ?? 0}
        </Text>
        <Text fontSize="xs" color="fg.muted" lineClamp={1}>
          Latest failure: {jobs.latest_failed?.task_name || '—'}
        </Text>
      </Box>

      {/* Market Audit */}
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card">
        <HStack justify="space-between" align="center" mb={1}>
          <Text fontSize="sm" fontWeight="semibold">Market Audit</Text>
          <DimBadge status={audit.status} />
        </HStack>
        <Text fontSize="xs" color="fg.muted">
          Tracked total: {audit.tracked_total ?? '—'}
        </Text>
        <Text fontSize="xs" color="fg.muted">
          Daily fill: {typeof audit.daily_fill_pct === 'number'
            ? `${audit.daily_fill_pct.toFixed(1)}%`
            : '—'}
        </Text>
        <Text fontSize="xs" color="fg.muted">
          Snapshot fill: {typeof audit.snapshot_fill_pct === 'number'
            ? `${audit.snapshot_fill_pct.toFixed(1)}%`
            : '—'}
        </Text>
        <Text fontSize="xs" color="fg.muted" lineClamp={1}>
          Missing: {Array.isArray(audit.missing_sample)
            ? (audit.missing_sample.slice(0, 3).join(', ') || '—')
            : '—'}
        </Text>
      </Box>
    </Box>
  );
};

export default AdminDomainCards;
