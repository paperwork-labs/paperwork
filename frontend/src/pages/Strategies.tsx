import React from 'react';
import { Box, Text, CardRoot, CardBody, VStack, Badge } from '@chakra-ui/react';

const Strategies: React.FC = () => {
  return (
    <Box>
      <Text fontSize="lg" fontWeight="semibold" mb={3} color="fg.default">
        Strategies
      </Text>

      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
        <CardBody>
          <VStack align="start" gap={2}>
            <Badge colorPalette="blue">Coming Soon</Badge>
            <Text color="fg.muted">
              The strategy engine is being rebuilt with a composable rules system. Define entry, exit, and trim rules using computed market indicators.
            </Text>
          </VStack>
        </CardBody>
      </CardRoot>
    </Box>
  );
};

export default Strategies;


