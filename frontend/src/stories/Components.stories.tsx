import React from "react";
import { Box, Button, Input, InputGroup, IconButton, VStack, Text, HStack } from "@chakra-ui/react";
import { FiEye } from "react-icons/fi";
import AppCard from "../components/ui/AppCard";
import FormField from "../components/ui/FormField";
import StatCard from "../components/shared/StatCard";
import { useColorMode } from "../theme/colorMode";

export default {
  title: "DesignSystem/Components",
};

export const Basics = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  return (
    <Box p={6}>
      <HStack justify="space-between" mb={5}>
        <Box>
          <Text fontSize="lg" fontWeight="semibold" color="fg.default">Components</Text>
          <Text fontSize="sm" color="fg.muted">Mode: {colorMode}</Text>
        </Box>
        <Button variant="outline" onClick={toggleColorMode}>Toggle mode</Button>
      </HStack>

      <AppCard maxW="520px">
        <VStack align="stretch" gap={4}>
          <Text fontSize="md" fontWeight="semibold" color="fg.default">Card</Text>
          <FormField label="Email" required helperText="We’ll never share your email.">
            <Input placeholder="you@example.com" />
          </FormField>
          <FormField label="Password" required>
            <InputGroup
              endElement={
                <IconButton aria-label="Show" size="sm" variant="ghost" color="fg.muted">
                  <FiEye />
                </IconButton>
              }
            >
              <Input placeholder="••••••••" type="password" />
            </InputGroup>
          </FormField>
          <HStack justify="flex-end">
            <Button variant="outline">Cancel</Button>
            <Button bg="brand.500" _hover={{ bg: "brand.400" }}>Continue</Button>
          </HStack>
        </VStack>
      </AppCard>

      <Box mt={8} maxW="520px">
        <Text fontSize="md" fontWeight="semibold" color="fg.default" mb={3}>StatCard (full)</Text>
        <AppCard>
          <VStack align="stretch" gap={3}>
            <StatCard variant="full" label="Tracked Symbols" value={512} helpText="Universe size" />
            <StatCard variant="full" label="Daily Coverage %" value="98.2%" helpText="502 / 511 bars" trend="up" color="green.400" />
            <StatCard variant="full" label="5m Coverage %" value="92.1%" helpText="470 / 511 bars" trend="down" color="red.400" />
          </VStack>
        </AppCard>
      </Box>
    </Box>
  );
};


