import React from 'react';
import { Box, Text, HStack, Badge } from '@chakra-ui/react';
import type { AdminHealthResponse } from '../../types/adminHealth';

interface Props {
  health: AdminHealthResponse | null;
}

interface RunbookEntry {
  what: string;
  steps: string[];
  contextualSteps?: (dim: Record<string, unknown>) => string[];
  threshold: (thresholds: Record<string, number>) => string;
  metricSummary?: (dim: Record<string, unknown>) => Array<{ label: string; value: string; ok: boolean }>;
}

const RUNBOOK: Record<string, RunbookEntry> = {
  coverage: {
    what: 'Daily price coverage has dropped below the required fill percentage or has stale trading dates.',
    steps: [
      'Auto-ops checks health every 15 minutes and triggers backfills automatically.',
      'Click "Refresh Coverage" in Safe Actions to see current state.',
      'If still stale, try "Backfill Daily Coverage (Tracked)" or "Backfill Daily (Stale Only)" from Backfill Actions.',
      'Check System Status for failed nightly pipeline or backfill tasks.',
    ],
    threshold: (t) =>
      `Daily fill >= ${t.coverage_daily_pct_min ?? 95}%, stale daily rows <= ${t.coverage_stale_daily_max ?? 0}`,
  },
  stage_quality: {
    what: 'Stage analysis has too many unknowns, invalid rows, or monotonicity violations in stage duration counters.',
    steps: [
      'Ensure daily bars are backfilled — stages cannot compute without OHLCV data. Run "Backfill Daily Coverage (Tracked)" from Backfill Actions.',
      'Run "Recompute Indicators (Market Snapshot)" under Operator Actions > Advanced Controls > Maintenance to recalculate stage labels.',
      'Run "Repair Stage History" under Operator Actions > Advanced Controls > Maintenance to fix stage duration counters (current_stage_days) across history.',
      'Check System Status for failed compute or backfill tasks.',
    ],
    contextualSteps: (dim) => {
      const steps: string[] = [];
      const unknownRate = Number(dim.unknown_rate ?? 0);
      const monotonicity = Number(dim.monotonicity_issues ?? 0);
      const invalidCount = Number(dim.invalid_count ?? 0);

      if (unknownRate > 0.35) {
        steps.push('Too many UNKNOWN stages — daily bars are likely missing. Run "Backfill Daily Coverage (Tracked)" first, then "Recompute Indicators (Market Snapshot)" under Operator Actions > Advanced Controls > Maintenance.');
      }
      if (monotonicity > 0) {
        steps.push('Stage day-counter gaps detected — run "Repair Stage History" under Operator Actions > Advanced Controls > Maintenance. This recomputes current_stage_days and previous_stage fields across the last 120 days of history.');
      }
      if (invalidCount > 0) {
        steps.push('Invalid stage rows found — check System Status for failed indicator compute tasks, then re-run "Recompute Indicators (Market Snapshot)".');
      }
      if (unknownRate <= 0.35 && monotonicity === 0 && invalidCount === 0) {
        steps.push('All stage sub-checks are passing. If this dimension is still red, check System Status for any ongoing issues.');
      }
      return steps;
    },
    threshold: (t) =>
      `Unknown rate <= ${((t.stage_unknown_rate_max ?? 0.35) * 100).toFixed(0)}%, invalid rows <= ${t.stage_invalid_max ?? 0}, monotonicity issues <= ${t.stage_monotonicity_max ?? 0}`,
    metricSummary: (dim) => [
      { label: 'Unknown rate', value: `${((Number(dim.unknown_rate ?? 0)) * 100).toFixed(2)}%`, ok: Number(dim.unknown_rate ?? 0) <= 0.35 },
      { label: 'Invalid rows', value: String(dim.invalid_count ?? 0), ok: Number(dim.invalid_count ?? 0) === 0 },
      { label: 'Monotonicity', value: String(dim.monotonicity_issues ?? 0), ok: Number(dim.monotonicity_issues ?? 0) === 0 },
      { label: 'Stale stages', value: String(dim.stale_stage_count ?? 0), ok: Number(dim.stale_stage_count ?? 0) === 0 },
    ],
  },
  jobs: {
    what: 'One or more background jobs have failed in the lookback window.',
    steps: [
      'Go to System Status to inspect the failed task and error message.',
      'Re-trigger the task from Operator Actions (Safe or Backfill sections).',
      'If the error is environmental (API key, network), fix the root cause. The schedule auto-retries on the next cron tick.',
    ],
    threshold: (t) =>
      `Error count <= ${t.jobs_error_max ?? 0} in the last ${t.jobs_lookback_hours ?? 24}h`,
  },
  regime: {
    what: 'Market regime data is missing or stale (>48h since last computation).',
    steps: [
      'Check System Status for failed nightly pipeline or regime tasks.',
      'Verify VIX/breadth data feeds are accessible (yfinance for ^VIX, ^VIX3M).',
      'Regime computation runs as part of the nightly pipeline. Click "Compute Market Regime" in Safe Actions to trigger manually.',
      'If breadth data (% >200D, % >50D) is off, ensure the nightly indicator pipeline ran successfully first.',
    ],
    threshold: () => 'Regime data must be less than 48 hours old',
    metricSummary: (dim) => [
      { label: 'State', value: String(dim.regime_state ?? '—'), ok: !!dim.regime_state },
      { label: 'Score', value: String(dim.composite_score ?? '—'), ok: !!dim.composite_score },
      { label: 'Age', value: `${Number(dim.age_hours ?? 0).toFixed(1)}h`, ok: Number(dim.age_hours ?? 0) < 48 },
    ],
  },
  audit: {
    what: 'Market audit detected that daily or snapshot fill percentages are below acceptable thresholds for the tracked universe.',
    steps: [
      'Auto-ops checks health every 15 minutes and triggers remediation automatically.',
      'For low daily fill: run "Backfill Daily Coverage (Tracked)" from Backfill Actions.',
      'For low snapshot fill: open Operator Actions > Advanced Controls and run "Backfill Snapshot History (period)".',
      'If specific symbols are listed as missing, verify they are still tracked in Market > Tracked.',
    ],
    threshold: (t) =>
      `Daily fill >= ${t.audit_daily_fill_pct_min ?? 95}%, snapshot fill >= ${t.audit_snapshot_fill_pct_min ?? 90}%`,
    metricSummary: (dim) => [
      { label: 'Daily fill', value: `${Number(dim.daily_fill_pct ?? 0).toFixed(1)}%`, ok: Number(dim.daily_fill_pct ?? 0) >= 95 },
      { label: 'Snapshot fill', value: `${Number(dim.snapshot_fill_pct ?? 0).toFixed(1)}%`, ok: Number(dim.snapshot_fill_pct ?? 0) >= 90 },
      { label: 'Tracked total', value: String(dim.tracked_total ?? '—'), ok: true },
    ],
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
            redDims.map(([key, dimData]) => {
              const entry = RUNBOOK[key];
              if (!entry) return null;

              const dim = dimData as unknown as Record<string, unknown>;
              let steps: string[];
              try {
                steps = entry.contextualSteps ? entry.contextualSteps(dim) : entry.steps;
              } catch {
                steps = entry.steps;
              }

              const metrics = entry.metricSummary ? entry.metricSummary(dim) : null;

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
                    <strong>Fix:</strong>
                  </Text>
                  <Box as="ol" pl={4} mb={1}>
                    {steps.map((step, idx) => (
                      <Box as="li" key={idx} fontSize="xs" color="fg.default" mb="2px">
                        {step}
                      </Box>
                    ))}
                  </Box>
                  {metrics && (
                    <HStack gap={3} flexWrap="wrap" mt={1} mb={1}>
                      {metrics.map((m) => (
                        <Badge
                          key={m.label}
                          size="sm"
                          variant="subtle"
                          colorPalette={m.ok ? 'green' : 'red'}
                        >
                          {m.label}: {m.value}
                        </Badge>
                      ))}
                    </HStack>
                  )}
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
