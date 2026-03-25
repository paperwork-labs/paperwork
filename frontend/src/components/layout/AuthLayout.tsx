import React from 'react';
import { Box, Text, type BoxProps } from '@chakra-ui/react';
import AppLogo from '../ui/AppLogo';

type Props = BoxProps & { children: React.ReactNode };

/**
 * Auth shell: full-viewport center, dark gradient background,
 * prominent brand mark + product name above the card slot.
 */
export default function AuthLayout({ children, ...props }: Props) {
  return (
    <Box
      minH="100vh"
      display="flex"
      alignItems="center"
      justifyContent="center"
      px={{ base: 4, md: 8 }}
      py={{ base: 10, md: 14 }}
      bg="radial-gradient(1200px 600px at 20% 10%, rgba(29,78,216,0.18), transparent 55%), radial-gradient(900px 500px at 85% 25%, rgba(245,158,11,0.10), transparent 55%), #0F172A"
      color="white"
      {...props}
    >
      <Box
        position="absolute"
        inset={0}
        pointerEvents="none"
        bg="radial-gradient(900px 500px at 50% 20%, rgba(255,255,255,0.06), transparent 60%)"
      />
      <Box position="relative" w="full" maxW={{ base: '420px', md: '440px' }}>
        <Box display="flex" alignItems="center" justifyContent="center" gap="14px" mb={6}>
          <AppLogo size={72} />
          <Text fontSize="xl" fontWeight="semibold" color="white" letterSpacing="-0.01em">
            AxiomFolio
          </Text>
        </Box>
        {children}
      </Box>
    </Box>
  );
}
