import * as React from 'react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ProviderMetrics, ProviderUsage } from '@/types/adminHealth';

interface Props {
  metrics: ProviderMetrics | undefined;
  checkedAt: string | undefined;
}

function budgetColor(pct: number): string {
  if (pct > 90) return 'text-destructive';
  if (pct > 70) return 'text-amber-600 dark:text-amber-400';
  return 'text-emerald-600 dark:text-emerald-400';
}

function barColor(pct: number): string {
  if (pct > 90) return 'bg-destructive';
  if (pct > 70) return 'bg-amber-500';
  return 'bg-emerald-500';
}

function estimateBurnRate(calls: number, checkedAt: string | undefined): { rate: string; eta: string | null } {
  if (!checkedAt || calls === 0) return { rate: '0/hr', eta: null };

  const now = new Date();
  const checked = new Date(checkedAt);
  const hoursElapsed = Math.max(0.5, (now.getTime() - new Date(checked.toDateString()).getTime()) / 3_600_000);
  const callsPerHour = Math.round(calls / hoursElapsed);

  return {
    rate: `${callsPerHour}/hr`,
    eta: null,
  };
}

function estimateExhaustion(calls: number, budget: number, checkedAt: string | undefined): string | null {
  if (!checkedAt || calls === 0 || budget <= 0) return null;

  const now = new Date();
  const dayStart = new Date(now.toDateString());
  const hoursElapsed = Math.max(0.5, (now.getTime() - dayStart.getTime()) / 3_600_000);
  const callsPerHour = calls / hoursElapsed;

  if (callsPerHour <= 0) return null;

  const remaining = budget - calls;
  if (remaining <= 0) return 'Exhausted';

  const hoursLeft = remaining / callsPerHour;
  if (hoursLeft > 24) return null;

  const eta = new Date(now.getTime() + hoursLeft * 3_600_000);
  return `~${eta.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
}

export function ProviderIntelligence({ metrics, checkedAt }: Props) {
  if (!metrics?.providers || Object.keys(metrics.providers).length === 0) {
    return null;
  }

  const providers = Object.entries(metrics.providers) as [string, ProviderUsage][];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
          Provider Intelligence
        </p>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>
            Cache: {metrics.l1_hits ?? 0} L1 + {metrics.l2_hits ?? 0} L2 = {metrics.cache_hit_rate ?? 0}% hit rate
          </span>
          <Badge variant="outline" className="text-[10px]">
            L2: {metrics.l2_hit_rate ?? 0}%
          </Badge>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {providers.map(([name, usage]) => {
          const { rate } = estimateBurnRate(usage.calls, checkedAt);
          const exhaustion = estimateExhaustion(usage.calls, usage.budget, checkedAt);

          return (
            <div key={name} className="rounded-lg border border-border bg-card p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium text-foreground">{name}</span>
                <span className={cn('font-mono text-xs', budgetColor(usage.pct))}>
                  {usage.pct}%
                </span>
              </div>

              <div className="relative mb-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={cn('h-full rounded-full transition-[width] duration-500', barColor(usage.pct))}
                  style={{ width: `${Math.min(100, usage.pct)}%` }}
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-1 text-[10px] text-muted-foreground">
                <span>
                  {usage.calls.toLocaleString()} / {usage.budget.toLocaleString()} calls
                </span>
                <span>Burn: {rate}</span>
              </div>

              {exhaustion && (
                <div className="mt-1">
                  <Badge
                    variant="outline"
                    className={cn(
                      'text-[10px]',
                      exhaustion === 'Exhausted'
                        ? 'border-destructive/40 text-destructive'
                        : 'border-amber-500/40 text-amber-600 dark:text-amber-400',
                    )}
                  >
                    {exhaustion === 'Exhausted' ? 'Budget exhausted' : `Exhausts at ${exhaustion}`}
                  </Badge>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default ProviderIntelligence;
