import React from "react";
import { Box, SimpleGrid, Text, HStack, VStack, Code, Image } from "@chakra-ui/react";
import { useColorMode } from "../theme/colorMode";
import axiomfolioLogo from "../assets/logos/axiomfolio.svg";

export default {
  title: "Brand/AxiomFolio",
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

export const Overview = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const palette = [
    ["Primary 500", "brand.500"],
    ["Primary 400", "brand.400"],
    ["Primary 600", "brand.600"],
    ["Canvas", "bg.canvas"],
    ["Panel", "bg.panel"],
    ["Text", "fg.default"],
  ] as const;

  return (
    <Box p={6}>
      <HStack justify="space-between" mb={6}>
        <Box>
          <Text fontSize="lg" fontWeight="semibold" color="fg.default">AxiomFolio brand</Text>
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

      <VStack align="stretch" gap={8}>
        <Box display="flex" gap={4} alignItems="center">
          <Image src={axiomfolioLogo} alt="AxiomFolio logo" boxSize="56px" />
          <Box>
            <Text fontSize="2xl" fontWeight="semibold" color="fg.default">AxiomFolio</Text>
            <Text fontSize="sm" color="fg.muted">Placeholder logo and wordmark for early branding.</Text>
          </Box>
        </Box>

        <Box>
          <Text fontSize="sm" fontWeight="semibold" color="fg.subtle" textTransform="uppercase" mb={3}>
            Palette
          </Text>
          <SimpleGrid columns={{ base: 1, sm: 2, md: 3 }} gap={4}>
            {palette.map(([name, value]) => (
              <Swatch key={name} name={name} value={value} />
            ))}
          </SimpleGrid>
        </Box>

        <Box>
          <Text fontSize="sm" fontWeight="semibold" color="fg.subtle" textTransform="uppercase" mb={3}>
            Typography
          </Text>
          <VStack align="stretch" gap={2}>
            <Text fontSize="2xl" fontWeight="semibold" fontFamily="heading" color="fg.default">
              AxiomFolio: Clarity for modern portfolios
            </Text>
            <Text fontSize="md" fontFamily="body" color="fg.muted">
              Product UI uses the shared Chakra v3 system for consistency, scale, and accessibility.
            </Text>
          </VStack>
        </Box>
      </VStack>
    </Box>
  );
};
