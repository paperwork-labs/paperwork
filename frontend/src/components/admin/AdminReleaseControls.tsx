import React from 'react';
import { Box, Badge, Button, HStack, Text } from '@chakra-ui/react';

interface Props {
  marketOnlyMode: boolean;
  portfolioEnabled: boolean;
  strategyEnabled: boolean;
  toggling: boolean;
  onToggleMarketOnly: () => void;
  onTogglePortfolio: () => void;
  onToggleStrategy: () => void;
}

const AdminReleaseControls: React.FC<Props> = ({
  marketOnlyMode,
  portfolioEnabled,
  strategyEnabled,
  toggling,
  onToggleMarketOnly,
  onTogglePortfolio,
  onToggleStrategy,
}) => {
  return (
    <Box mb={3} borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={3} bg="bg.muted">
      <Text fontSize="sm" fontWeight="semibold" color="fg.default" mb={1}>
        Release Controls
      </Text>
      <Text fontSize="xs" color="fg.muted" mb={3}>
        Keep market-only enabled while building. Disable market-only and enable sections when ready.
      </Text>
      <HStack justify="space-between" align="center" flexWrap="wrap" gap={3} mb={2}>
        <Text fontSize="sm">Market-only mode</Text>
        <HStack gap={2}>
          <Badge colorScheme={marketOnlyMode ? 'green' : 'gray'} variant="subtle">
            {marketOnlyMode ? 'ON' : 'OFF'}
          </Badge>
          <Button size="xs" variant="outline" loading={toggling} onClick={onToggleMarketOnly}>
            {marketOnlyMode ? 'Disable' : 'Enable'}
          </Button>
        </HStack>
      </HStack>
      <HStack justify="space-between" align="center" flexWrap="wrap" gap={3} mb={2}>
        <Text fontSize="sm">Portfolio section</Text>
        <HStack gap={2}>
          <Badge colorScheme={portfolioEnabled ? 'green' : 'gray'} variant="subtle">
            {portfolioEnabled ? 'ENABLED' : 'DISABLED'}
          </Badge>
          <Button size="xs" variant="outline" loading={toggling} onClick={onTogglePortfolio}>
            {portfolioEnabled ? 'Disable' : 'Enable'}
          </Button>
        </HStack>
      </HStack>
      <HStack justify="space-between" align="center" flexWrap="wrap" gap={3}>
        <Text fontSize="sm">Strategy section</Text>
        <HStack gap={2}>
          <Badge colorScheme={strategyEnabled ? 'green' : 'gray'} variant="subtle">
            {strategyEnabled ? 'ENABLED' : 'DISABLED'}
          </Badge>
          <Button size="xs" variant="outline" loading={toggling} onClick={onToggleStrategy}>
            {strategyEnabled ? 'Disable' : 'Enable'}
          </Button>
        </HStack>
      </HStack>
    </Box>
  );
};

export default AdminReleaseControls;
