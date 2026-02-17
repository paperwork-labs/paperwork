import React from "react";
import { Box, SimpleGrid, Text, Code, HStack } from "@chakra-ui/react";
import { useColorMode } from "../theme/colorMode";

export default {
  title: "DesignSystem/Tokens",
};

const Swatch = ({ name, value }: { name: string; value: string }) => (
  <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" overflow="hidden" bg="bg.panel">
    <Box h="44px" bg={value} />
    <Box p={3}>
      <Text fontSize="sm" color="fg.default">{name}</Text>
      <Code fontSize="xs">{value}</Code>
    </Box>
  </Box>
);

export const SemanticTokens = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const tokens = [
    ["bg.canvas", "bg.canvas"],
    ["bg.panel", "bg.panel"],
    ["bg.card", "bg.card"],
    ["bg.input", "bg.input"],
    ["fg.default", "fg.default"],
    ["fg.muted", "fg.muted"],
    ["fg.subtle", "fg.subtle"],
    ["border.subtle", "border.subtle"],
    ["border.strong", "border.strong"],
    ["status.success", "status.success"],
    ["status.warning", "status.warning"],
    ["status.danger", "status.danger"],
    ["status.info", "status.info"],
  ] as const;

  return (
    <Box p={6}>
      <HStack justify="space-between" mb={5}>
        <Box>
          <Text fontSize="lg" fontWeight="semibold" color="fg.default">Semantic tokens</Text>
          <Text fontSize="sm" color="fg.muted">Mode: {colorMode}</Text>
        </Box>
        <Box
          as="button"
          onClick={toggleColorMode}
          style={{
            padding: "8px 12px",
            borderRadius: 10,
            border: "1px solid rgba(255,255,255,0.12)",
          }}
        >
          Toggle mode
        </Box>
      </HStack>

      <SimpleGrid columns={{ base: 1, sm: 2, md: 3 }} gap={4}>
        {tokens.map(([name, value]) => (
          <Swatch key={name} name={name} value={value} />
        ))}
      </SimpleGrid>
    </Box>
  );
};

export const AxiomFolioPalette = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const brandTokens = [
    ["brand.50", "brand.50"],
    ["brand.100", "brand.100"],
    ["brand.200", "brand.200"],
    ["brand.300", "brand.300"],
    ["brand.400 (dark primary)", "brand.400"],
    ["brand.500", "brand.500"],
    ["brand.600 (secondary)", "brand.600"],
    ["brand.700 (light primary)", "brand.700"],
    ["brand.800", "brand.800"],
    ["brand.900", "brand.900"],
    ["focusRing", "focusRing"],
  ] as const;

  return (
    <Box p={6}>
      <HStack justify="space-between" mb={5}>
        <Box>
          <Text fontSize="lg" fontWeight="semibold" color="fg.default">AxiomFolio palette</Text>
          <Text fontSize="sm" color="fg.muted">Mode: {colorMode}</Text>
        </Box>
        <Box
          as="button"
          onClick={toggleColorMode}
          style={{
            padding: "8px 12px",
            borderRadius: 10,
            border: "1px solid rgba(255,255,255,0.12)",
          }}
        >
          Toggle mode
        </Box>
      </HStack>

      <SimpleGrid columns={{ base: 1, sm: 2, md: 3 }} gap={4}>
        {brandTokens.map(([name, value]) => (
          <Swatch key={name} name={name} value={value} />
        ))}
      </SimpleGrid>
    </Box>
  );
};
