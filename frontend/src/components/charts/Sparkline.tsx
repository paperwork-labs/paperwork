import React from 'react';
import { Box, HStack } from '@chakra-ui/react';

type SparklineProps = {
  values?: number[];
  max?: number;
  color?: string;
  height?: number;
};

const Sparkline: React.FC<SparklineProps> = ({ values = [], max, color = 'brand.400', height = 32 }) => {
  if (!values.length) {
    return <Box fontSize="xs" color="fg.muted">No samples</Box>;
  }
  const safeMax = typeof max === 'number' ? max : Math.max(...values, 1);
  return (
    <HStack align="flex-end" gap={0.5} h={`${height}px`}>
      {values.map((value, idx) => {
        const normalized = safeMax ? Math.max((value / safeMax) * 100, 5) : 0;
        return (
          <Box
            key={`${value}-${idx}`}
            w="4px"
            borderRadius="sm"
            bg={color}
            minH="3px"
            height={`${normalized}%`}
          />
        );
      })}
    </HStack>
  );
};

export default Sparkline;

