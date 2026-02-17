import React from 'react';
import { Badge, Box, Heading, HStack, Stack, Text } from '@chakra-ui/react';
import type {
  CoverageAction,
  CoverageBucketGroup,
  CoverageHeroMeta,
  CoverageKpi,
  CoverageSparkline,
} from '../../utils/coverage';

export interface CoverageSummaryCardProps {
  hero: CoverageHeroMeta;
  status?: any;
  showUpdated?: boolean;
  children?: React.ReactNode;
}

/**
 * Read-only coverage summary container.
 * Keep this dependency-light so CI doesn't depend on chart libs/DOM quirks.
 */
export const CoverageSummaryCard: React.FC<CoverageSummaryCardProps> = ({
  hero,
  showUpdated = true,
  children,
}) => {
  const label = String(hero.statusLabel || '').toUpperCase() || '—';
  const palette =
    hero.statusColor === 'green'
      ? 'green'
      : hero.statusColor === 'yellow'
        ? 'orange'
        : hero.statusColor === 'red'
          ? 'red'
          : 'gray';
  return (
    <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
      <Stack gap={3}>
        <Box>
          <HStack justify="space-between" align="start" gap={3} flexWrap="wrap">
            <Box>
              <Heading size="sm">Coverage</Heading>
              {showUpdated && hero && hero.updatedRelative && hero.updatedDisplay ? (
                <Text fontSize="xs" color="fg.muted">
                  Updated {hero.updatedRelative} ({hero.updatedDisplay})
                </Text>
              ) : null}
            </Box>
            <Badge variant="subtle" colorPalette={palette}>
              {label}
            </Badge>
          </HStack>
          {hero.summary ? (
            <Text mt={1} fontSize="sm" color="fg.muted">
              {hero.summary}
            </Text>
          ) : null}
          {hero.warningBanner ? (
            <Box mt={2} borderWidth="1px" borderColor="border.subtle" borderRadius="md" p={3} bg="bg.muted">
              <Text fontWeight="semibold">{hero.warningBanner.title}</Text>
              {hero.warningBanner.description ? (
                <Text fontSize="sm" color="fg.muted">
                  {hero.warningBanner.description}
                </Text>
              ) : null}
            </Box>
          ) : null}
        </Box>

        {children ? <Box>{children}</Box> : null}
      </Stack>
    </Box>
  );
};

export interface CoverageKpiGridProps {
  kpis: CoverageKpi[];
  variant?: 'compact' | 'stat' | string;
}

export const CoverageKpiGrid: React.FC<CoverageKpiGridProps> = ({ kpis }) => {
  return (
    <Box>
      <Heading size="xs" mb={2}>
        KPIs
      </Heading>
      <Box display="grid" gridTemplateColumns="repeat(auto-fit, minmax(160px, 1fr))" gap={3}>
        {kpis.map((kpi) => (
          <Box key={kpi.id} borderWidth="1px" borderRadius="md" p={3}>
            <Text fontSize="xs" color="fg.subtle">
              {kpi.label}
            </Text>
            <Text fontSize="lg" fontWeight="semibold">
              {kpi.value ?? '—'}
              {kpi.unit ? ` ${kpi.unit}` : ''}
            </Text>
            {kpi.help ? (
              <Text fontSize="xs" color="fg.muted">
                {kpi.help}
              </Text>
            ) : null}
          </Box>
        ))}
      </Box>
    </Box>
  );
};

export interface CoverageTrendGridProps {
  sparkline: CoverageSparkline;
}

export const CoverageTrendGrid: React.FC<CoverageTrendGridProps> = ({ sparkline }) => {
  const daily = sparkline.daily_pct?.[sparkline.daily_pct.length - 1];
  const m5 = sparkline.m5_pct?.[sparkline.m5_pct.length - 1];

  return (
    <Box mt={4}>
      <Heading size="xs" mb={2}>
        Trend (latest)
      </Heading>
      <Box display="grid" gridTemplateColumns="repeat(auto-fit, minmax(160px, 1fr))" gap={3}>
        <Box borderWidth="1px" borderRadius="md" p={3}>
          <Text fontSize="xs" color="fg.subtle">
            Daily coverage %
          </Text>
          <Text fontSize="lg" fontWeight="semibold">
            {typeof daily === 'number' ? daily.toFixed(1) : '—'}%
          </Text>
        </Box>
        <Box borderWidth="1px" borderRadius="md" p={3}>
          <Text fontSize="xs" color="fg.subtle">
            5m coverage %
          </Text>
          <Text fontSize="lg" fontWeight="semibold">
            {typeof m5 === 'number' ? m5.toFixed(1) : '—'}%
          </Text>
        </Box>
      </Box>
    </Box>
  );
};

export interface CoverageBucketsGridProps {
  groups: CoverageBucketGroup[];
}

export const CoverageBucketsGrid: React.FC<CoverageBucketsGridProps> = ({ groups }) => {
  return (
    <Box mt={4}>
      <Heading size="xs" mb={2}>
        Freshness Buckets
      </Heading>
      <Box display="grid" gridTemplateColumns="repeat(auto-fit, minmax(240px, 1fr))" gap={3}>
        {groups.map((group) => (
          <Box key={group.interval} borderWidth="1px" borderRadius="md" p={3}>
            <Text fontWeight="semibold" mb={2}>
              {group.title}
            </Text>
            <Stack gap={1}>
              {group.buckets.map((b) => (
                <Box key={b.label} display="flex" justifyContent="space-between">
                  <Text fontSize="sm" color="fg.subtle">
                    {b.label}
                  </Text>
                  <Text fontSize="sm" fontWeight="semibold">
                    {b.count}
                  </Text>
                </Box>
              ))}
            </Stack>
          </Box>
        ))}
      </Box>
    </Box>
  );
};

export interface CoverageActionsListProps {
  actions: CoverageAction[];
  onRun: (taskName: string, label?: string) => Promise<void> | void;
  buttonRenderer?: (action: CoverageAction, handleClick: () => void) => React.ReactNode;
}

export const CoverageActionsList: React.FC<CoverageActionsListProps> = ({
  actions,
  onRun,
  buttonRenderer,
}) => {
  return (
    <Stack gap={2}>
      {actions.map((action) => {
        const handleClick = () => void onRun(action.task_name, action.label);
        return (
          <Box
            key={action.task_name}
            borderWidth="1px"
            borderRadius="md"
            p={3}
            display="flex"
            alignItems="center"
            justifyContent="space-between"
            gap={3}
          >
            <Box>
              <Text fontWeight="semibold">{action.label}</Text>
              {action.description ? (
                <Text fontSize="sm" color="fg.subtle">
                  {action.description}
                </Text>
              ) : null}
            </Box>
            <Box>
              {buttonRenderer ? (
                buttonRenderer(action, handleClick)
              ) : (
                <button disabled={Boolean(action.disabled)} onClick={handleClick}>
                  Run
                </button>
              )}
            </Box>
          </Box>
        );
      })}
    </Stack>
  );
};


