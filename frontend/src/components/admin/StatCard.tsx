import React from 'react';
import { Box, Text, HStack, Icon } from '@chakra-ui/react';
import { FiTrendingDown, FiTrendingUp } from 'react-icons/fi';

export interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  /** Compact = border box (dashboard style); full = KPI style without Chakra Stat primitives */
  variant?: 'compact' | 'full';
  trend?: 'up' | 'down';
  color?: string;
  helpText?: string;
  icon?: React.ElementType;
}

const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  sub,
  variant = 'compact',
  trend,
  color,
  helpText,
  icon,
}) => {
  if (variant === 'full') {
    return (
      <Box flex="1" minW="140px">
        <HStack gap={1} mb={1}>
          {icon ? <Icon as={icon} color="fg.muted" boxSize={4} /> : null}
          <Text fontSize="sm" color="fg.muted">
            {label}
          </Text>
        </HStack>
        <Text
          fontSize="2xl"
          fontWeight="semibold"
          fontFamily="mono"
          letterSpacing="-0.02em"
          color={color}
          aria-label={`${label}: ${value}`}
        >
          {value}
        </Text>
        {(helpText !== undefined || sub) && (
          <HStack gap={1} mt={1} fontSize="xs" color="fg.muted">
            {trend === 'up' && <Icon as={FiTrendingUp} boxSize={3.5} color="green.fg" aria-hidden />}
            {trend === 'down' && <Icon as={FiTrendingDown} boxSize={3.5} color="red.fg" aria-hidden />}
            <Text as="span">{helpText ?? sub}</Text>
          </HStack>
        )}
      </Box>
    );
  }

  return (
    <Box
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="lg"
      p={3}
      bg="bg.card"
      flex="1"
      minW="120px"
      transition="box-shadow 200ms ease, transform 200ms ease"
      _hover={{ boxShadow: '0 4px 6px rgba(0,0,0,0.1)', transform: 'translateY(-1px)' }}
    >
      <Text fontSize="xs" color="fg.muted">
        {label}
      </Text>
      <Text
        fontSize="lg"
        fontWeight="bold"
        fontFamily="mono"
        letterSpacing="-0.02em"
        color={color}
        aria-label={`${label}: ${value}`}
      >
        {value}
      </Text>
      {sub != null && sub !== '' && (
        <Text fontSize="xs" color="fg.muted">
          {sub}
        </Text>
      )}
    </Box>
  );
};

export default StatCard;
