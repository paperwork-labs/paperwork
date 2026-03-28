import React from 'react';
import {
  Alert,
  Badge,
  Button,
  ChakraProvider,
  defaultSystem,
  HStack,
  Spinner,
  Text,
} from '@chakra-ui/react';
import hotToast from 'react-hot-toast';

import { useAuth } from '../../context/AuthContext';
import { isPlatformAdminRole } from '../../utils/userRole';
import { useCircuitBreakerStatus, useResetCircuitBreakerKillSwitch } from '../../hooks/useCircuitBreaker';
import type { CircuitBreakerStatus } from '../../types/circuitBreaker';

function tierAlertProps(tier: number): {
  status: 'success' | 'warning' | 'error' | 'neutral';
  colorPalette?: string;
  title: string;
} {
  if (tier >= 3) {
    return { status: 'error', title: 'Trading Halted' };
  }
  if (tier === 2) {
    return { status: 'warning', colorPalette: 'orange', title: 'Entries Blocked' };
  }
  if (tier === 1) {
    return { status: 'warning', title: 'Circuit Warning' };
  }
  return { status: 'success', title: 'Normal' };
}

function KillSwitchBadge({ active }: { active: boolean }) {
  return (
    <Badge colorPalette={active ? 'red' : 'gray'} variant="subtle">
      Kill switch {active ? 'ON' : 'off'}
    </Badge>
  );
}

function BannerBody({
  data,
  isAdmin,
  onReset,
  resetPending,
}: {
  data: CircuitBreakerStatus;
  isAdmin: boolean;
  onReset: () => void;
  resetPending: boolean;
}) {
  const { status: alertStatus, colorPalette, title } = tierAlertProps(data.tier);
  const subtleNormal = data.tier === 0 && !data.kill_switch_active;

  return (
    <Alert.Root
      status={alertStatus}
      {...(colorPalette ? { colorPalette } : {})}
      variant={subtleNormal ? 'subtle' : 'solid'}
      borderRadius="md"
      alignItems="flex-start"
    >
      <Alert.Indicator />
      <Alert.Content w="full">
        <HStack flexWrap="wrap" justify="space-between" gap={3} w="full" align="flex-start">
          <Alert.Title fontSize={subtleNormal ? 'sm' : 'md'}>{title}</Alert.Title>
          {isAdmin ? (
            <Button
              size="sm"
              variant="outline"
              colorPalette="gray"
              loading={resetPending}
              disabled={!data.kill_switch_active || resetPending}
              onClick={onReset}
              aria-label="Reset kill switch"
            >
              Reset kill switch
            </Button>
          ) : null}
        </HStack>
        <Alert.Description fontSize="sm" mt={1}>
          <HStack flexWrap="wrap" gap={2} align="center">
            <Text as="span">
              Daily loss:{' '}
              <Text as="span" fontWeight="semibold">
                {data.daily_pnl_pct.toFixed(2)}%
              </Text>
            </Text>
            <KillSwitchBadge active={data.kill_switch_active} />
            {data.trip_reason ? (
              <Text as="span" color="fg.muted">
                {data.trip_reason}
              </Text>
            ) : null}
          </HStack>
          {data.reason && data.tier > 0 ? (
            <Text mt={1} fontSize="xs" opacity={0.9}>
              {data.reason}
            </Text>
          ) : null}
        </Alert.Description>
      </Alert.Content>
    </Alert.Root>
  );
}

/**
 * Tiered circuit breaker banner (Chakra UI + defaultSystem). Nested `ChakraProvider` keeps the
 * app shell on Tailwind/shadcn without a global Chakra theme.
 */
export function CircuitBreakerBanner() {
  const { user } = useAuth();
  const isAdmin = isPlatformAdminRole(user?.role);
  const { data, isPending, isError } = useCircuitBreakerStatus();
  const resetMutation = useResetCircuitBreakerKillSwitch();

  const handleReset = () => {
    resetMutation.mutate(undefined, {
      onSuccess: () => {
        hotToast.success('Kill switch cleared');
      },
      onError: () => {
        hotToast.error('Could not reset kill switch');
      },
    });
  };

  if (!isPending && (isError || !data)) {
    return null;
  }

  return (
    <ChakraProvider value={defaultSystem}>
      {isPending ? (
        <HStack py={2} px={1} gap={2} color="fg.muted">
          <Spinner size="sm" />
          <Text fontSize="sm">Loading circuit breaker…</Text>
        </HStack>
      ) : (
        <BannerBody
          data={data}
          isAdmin={isAdmin}
          onReset={handleReset}
          resetPending={resetMutation.isPending}
        />
      )}
    </ChakraProvider>
  );
}
