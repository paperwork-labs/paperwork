import React from "react";
import { Box, SimpleGrid, Text, HStack, VStack, Code, Image } from "@chakra-ui/react";
import { useColorMode } from "../theme/colorMode";
import AppLogo from "../components/ui/AppLogo";
import lockupLogo from "../assets/logos/axiomfolio-lockup.svg";
import lockupDarkLogo from "../assets/logos/axiomfolio-lockup-dark.svg";
import lockupSurfaceLogo from "../assets/logos/axiomfolio-lockup-surface.svg";
import starIcon from "../assets/logos/axiomfolio-icon-star.svg";

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
  const brandTokens = [
    ["brand.700 (primary)", "brand.700"],
    ["brand.600 (secondary)", "brand.600"],
    ["brand.500", "brand.500"],
    ["brand.400 (dark primary)", "brand.400"],
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
        {/* --- Brand mark (the logo) --- */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" color="fg.subtle" textTransform="uppercase" mb={3}>
            Brand mark (the logo)
          </Text>
          <Text fontSize="xs" color="fg.muted" mb={4}>
            The four-point star IS the logo. It renders via {"<AppLogo />"} and uses fixed colors that work on both light and dark backgrounds (no theme switching).
          </Text>
          <HStack gap={6} align="end">
            <VStack gap={1}>
              <AppLogo size={64} />
              <Text fontSize="xs" color="fg.subtle">64px</Text>
            </VStack>
            <VStack gap={1}>
              <AppLogo size={48} />
              <Text fontSize="xs" color="fg.subtle">48px</Text>
            </VStack>
            <VStack gap={1}>
              <AppLogo size={36} />
              <Text fontSize="xs" color="fg.subtle">36px</Text>
            </VStack>
            <VStack gap={1}>
              <AppLogo size={24} />
              <Text fontSize="xs" color="fg.subtle">24px</Text>
            </VStack>
          </HStack>
        </Box>

        {/* --- Product name alongside mark --- */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" color="fg.subtle" textTransform="uppercase" mb={3}>
            Mark + product name (usage examples)
          </Text>
          <Text fontSize="xs" color="fg.muted" mb={4}>
            "AxiomFolio" is the product name — not part of the logo. Render it as separate text alongside the mark.
          </Text>
          <VStack align="start" gap={4}>
            <HStack gap="14px" align="center">
              <AppLogo size={52} />
              <Text fontSize="md" fontWeight="semibold" color="fg.default" letterSpacing="-0.01em">AxiomFolio</Text>
            </HStack>
            <HStack gap="10px" align="center">
              <AppLogo size={36} />
              <Text fontSize="sm" fontWeight="semibold" color="fg.default" letterSpacing="-0.01em">AxiomFolio</Text>
            </HStack>
          </VStack>
        </Box>

        {/* --- Static SVG assets --- */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" color="fg.subtle" textTransform="uppercase" mb={3}>
            Static SVG assets
          </Text>
          <Text fontSize="xs" color="fg.muted" mb={4}>
            For external use (docs, marketing, social). The lockups bake in the product name for contexts where the React component isn't available.
          </Text>
          <VStack align="stretch" gap={4}>
            <HStack gap={4} align="start">
              <Box p={4} borderRadius="lg" borderWidth="1px" borderColor="border.subtle" bg="white" display="inline-block">
                <Image src={lockupLogo} alt="Lockup (light)" height="48px" />
              </Box>
              <Box p={4} borderRadius="lg" bg="#0F172A" display="inline-block">
                <Image src={lockupDarkLogo} alt="Lockup (dark)" height="48px" />
              </Box>
            </HStack>
            <Box p={4} borderRadius="lg" bg="#0F172A" display="inline-block">
              <Image src={lockupSurfaceLogo} alt="Lockup on surface chip" height="56px" />
            </Box>
            <HStack gap={4}>
              <Box p={3} borderRadius="lg" borderWidth="1px" borderColor="border.subtle" bg="white" display="inline-block">
                <Image src={starIcon} alt="Star mark (light)" boxSize="48px" />
              </Box>
              <Box p={3} borderRadius="lg" bg="#0F172A" display="inline-block">
                <Image src={starIcon} alt="Star mark (dark)" boxSize="48px" />
              </Box>
            </HStack>
          </VStack>
        </Box>

        {/* --- Palette --- */}
        <Box>
          <Text fontSize="sm" fontWeight="semibold" color="fg.subtle" textTransform="uppercase" mb={3}>
            Brand palette
          </Text>
          <SimpleGrid columns={{ base: 1, sm: 2, md: 3 }} gap={4}>
            {brandTokens.map(([name, value]) => (
              <Swatch key={name} name={name} value={value} />
            ))}
          </SimpleGrid>
        </Box>

        <Box>
          <Text fontSize="sm" fontWeight="semibold" color="fg.subtle" textTransform="uppercase" mb={3}>
            Status colors
          </Text>
          <SimpleGrid columns={{ base: 1, sm: 2, md: 4 }} gap={4}>
            <Swatch name="status.success" value="status.success" />
            <Swatch name="status.warning" value="status.warning" />
            <Swatch name="status.danger" value="status.danger" />
            <Swatch name="status.info" value="status.info" />
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
