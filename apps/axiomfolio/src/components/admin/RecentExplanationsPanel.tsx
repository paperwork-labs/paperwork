/**
 * RecentExplanationsPanel — top-of-SystemStatus panel showing the 10
 * newest AutoOps anomaly explanations.
 *
 * Polls `GET /api/v1/admin/agent/explanations?limit=10` every 30 seconds
 * via TanStack Query (`refetchInterval`). React Query v5 pauses polling
 * automatically when `document.visibilityState === 'hidden'` so we don't
 * burn cycles on a backgrounded tab.
 *
 * Loading / error / empty / data states are kept distinct (no silent
 * fallbacks per `.cursor/rules/no-silent-fallback.mdc`). The panel is a
 * thin presentation layer; the drawer it opens is responsible for the
 * full explanation render.
 */
import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Info, Sparkles } from 'lucide-react';

import {
  AnomalyExplanationDrawer,
  type AnomalyExplanationTrigger,
} from '@/components/admin/AnomalyExplanationDrawer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/skeleton';
import { useBackendUser } from '@/hooks/use-backend-user';
import { cn } from '@/lib/utils';
import {
  listExplanations,
  type AutoOpsExplanation,
  type AutoOpsExplanationList,
} from '@/services/autoOps';
import { isPlatformAdminRole } from '@/utils/userRole';

const POLL_INTERVAL_MS = 30_000;
const PREVIEW_CHAR_LIMIT = 80;

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function previewNarrative(row: AutoOpsExplanation): string {
  const narrative = row.payload?.narrative ?? row.summary ?? '';
  const trimmed = narrative.replace(/\s+/g, ' ').trim();
  if (trimmed.length <= PREVIEW_CHAR_LIMIT) return trimmed;
  // Cut on a word boundary if convenient; otherwise hard truncate.
  const cut = trimmed.slice(0, PREVIEW_CHAR_LIMIT);
  const lastSpace = cut.lastIndexOf(' ');
  return `${(lastSpace > 40 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`;
}

function PanelHeader({ count }: { count: number | null }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-primary" aria-hidden />
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Recent AutoOps Explanations
        </p>
      </div>
      {count != null ? (
        <span className="text-[10px] tabular-nums text-muted-foreground">
          {count} total
        </span>
      ) : null}
    </div>
  );
}

function PanelSkeleton() {
  return (
    <div className="space-y-2" data-testid="recent-explanations-skeleton">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="flex items-center gap-3 rounded-md border border-border/40 bg-muted/20 px-3 py-2"
        >
          <Skeleton className="size-4 rounded-full" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-3/4" />
          </div>
          <Skeleton className="h-6 w-12 rounded-md" />
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div
      className="flex flex-col items-center gap-2 rounded-md border border-dashed border-border bg-muted/20 px-4 py-8 text-center"
      data-testid="recent-explanations-empty"
    >
      <Info className="size-5 text-muted-foreground" aria-hidden />
      <p className="text-sm text-foreground">No explanations yet.</p>
      <p className="max-w-sm text-xs text-muted-foreground">
        Click &quot;Explain&quot; on a dimension card to generate one.
      </p>
    </div>
  );
}

interface ExplanationRowProps {
  row: AutoOpsExplanation;
  onOpen: (row: AutoOpsExplanation) => void;
}

function ExplanationRow({ row, onOpen }: ExplanationRowProps) {
  const preview = previewNarrative(row);
  return (
    <li
      className={cn(
        'flex items-start gap-3 rounded-md border border-border/40 bg-muted/20 px-3 py-2',
        'transition-colors hover:bg-muted/40',
      )}
      data-testid="recent-explanation-row"
    >
      <div className="mt-0.5 flex flex-col items-end gap-0.5 text-[10px] tabular-nums text-muted-foreground">
        <span>{formatTimestamp(row.generated_at)}</span>
        {row.is_fallback ? (
          <Badge
            variant="outline"
            className="border-amber-500/40 px-1 py-0 text-[9px] text-amber-700 dark:text-amber-300"
            data-testid="row-degraded-badge"
          >
            Degraded
          </Badge>
        ) : null}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="truncate text-xs font-medium text-foreground">
            {row.category}
          </span>
          <Badge variant="outline" className="px-1 py-0 text-[9px] uppercase">
            {row.severity}
          </Badge>
        </div>
        <p
          className="mt-0.5 line-clamp-2 text-xs text-muted-foreground"
          data-testid="recent-explanation-preview"
        >
          {preview || '—'}
        </p>
      </div>
      <Button
        type="button"
        size="xs"
        variant="outline"
        onClick={() => onOpen(row)}
        aria-label={`Open explanation for ${row.category}`}
      >
        Open
      </Button>
    </li>
  );
}

export function RecentExplanationsPanel() {
  const { user } = useBackendUser();
  const isAdmin = isPlatformAdminRole(user?.role);

  const [trigger, setTrigger] = React.useState<AnomalyExplanationTrigger | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const query = useQuery<AutoOpsExplanationList>({
    queryKey: ['admin', 'autoops', 'recent-explanations', 10],
    queryFn: () => listExplanations({ limit: 10 }),
    refetchInterval: POLL_INTERVAL_MS,
    enabled: isAdmin,
    // TanStack Query v5 already pauses on hidden tabs by default
    // (`refetchIntervalInBackground: false`); we keep that default
    // explicit here so a future config change doesn't flip it silently.
    refetchIntervalInBackground: false,
  });

  const handleOpen = React.useCallback((row: AutoOpsExplanation) => {
    setTrigger({ mode: 'existing', explanation: row });
    setDrawerOpen(true);
  }, []);

  if (!isAdmin) return null;

  const items = query.data?.items ?? [];

  return (
    <>
      <Card data-testid="recent-explanations-panel">
        <CardContent className="space-y-3 pt-6">
          <PanelHeader count={query.data?.total ?? null} />
          {query.isLoading ? (
            <PanelSkeleton />
          ) : query.isError ? (
            <ErrorState
              title="Couldn't load recent explanations"
              description="The AutoOps explanation feed is temporarily unavailable."
              error={query.error}
              retry={() => void query.refetch()}
            />
          ) : items.length === 0 ? (
            <EmptyState />
          ) : (
            <ul className="space-y-1.5">
              {items.map((row) => (
                <ExplanationRow key={row.id} row={row} onOpen={handleOpen} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <AnomalyExplanationDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        trigger={trigger}
      />
    </>
  );
}

export default RecentExplanationsPanel;
