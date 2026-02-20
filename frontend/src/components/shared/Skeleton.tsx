import React from 'react';
import { Box, Skeleton, VStack, HStack } from '@chakra-ui/react';

/** Matches StatCard dimensions with pulsing placeholder. */
export const StatCardSkeleton: React.FC = () => (
  <Box p={4} borderRadius="xl" borderWidth="1px" borderColor="border.subtle" bg="bg.card">
    <VStack align="stretch" gap={2}>
      <Skeleton height="14px" width="60%" />
      <Skeleton height="24px" width="80%" />
    </VStack>
  </Box>
);

/** Rows of pulsing bars matching table column widths. */
export const TableSkeleton: React.FC<{ rows?: number; cols?: number }> = ({ rows = 8, cols = 5 }) => (
  <VStack align="stretch" gap={2}>
    {Array.from({ length: rows }).map((_, i) => (
      <HStack key={i} gap={3}>
        {Array.from({ length: cols }).map((_, j) => (
          <Skeleton key={j} height="20px" flex={j === 0 ? 2 : 1} />
        ))}
      </HStack>
    ))}
  </VStack>
);

/** Rectangle with pulsing gradient for chart placeholders. */
export const ChartSkeleton: React.FC = () => (
  <Box borderRadius="lg" overflow="hidden" bg="bg.subtle" minH="200px">
    <Skeleton height="100%" width="100%" />
  </Box>
);
