import React from 'react';
import { Box, HStack, Text, Badge } from '@chakra-ui/react';
import { STAGE_COLORS } from '../../constants/chart';

const STAGES = ['1', '2A', '2B', '2C', '3', '4'] as const;

export interface StageBarProps {
  counts: Record<string, number>;
  total: number;
}

const StageBar: React.FC<StageBarProps> = ({ counts, total }) => {
  if (total === 0) {
    return (
      <Text fontSize="xs" color="fg.muted">
        No data
      </Text>
    );
  }
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
          return (
            <Box
              key={s}
              w={`${pct}%`}
              bg={`${palette}.400`}
              display="flex"
              alignItems="center"
              justifyContent="center"
              aria-label={`Stage ${s}: ${count} positions, ${pct.toFixed(0)}%`}
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
              variant="subtle"
              colorPalette={STAGE_COLORS[s] ?? 'gray'}
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
