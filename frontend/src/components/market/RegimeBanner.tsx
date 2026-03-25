import React from 'react';
import { Box, HStack, Text, Badge, VStack } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../../services/api';
import { REGIME_HEX } from '../../constants/chart';

interface RegimeData {
  regime_state: string;
  composite_score: number;
  as_of_date: string;
  vix_spot: number | null;
  vix3m_vix_ratio: number | null;
  vvix_vix_ratio: number | null;
  nh_nl: number | null;
  pct_above_200d: number | null;
  pct_above_50d: number | null;
  cash_floor_pct: number | null;
  max_equity_exposure_pct: number | null;
  regime_multiplier: number | null;
}

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull',
  R2: 'Bull Extended',
  R3: 'Chop',
  R4: 'Bear Rally',
  R5: 'Bear',
};

const RegimeBanner: React.FC = () => {
  const { data, isPending } = useQuery({
    queryKey: ['regime-current'],
    queryFn: async () => {
      const resp = await marketDataApi.getCurrentRegime();
      return resp?.data?.regime as RegimeData | null;
    },
    refetchInterval: 5 * 60 * 1000,
    staleTime: 2 * 60 * 1000,
  });

  if (isPending || !data) {
    return (
      <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.card" mb={3}>
        <Text fontSize="xs" color="fg.muted">Loading regime data...</Text>
      </Box>
    );
  }

  const color = REGIME_HEX[data.regime_state] || '#718096';
  const label = REGIME_LABELS[data.regime_state] || data.regime_state;

  return (
    <Box
      borderWidth="2px"
      borderColor={color}
      borderRadius="lg"
      p={3}
      bg="bg.card"
      mb={3}
    >
      <HStack justify="space-between" flexWrap="wrap" gap={2}>
        <HStack gap={3}>
          <HStack gap={2}>
            <Box w="14px" h="14px" borderRadius="sm" bg={color} flexShrink={0} />
            <Text fontSize="md" fontWeight="bold">
              {data.regime_state}
            </Text>
            <Badge
              variant="subtle"
              size="sm"
              style={{ backgroundColor: `${color}22`, color }}
            >
              {label}
            </Badge>
          </HStack>
          <Text fontSize="sm" color="fg.muted">
            Composite: <Text as="span" fontWeight="semibold" color="fg.default">{data.composite_score?.toFixed(1)}</Text>
          </Text>
        </HStack>

        <HStack gap={4} flexWrap="wrap">
          {data.vix_spot != null && (
            <VStack gap={0} align="center">
              <Text fontSize="10px" color="fg.muted">VIX</Text>
              <Text fontSize="xs" fontWeight="semibold">{data.vix_spot.toFixed(1)}</Text>
            </VStack>
          )}
          {data.vix3m_vix_ratio != null && (
            <VStack gap={0} align="center">
              <Text fontSize="10px" color="fg.muted">VIX3M/VIX</Text>
              <Text fontSize="xs" fontWeight="semibold">{data.vix3m_vix_ratio.toFixed(2)}</Text>
            </VStack>
          )}
          {data.nh_nl != null && (
            <VStack gap={0} align="center">
              <Text fontSize="10px" color="fg.muted">NH−NL</Text>
              <Text fontSize="xs" fontWeight="semibold">{data.nh_nl}</Text>
            </VStack>
          )}
          {data.pct_above_200d != null && (
            <VStack gap={0} align="center">
              <Text fontSize="10px" color="fg.muted">&gt;200D</Text>
              <Text fontSize="xs" fontWeight="semibold">{data.pct_above_200d.toFixed(0)}%</Text>
            </VStack>
          )}
          {data.pct_above_50d != null && (
            <VStack gap={0} align="center">
              <Text fontSize="10px" color="fg.muted">&gt;50D</Text>
              <Text fontSize="xs" fontWeight="semibold">{data.pct_above_50d.toFixed(0)}%</Text>
            </VStack>
          )}
          {data.regime_multiplier != null && (
            <VStack gap={0} align="center">
              <Text fontSize="10px" color="fg.muted">Size Mult</Text>
              <Text fontSize="xs" fontWeight="semibold">{data.regime_multiplier.toFixed(2)}×</Text>
            </VStack>
          )}
          {data.max_equity_exposure_pct != null && (
            <VStack gap={0} align="center">
              <Text fontSize="10px" color="fg.muted">Max Eq</Text>
              <Text fontSize="xs" fontWeight="semibold">{data.max_equity_exposure_pct.toFixed(0)}%</Text>
            </VStack>
          )}
        </HStack>
      </HStack>
    </Box>
  );
};

export default RegimeBanner;
