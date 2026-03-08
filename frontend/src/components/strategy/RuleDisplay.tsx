import {
  Box,
  Text,
  Badge,
  HStack,
  VStack,
  CardRoot,
  CardBody,
  SimpleGrid,
} from '@chakra-ui/react';
import type { ConditionGroupData, ConditionData } from '../../types/strategy';

const OPERATOR_MAP: Record<string, string> = {
  gt: '>',
  gte: '>=',
  lt: '<',
  lte: '<=',
  eq: '=',
  neq: '!=',
  between: 'between',
};

function formatOperator(op: string): string {
  return OPERATOR_MAP[op] ?? op;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return JSON.stringify(value);
}

function ConditionRow({ condition }: { condition: ConditionData }) {
  const opDisplay = formatOperator(condition.operator);
  const valueDisplay =
    condition.operator === 'between'
      ? `${formatValue(condition.value)} … ${formatValue(condition.value_high)}`
      : formatValue(condition.value);

  return (
    <CardRoot
      size="sm"
      bg="bg.card"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="md"
    >
      <CardBody py={2} px={3}>
        <HStack gap={2} flexWrap="wrap" fontSize="sm">
          <Text as="span" fontWeight="medium" color="fg.default">
            {condition.field}
          </Text>
          <Text as="span" color="fg.muted">
            {opDisplay}
          </Text>
          <Text as="span" color="fg.default">
            {valueDisplay}
          </Text>
        </HStack>
      </CardBody>
    </CardRoot>
  );
}

interface RuleDisplayProps {
  group: ConditionGroupData;
  label?: string;
  depth?: number;
}

function RuleDisplayInner({ group, label, depth = 0 }: RuleDisplayProps) {
  const logicLabel = group.logic.toUpperCase();
  const hasContent = group.conditions.length > 0 || group.groups.length > 0;

  if (!hasContent) return null;

  return (
    <Box>
      {label && (
        <Text fontSize="xs" fontWeight="semibold" color="fg.muted" mb={1} textTransform="uppercase" letterSpacing="wider">
          {label}
        </Text>
      )}
      <VStack align="stretch" gap={2} pl={depth > 0 ? 4 : 0} borderLeftWidth={depth > 0 ? 2 : 0} borderColor="border.subtle">
        <Badge
          size="sm"
          colorPalette="gray"
          variant="subtle"
          alignSelf="flex-start"
        >
          {logicLabel}
        </Badge>
        <VStack align="stretch" gap={2} pl={2}>
          {group.conditions.map((cond, idx) => (
            <ConditionRow key={idx} condition={cond} />
          ))}
          {group.groups.map((g, idx) => (
            <RuleDisplayInner key={idx} group={g} depth={depth + 1} />
          ))}
        </VStack>
      </VStack>
    </Box>
  );
}

export default function RuleDisplay({ group, label }: { group: ConditionGroupData; label?: string }) {
  return (
    <Box>
      <RuleDisplayInner group={group} label={label} />
    </Box>
  );
}

export function EntryExitRules({
  entryRules,
  exitRules,
}: {
  entryRules?: ConditionGroupData;
  exitRules?: ConditionGroupData;
}) {
  const hasEntry = entryRules && (entryRules.conditions.length > 0 || entryRules.groups.length > 0);
  const hasExit = exitRules && (exitRules.conditions.length > 0 || exitRules.groups.length > 0);

  if (!hasEntry && !hasExit) {
    return (
      <Text fontSize="sm" color="fg.muted">
        No entry or exit rules configured.
      </Text>
    );
  }

  return (
    <SimpleGrid columns={{ base: 1, md: 2 }} gap={4}>
      {hasEntry && (
        <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
          <CardBody>
            <RuleDisplay group={entryRules!} label="Entry" />
          </CardBody>
        </CardRoot>
      )}
      {hasExit && (
        <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
          <CardBody>
            <RuleDisplay group={exitRules!} label="Exit" />
          </CardBody>
        </CardRoot>
      )}
    </SimpleGrid>
  );
}
