import React from 'react';
import {
  Box,
  Text,
  HStack,
  Icon,
  StatRoot,
  StatLabel,
  StatValueText,
  StatHelpText,
  StatUpIndicator,
  StatDownIndicator,
} from '@chakra-ui/react';

export interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  /** Compact = border box (dashboard style); full = Chakra StatRoot (KPI style) */
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
      <StatRoot>
        <StatLabel>
          <HStack gap={1}>
            {icon && <Icon as={icon} />}
            <Text>{label}</Text>
          </HStack>
        </StatLabel>
        <StatValueText color={color} aria-label={`${label}: ${value}`}>{value}</StatValueText>
        {(helpText !== undefined || sub) && (
          <StatHelpText>
            {trend === 'up' && <StatUpIndicator />}
            {trend === 'down' && <StatDownIndicator />}
            {helpText ?? sub}
          </StatHelpText>
        )}
      </StatRoot>
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
      _hover={{ boxShadow: "0 4px 6px rgba(0,0,0,0.1)", transform: "translateY(-1px)" }}
    >
      <Text fontSize="xs" color="fg.muted">
        {label}
      </Text>
      <Text fontSize="lg" fontWeight="bold" fontFamily="mono" letterSpacing="-0.02em" color={color} aria-label={`${label}: ${value}`}>
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
