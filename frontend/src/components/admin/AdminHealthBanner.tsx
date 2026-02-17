import React from 'react';
import { Box, Badge, HStack, Text } from '@chakra-ui/react';
import type { AdminHealthResponse } from '../../types/adminHealth';
import { formatDateTime } from '../../utils/format';

interface Props {
  health: AdminHealthResponse | null;
  timezone?: string;
}

const STATUS_PALETTE: Record<string, string> = {
  green: 'green',
  yellow: 'orange',
  red: 'red',
};

const STATUS_TEXT_COLOR: Record<string, string> = {
  green: 'status.success',
  yellow: 'status.warning',
  red: 'status.danger',
};

const AdminHealthBanner: React.FC<Props> = ({ health, timezone }) => {
  if (!health) return null;

  const palette = STATUS_PALETTE[health.composite_status] ?? 'gray';
  const dims = health.dimensions;

  return (
    <Box
      mb={4}
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="lg"
      p={3}
      bg="bg.muted"
    >
      <HStack justify="space-between" align="center" flexWrap="wrap" gap={2} mb={2}>
        <HStack gap={2} align="center">
          <Text fontSize="sm" fontWeight="semibold">System Health</Text>
          <Badge variant="subtle" colorPalette={palette}>
            {health.composite_status.toUpperCase()}
          </Badge>
        </HStack>
        <Text fontSize="xs" color="fg.muted">
          Checked: {formatDateTime(health.checked_at, timezone)}
        </Text>
      </HStack>
      <Text fontSize="xs" color="fg.muted" mb={2}>
        {health.composite_reason}
      </Text>
      <HStack gap={2} flexWrap="wrap">
        {Object.entries(dims).map(([key, dim]) => {
          const dimPalette = STATUS_PALETTE[dim.status] ?? 'gray';
          return (
            <Badge
              key={key}
              variant="subtle"
              colorPalette={dimPalette}
            >
              <Box
                as="span"
                display="inline-block"
                w="6px"
                h="6px"
                borderRadius="full"
                bg={STATUS_TEXT_COLOR[dim.status] ?? 'fg.muted'}
                mr={1}
              />
              {key.replace('_', ' ')}
            </Badge>
          );
        })}
      </HStack>
    </Box>
  );
};

export default AdminHealthBanner;
