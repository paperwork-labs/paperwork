import React from 'react';
import { Box, Text, CardRoot, CardBody, VStack, Badge } from '@chakra-ui/react';

const StrategiesManager: React.FC = () => {
  return (
    <Box>
      <Text fontSize="lg" fontWeight="semibold" mb={3} color="fg.default">
        Strategy Manager
      </Text>

      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
        <CardBody>
          <VStack align="start" gap={2}>
            <Badge colorPalette="blue">Coming Soon</Badge>
            <Text color="fg.muted">
              The strategy builder will let you compose rules from market indicators like Weinstein stage, RS Mansfield, TD Sequential, and more.
            </Text>
          </VStack>
        </CardBody>
      </CardRoot>
    </Box>
  );
};

export default StrategiesManager;


