import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
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
    <Card size="sm" className="shadow-none">
      <CardContent className="py-2">
        <div className="flex flex-wrap gap-2 text-sm">
          <span className="font-medium text-foreground">{condition.field}</span>
          <span className="text-muted-foreground">{opDisplay}</span>
          <span className="text-foreground">{valueDisplay}</span>
        </div>
      </CardContent>
    </Card>
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
    <div>
      {label && (
        <p className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{label}</p>
      )}
      <div
        className={cn(
          'flex flex-col gap-2',
          depth > 0 && 'border-l-2 border-border pl-4',
        )}
      >
        <Badge variant="secondary" className="w-fit text-[10px]">
          {logicLabel}
        </Badge>
        <div className="flex flex-col gap-2 pl-2">
          {group.conditions.map((cond, idx) => (
            <ConditionRow key={idx} condition={cond} />
          ))}
          {group.groups.map((g, idx) => (
            <RuleDisplayInner key={idx} group={g} depth={depth + 1} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function RuleDisplay({ group, label }: { group: ConditionGroupData; label?: string }) {
  return (
    <div>
      <RuleDisplayInner group={group} label={label} />
    </div>
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
    return <p className="text-sm text-muted-foreground">No entry or exit rules configured.</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {hasEntry && (
        <Card>
          <CardContent className="pt-6">
            <RuleDisplay group={entryRules!} label="Entry" />
          </CardContent>
        </Card>
      )}
      {hasExit && (
        <Card>
          <CardContent className="pt-6">
            <RuleDisplay group={exitRules!} label="Exit" />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
