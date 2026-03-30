import React from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { AdminHealthResponse } from '../../types/adminHealth';
import { formatDateTime } from '../../utils/format';

interface Props {
  health: AdminHealthResponse | null;
  timezone?: string;
}

function compositeBannerClass(status: string): string {
  switch (status) {
    case 'green':
      return 'border-[rgb(var(--status-success)/0.35)] bg-[rgb(var(--status-success)/0.08)]';
    case 'yellow':
      return 'border-[rgb(var(--status-warning)/0.4)] bg-[rgb(var(--status-warning)/0.1)]';
    case 'red':
      return 'border-destructive/40 bg-destructive/5';
    default:
      return 'border-border bg-muted/50';
  }
}

function dimBadgeClass(status: string): string {
  switch (status) {
    case 'green':
    case 'ok':
      return 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]';
    case 'yellow':
    case 'warning':
      return 'border-transparent bg-[rgb(var(--status-warning)/0.12)] text-[rgb(var(--status-warning)/1)]';
    case 'red':
    case 'error':
      return 'border-transparent bg-destructive/10 text-destructive';
    default:
      return 'border-transparent bg-muted text-muted-foreground';
  }
}

function dimDotClass(status: string): string {
  switch (status) {
    case 'green':
    case 'ok':
      return 'bg-[rgb(var(--status-success)/1)]';
    case 'yellow':
    case 'warning':
      return 'bg-[rgb(var(--status-warning)/1)]';
    case 'red':
    case 'error':
      return 'bg-[rgb(var(--status-danger)/1)]';
    default:
      return 'bg-muted-foreground';
  }
}

const AdminHealthBanner: React.FC<Props> = ({ health, timezone }) => {
  if (!health) return null;

  const paletteKey = health.composite_status;
  const dims = health.dimensions;

  return (
    <Alert className={cn('mb-4', compositeBannerClass(paletteKey))}>
      <div className="flex w-full flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <AlertTitle className="text-sm font-semibold">System Health</AlertTitle>
            <Badge variant="outline" className={cn('font-medium uppercase', dimBadgeClass(paletteKey))}>
              {health.composite_status.toUpperCase()}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Checked: {formatDateTime(health.checked_at, timezone)}
          </p>
        </div>
        <AlertDescription className="mb-0 text-xs text-muted-foreground">{health.composite_reason}</AlertDescription>
        <div className="flex flex-wrap gap-2">
          {Object.entries(dims).map(([key, dim]) => (
            <Badge
              key={key}
              variant="outline"
              className={cn('inline-flex items-center gap-1 font-normal capitalize', dimBadgeClass(dim.status))}
            >
              <span
                className={cn('inline-block size-1.5 shrink-0 rounded-full', dimDotClass(dim.status))}
                aria-hidden
              />
              {key.replace('_', ' ')}
            </Badge>
          ))}
        </div>
      </div>
    </Alert>
  );
};

export default AdminHealthBanner;
