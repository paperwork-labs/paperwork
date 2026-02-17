import React from 'react';
import { Box, Text, HStack } from '@chakra-ui/react';
import type { AdminHealthResponse } from '../../types/adminHealth';

interface Props {
  health: AdminHealthResponse | null;
}

interface RunbookEntry {
  what: string;
  fix: string;
  threshold: (thresholds: Record<string, number>) => string;
}

const RUNBOOK: Record<string, RunbookEntry> = {
  coverage: {
    what: 'Daily price coverage has dropped below the required fill percentage or has stale trading dates.',
    fix: 'Click "Refresh Coverage" on the Admin Dashboard. If the issue persists, try "Backfill Daily Coverage (Tracked)" or "Backfill Daily (Stale Only)" from the Backfill Actions section. Check Settings > Admin > Jobs for failed coverage tasks and Admin > Schedules to verify the hourly coverage monitor is running.',
    threshold: (t) =>
      `Daily fill >= ${t.coverage_daily_pct_min ?? 95}%, stale daily rows <= ${t.coverage_stale_daily_max ?? 0}`,
  },
  stage_quality: {
    what: 'Stage analysis has too many unknowns, invalid rows, or monotonicity violations.',
    fix: 'Click "Recompute Indicators (Market Snapshot)" under Show Advanced > Maintenance. If unknowns persist, the underlying daily bars may be missing — run "Backfill Daily Coverage (Tracked)" first, then recompute. Check Settings > Admin > Jobs for specific task errors.',
    threshold: (t) =>
      `Unknown rate <= ${((t.stage_unknown_rate_max ?? 0.35) * 100).toFixed(0)}%, invalid rows <= ${t.stage_invalid_max ?? 0}, monotonicity issues <= ${t.stage_monotonicity_max ?? 0}`,
  },
  jobs: {
    what: 'One or more background jobs have failed in the lookback window.',
    fix: 'Go to Settings > Admin > Jobs to inspect the failed task. Check the error message, then re-trigger the task from Operator Actions (Safe or Backfill sections) or fix the underlying issue (e.g., API key, network). The schedule auto-retries on the next cron tick.',
    threshold: (t) =>
      `Error count <= ${t.jobs_error_max ?? 0} in the last ${t.jobs_lookback_hours ?? 24}h`,
  },
  audit: {
    what: 'Market audit detected that daily or snapshot fill percentages are below acceptable thresholds for the tracked universe.',
    fix: 'Run "Backfill Daily Coverage (Tracked)" from the Backfill Actions section. For snapshot history gaps, open Show Advanced and run "Backfill Snapshot History (period)". Check Settings > Admin > Jobs for audit task results. If specific symbols are listed as missing, verify they are still tracked in Market > Tracked.',
    threshold: (t) =>
      `Daily fill >= ${t.audit_daily_fill_pct_min ?? 95}%, snapshot fill >= ${t.audit_snapshot_fill_pct_min ?? 90}%`,
  },
};

const AdminRunbook: React.FC<Props> = ({ health }) => {
  const [expanded, setExpanded] = React.useState(false);

  if (!health) return null;

  const dims = health.dimensions;
  const redDims = Object.entries(dims).filter(([, dim]) => dim.status === 'red');

  return (
    <Box
      mb={4}
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="lg"
      p={3}
      bg="bg.muted"
    >
      <HStack
        justify="space-between"
        align="center"
        cursor="pointer"
        onClick={() => setExpanded((v) => !v)}
        userSelect="none"
      >
        <Text fontSize="sm" fontWeight="semibold">
          Runbook / On-Call Guide {redDims.length > 0 ? `(${redDims.length} issue${redDims.length > 1 ? 's' : ''})` : ''}
        </Text>
        <Text fontSize="xs" color="fg.muted">{expanded ? '▲ collapse' : '▼ expand'}</Text>
      </HStack>

      {expanded && (
        <Box mt={2}>
          {redDims.length === 0 ? (
            <Text fontSize="xs" color="status.success">
              All systems healthy — no action needed.
            </Text>
          ) : (
            redDims.map(([key]) => {
              const entry = RUNBOOK[key];
              if (!entry) return null;
              return (
                <Box
                  key={key}
                  mt={2}
                  p={2}
                  borderWidth="1px"
                  borderColor="border.subtle"
                  borderRadius="md"
                  bg="bg.card"
                >
                  <Text fontSize="sm" fontWeight="semibold" color="status.danger" mb={1}>
                    {key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </Text>
                  <Text fontSize="xs" color="fg.default" mb={1}>
                    <strong>What:</strong> {entry.what}
                  </Text>
                  <Text fontSize="xs" color="fg.default" mb={1}>
                    <strong>Fix:</strong> {entry.fix}
                  </Text>
                  <Text fontSize="xs" color="fg.muted">
                    <strong>Threshold:</strong> {entry.threshold(health.thresholds)}
                  </Text>
                </Box>
              );
            })
          )}
        </Box>
      )}
    </Box>
  );
};

export default AdminRunbook;
