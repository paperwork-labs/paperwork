import * as React from 'react';
import { CheckCircle2, AlertCircle, XCircle, Circle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { AdminHealthResponse } from '@/types/adminHealth';

type HealthDimensions = AdminHealthResponse['dimensions'];
type DimensionKey = keyof HealthDimensions;
type DimensionValue = NonNullable<HealthDimensions[DimensionKey]>;

export interface HealthGridProps {
  dimensions: HealthDimensions | null;
  loading?: boolean;
  getHint?: (key: string, dim: DimensionValue) => string | null;
  /**
   * Optional per-row action slot (e.g. an "Explain" button). Rendered
   * alongside the status badge of each non-advisory row only — advisory
   * rows are informational and don't get actions to keep the visual
   * hierarchy intact.
   */
  renderActions?: (key: string, dim: DimensionValue) => React.ReactNode;
  compact?: boolean;
  className?: string;
}

const STATUS_DOT: Record<string, string> = {
  green: 'bg-emerald-500',
  ok: 'bg-emerald-500',
  yellow: 'bg-amber-500',
  warning: 'bg-amber-500',
  red: 'bg-destructive',
  error: 'bg-destructive',
};

function getStatusIcon(status: string, compact: boolean) {
  const size = compact ? 'size-3.5' : 'size-4';
  
  switch (status) {
    case 'green':
    case 'ok':
      return <CheckCircle2 className={cn(size, 'text-emerald-500')} aria-hidden />;
    case 'yellow':
    case 'warning':
      return <AlertCircle className={cn(size, 'text-amber-500')} aria-hidden />;
    case 'red':
    case 'error':
      return <XCircle className={cn(size, 'text-destructive')} aria-hidden />;
    default:
      return <Circle className={cn(size, 'text-muted-foreground')} aria-hidden />;
  }
}

function formatKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatusBadge({ status, compact }: { status: string; compact: boolean }) {
  const isPass = status === 'green' || status === 'ok';
  const isWarn = status === 'yellow' || status === 'warning';

  const label = isPass ? 'Healthy' : isWarn ? 'Warning' : 'Critical';

  return (
    <Badge
      variant="outline"
      className={cn(
        compact ? 'text-[10px] px-1.5 py-0' : 'font-normal',
        isPass && 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300',
        isWarn && 'border-amber-500/40 text-amber-700 dark:text-amber-300',
        !isPass && !isWarn && 'border-destructive/40 text-destructive'
      )}
    >
      {label}
    </Badge>
  );
}

function DimensionRow({
  keyName,
  dim,
  hint,
  compact,
  advisory,
  actions,
}: {
  keyName: string;
  dim: DimensionValue;
  hint: string | null;
  compact: boolean;
  advisory?: boolean;
  actions?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        'rounded-lg px-3 py-2',
        advisory ? 'bg-muted/30 opacity-60' : 'bg-muted/50'
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {compact ? (
            <span
              className={cn(
                'size-[7px] shrink-0 rounded-full',
                STATUS_DOT[dim.status] || 'bg-muted-foreground/50'
              )}
            />
          ) : (
            getStatusIcon(dim.status, compact)
          )}
          <span
            className={cn(
              'font-medium text-foreground',
              compact ? 'text-sm' : 'text-sm'
            )}
          >
            {formatKey(keyName)}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {advisory ? (
            <span className="text-[10px] text-muted-foreground">
              {dim.status.toUpperCase()}
            </span>
          ) : (
            <StatusBadge status={dim.status} compact={compact} />
          )}
          {actions}
        </div>
      </div>
      {hint && (
        <p className="mt-1 ml-4 text-[10px] text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}

export function HealthGrid({
  dimensions,
  loading,
  getHint,
  renderActions,
  compact = false,
  className,
}: HealthGridProps) {
  if (loading) {
    return (
      <div className={cn('flex flex-col gap-2', className)}>
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-8 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (!dimensions) {
    return (
      <p className="text-sm text-muted-foreground">
        Health data unavailable
      </p>
    );
  }

  const entries = (
    Object.entries(dimensions) as [DimensionKey, DimensionValue | undefined][]
  ).filter((entry): entry is [DimensionKey, DimensionValue] => Boolean(entry[1]));
  const mainDimensions = entries.filter(([, dim]) => !dim.advisory);
  const advisoryDimensions = entries.filter(([, dim]) => dim.advisory);

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {mainDimensions.map(([key, dim]) => (
        <DimensionRow
          key={key}
          keyName={key}
          dim={dim}
          hint={getHint?.(key, dim) ?? null}
          compact={compact}
          actions={renderActions?.(key, dim)}
        />
      ))}

      {advisoryDimensions.length > 0 && (
        <>
          <p className="mt-2 text-[10px] font-medium tracking-wider text-muted-foreground/70 uppercase">
            Broker (advisory)
          </p>
          {advisoryDimensions.map(([key, dim]) => (
            <DimensionRow
              key={key}
              keyName={key}
              dim={dim}
              hint={getHint?.(key, dim) ?? null}
              compact={compact}
              advisory
            />
          ))}
        </>
      )}
    </div>
  );
}

export default HealthGrid;
