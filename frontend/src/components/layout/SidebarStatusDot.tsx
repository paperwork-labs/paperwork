import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import useAdminHealth from '@/hooks/useAdminHealth';
import type { AdminHealthResponse } from '@/types/adminHealth';

type DotColor = 'green' | 'amber' | 'red' | 'grey';

interface DotBreakdown {
  total: number;
  healthy: number;
  stale: number;
  error: number;
}

/**
 * Walk the health response and count dimensions by status bucket.
 * "stale" = yellow/warning; "error" = red/error; anything else = healthy.
 * Kept as a pure helper so the component stays easy to test.
 */
function summarizeHealth(health: AdminHealthResponse): {
  color: DotColor;
  breakdown: DotBreakdown;
} {
  const dims = health.dimensions as Record<string, { status?: string; advisory?: boolean } | undefined>;
  const entries = Object.values(dims).filter(
    (d): d is { status?: string; advisory?: boolean } => Boolean(d),
  );

  let healthy = 0;
  let stale = 0;
  let errorCount = 0;

  for (const dim of entries) {
    const status = (dim.status ?? '').toLowerCase();
    // Advisory dimensions never escalate the dot colour — they are informational.
    const advisory = dim.advisory === true;
    if (!advisory && (status === 'red' || status === 'error')) {
      errorCount += 1;
    } else if (!advisory && (status === 'yellow' || status === 'warning')) {
      stale += 1;
    } else {
      healthy += 1;
    }
  }

  const total = entries.length;
  let color: DotColor = 'green';
  if (errorCount > 0) color = 'red';
  else if (stale > 0) color = 'amber';

  return {
    color,
    breakdown: { total, healthy, stale, error: errorCount },
  };
}

interface SidebarStatusDotProps {
  /** When false the dot is hidden (non-admin users). */
  isAdmin: boolean;
}

/**
 * Tiny coloured dot rendered in the sidebar's SETTINGS header (admin-only).
 *
 * Four explicit states — never silently defaults to green on failure:
 *   - isAdmin=false           → returns null
 *   - loading                 → no dot (prevents layout thrash / false green)
 *   - fetch error (401/403/x) → muted grey dot + "status unknown" tooltip
 *   - empty dimensions        → no dot
 *   - data                    → green / amber / red based on worst dim
 *
 * Clicks route to the System Status page; hover surfaces a dim breakdown.
 */
const SidebarStatusDot: React.FC<SidebarStatusDotProps> = ({ isAdmin }) => {
  const navigate = useNavigate();
  const { health, loading, isError } = useAdminHealth();

  const summary = useMemo(() => {
    if (!health) return null;
    return summarizeHealth(health);
  }, [health]);

  if (!isAdmin) return null;
  if (loading) return null;

  // Fetch failed (likely 401/403 for a demoted admin, or network blip).
  // Muted grey dot with explicit "status unknown" tooltip — never a silent
  // fallback to green, which would violate no-silent-fallback.
  if (isError || !health) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label="System status unknown"
            onClick={() => navigate('/settings/admin/system')}
            className={cn(
              'inline-flex size-1.5 shrink-0 rounded-full',
              'bg-muted-foreground/40 hover:bg-muted-foreground/60',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            )}
            data-testid="sidebar-status-dot"
            data-dot-color="grey"
          />
        </TooltipTrigger>
        <TooltipContent side="right" className="text-xs">
          System status unknown
        </TooltipContent>
      </Tooltip>
    );
  }

  if (!summary || summary.breakdown.total === 0) return null;

  const { color, breakdown } = summary;
  const colorClass =
    color === 'red'
      ? 'bg-rose-500/80 hover:bg-rose-500'
      : color === 'amber'
        ? 'bg-amber-400/80 hover:bg-amber-400'
        : 'bg-emerald-500/80 hover:bg-emerald-500';

  const label =
    color === 'green'
      ? `All ${breakdown.total} systems healthy`
      : color === 'amber'
        ? `${breakdown.stale} stale / ${breakdown.total}`
        : `${breakdown.error} error / ${breakdown.total}`;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={`System status: ${label}`}
          onClick={() => navigate('/settings/admin/system')}
          className={cn(
            'inline-flex size-1.5 shrink-0 rounded-full transition-colors',
            colorClass,
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          )}
          data-testid="sidebar-status-dot"
          data-dot-color={color}
        />
      </TooltipTrigger>
      <TooltipContent side="right" className="text-xs">
        {label}
      </TooltipContent>
    </Tooltip>
  );
};

export default React.memo(SidebarStatusDot);
