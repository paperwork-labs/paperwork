import React from 'react';
import { Box, HStack, Text, Badge } from '@chakra-ui/react';
import { STAGE_COLORS } from '../../constants/chart';

/** Display order: 10 sub-stages, then legacy rollup labels (1–4) for older snapshot data. */
const STAGES = [
  '1A', '1B', '2A', '2B', '2B(RS-)', '2C', '3A', '3B', '4A', '4B', '4C',
  '1', '2', '3', '4',
] as const;

export interface StageBarProps {
  counts: Record<string, number>;
  total?: number;
  onClick?: (stage: string) => void;
  activeStage?: string | null;
}

const StageBar: React.FC<StageBarProps> = ({ counts, total: totalProp, onClick, activeStage }) => {
  const total = totalProp ?? Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) {
    return (
      <Text fontSize="xs" color="fg.muted">
        No data
      </Text>
    );
  }
  const isInteractive = !!onClick;
  const distributionLabel = `Stage distribution: ${STAGES.map((s) => `${s}: ${counts[s] ?? 0}`).join(', ')}`;
  return (
    <Box>
      <Box
        display="flex"
        h="24px"
        borderRadius="md"
        overflow="hidden"
        role="img"
        aria-label={distributionLabel}
      >
        {STAGES.map((s) => {
          const count = counts[s] ?? 0;
          const pct = (count / total) * 100;
          if (pct === 0) return null;
          const palette = STAGE_COLORS[s] ?? 'gray';
          const isActive = activeStage === s;
          return (
            <Box
              key={s}
              w={`${pct}%`}
              bg={`${palette}.400`}
              display="flex"
              alignItems="center"
              justifyContent="center"
              aria-label={`Stage ${s}: ${count} positions, ${pct.toFixed(0)}%`}
              cursor={isInteractive ? 'pointer' : undefined}
              onClick={isInteractive ? () => onClick(s) : undefined}
              opacity={activeStage && !isActive ? 0.45 : 1}
              transition="opacity 200ms ease"
              _hover={isInteractive ? { opacity: 0.85 } : undefined}
            >
              {pct > 4 && (
                <Text fontSize="10px" fontWeight="bold" color="white">
                  {s}
                </Text>
              )}
            </Box>
          );
        })}
      </Box>
      <HStack gap={2} mt={1} flexWrap="wrap">
        {STAGES.map((s) => {
          const count = counts[s] ?? 0;
          return (
            <Badge
              key={s}
              size="sm"
              variant={activeStage === s ? 'solid' : 'subtle'}
              colorPalette={STAGE_COLORS[s] ?? 'gray'}
              cursor={isInteractive ? 'pointer' : undefined}
              onClick={isInteractive ? () => onClick(s) : undefined}
              transition="all 200ms ease"
            >
              {s}: {count} ({total > 0 ? ((count / total) * 100).toFixed(0) : 0}%)
            </Badge>
          );
        })}
      </HStack>
    </Box>
  );
};

export default StageBar;
