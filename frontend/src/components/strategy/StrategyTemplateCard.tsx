import React from 'react';
import {
  Box,
  Text,
  Badge,
  HStack,
  VStack,
  CardRoot,
  CardBody,
  Button,
  Icon,
} from '@chakra-ui/react';
import { FiTrendingUp, FiRefreshCw, FiTarget, FiZap } from 'react-icons/fi';
import type { StrategyTemplate } from '../../types/strategy';

interface Props {
  template: StrategyTemplate;
  onUseTemplate: (templateId: string) => void;
}

const TYPE_CONFIG: Record<string, { colorPalette: 'blue' | 'purple' | 'green' | 'gray'; icon: typeof FiTarget }> = {
  momentum: { colorPalette: 'blue', icon: FiTrendingUp },
  mean_reversion: { colorPalette: 'purple', icon: FiRefreshCw },
  breakout: { colorPalette: 'green', icon: FiZap },
  custom: { colorPalette: 'gray', icon: FiTarget },
};

function formatStrategyType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export default function StrategyTemplateCard({ template, onUseTemplate }: Props) {
  const config = TYPE_CONFIG[template.strategy_type] ?? {
    colorPalette: 'gray' as const,
    icon: FiTarget,
  };
  const TypeIcon = config.icon;

  return (
    <CardRoot
      bg="bg.card"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="xl"
      _hover={{ borderColor: 'border.emphasized' }}
      cursor="pointer"
      onClick={() => onUseTemplate(template.id)}
    >
      <CardBody>
        <VStack align="stretch" gap={3}>
          <Badge
            colorPalette={config.colorPalette}
            variant="subtle"
            size="sm"
            alignSelf="flex-start"
          >
            <Icon as={TypeIcon} mr={1} />
            {formatStrategyType(template.strategy_type)}
          </Badge>

          <Text fontWeight="semibold" color="fg.default">
            {template.name}
          </Text>

          <Text fontSize="sm" color="fg.muted" lineClamp={3}>
            {template.description}
          </Text>

          <HStack gap={4} fontSize="xs" color="fg.muted" flexWrap="wrap">
            <Text>{template.position_size_pct}% position</Text>
            <Text>{template.max_positions} max positions</Text>
            {template.stop_loss_pct != null && (
              <Text>{template.stop_loss_pct}% stop loss</Text>
            )}
          </HStack>

          <Button
            size="sm"
            colorPalette="blue"
            onClick={(e) => {
              e.stopPropagation();
              onUseTemplate(template.id);
            }}
          >
            Use Template
          </Button>
        </VStack>
      </CardBody>
    </CardRoot>
  );
}
