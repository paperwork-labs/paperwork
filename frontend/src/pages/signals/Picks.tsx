import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { AlertTriangle, ClipboardList, Sparkles } from 'lucide-react';

import api from '@/services/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { actionChipClass } from '@/lib/picks';
import { cn } from '@/lib/utils';

interface PublishedPick {
  id: number;
  ticker: string;
  action: string;
  thesis: string | null;
  target_price: string | null;
  stop_loss: string | null;
  source: string;
  published_at: string | null;
}

interface PublishedResponse {
  items: PublishedPick[];
  is_preview: boolean;
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return `${s.slice(0, max)}…`;
}

const Picks: React.FC = () => {
  const [expanded, setExpanded] = React.useState<Record<number, boolean>>({});

  const q = useQuery<PublishedResponse>({
    queryKey: ['picks-published'],
    queryFn: async () => {
      const res = await api.get<PublishedResponse>('/picks/published?limit=50');
      return res.data;
    },
  });

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <ClipboardList className="size-5 text-primary" aria-hidden />
          <h1 className="font-heading text-xl font-semibold tracking-tight">Picks</h1>
        </div>
        <p className="text-sm text-muted-foreground">Published validator candidates.</p>
      </header>

      {q.isLoading ? (
        <div className="space-y-3" data-testid="picks-loading">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : q.isError ? (
        <Card className="border-destructive/40 bg-destructive/5" data-testid="picks-error">
          <CardHeader className="flex flex-row items-start gap-3 pb-2">
            <AlertTriangle className="mt-0.5 size-5 text-destructive" aria-hidden />
            <div className="space-y-2">
              <p className="font-medium text-foreground">Unable to load picks</p>
              <p className="text-sm text-muted-foreground">
                {q.error instanceof Error ? q.error.message : 'Check your connection and try again.'}
              </p>
              <Button type="button" size="sm" variant="outline" onClick={() => void q.refetch()}>
                Retry
              </Button>
            </div>
          </CardHeader>
        </Card>
      ) : (
        <>
          {q.data?.is_preview ? (
            <Card className="border-primary/40 bg-primary/5">
              <CardHeader className="flex flex-row items-start gap-3 pb-2">
                <Sparkles className="mt-0.5 size-5 text-primary" aria-hidden />
                <div className="space-y-1">
                  <p className="font-medium text-foreground">Upgrade to Lite to see all picks</p>
                  <p className="text-sm text-muted-foreground">
                    You are viewing a preview: at most one latest published pick per source.
                    Upgrade to Lite for the full feed in real time.
                  </p>
                  <Button type="button" asChild size="sm" className="mt-2 w-fit">
                    <Link to="/pricing">See plans</Link>
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ) : null}

          {!q.data?.items.length ? (
            <Card data-testid="picks-empty">
              <CardHeader className="flex flex-row items-start gap-3 pb-2">
                <ClipboardList className="mt-0.5 size-5 text-muted-foreground" aria-hidden />
                <div className="space-y-2">
                  <p className="font-medium text-foreground">No published picks yet</p>
                  <p className="text-sm text-muted-foreground">
                    Picks are published after validator runs — check back in a few hours, or
                    explore the strategies feeding the validator.
                  </p>
                  <Button asChild size="sm" variant="outline">
                    <Link to="/lab/strategies">Browse strategies</Link>
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ) : (
            q.data.items.map((row) => {
              const isOpen = expanded[row.id] ?? false;
              const thesis = row.thesis ?? '';
              const body = isOpen ? thesis : truncate(thesis, 220);
              return (
                <Card key={row.id}>
                  <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2 pb-2">
                    <div>
                      <p className="font-mono text-xl font-semibold">{row.ticker}</p>
                      <p className="text-xs text-muted-foreground">
                        {row.source}
                        {row.published_at
                          ? ` · ${new Date(row.published_at).toLocaleString()}`
                          : null}
                      </p>
                    </div>
                    <Badge className={cn('uppercase', actionChipClass(row.action))}>
                      {row.action}
                    </Badge>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <p className="whitespace-pre-wrap text-foreground">{body || '—'}</p>
                    {thesis.length > 220 ? (
                      <Button
                        type="button"
                        variant="link"
                        className="h-auto px-0 py-0"
                        aria-expanded={isOpen}
                        onClick={() =>
                          setExpanded((m) => ({ ...m, [row.id]: !isOpen }))
                        }
                      >
                        {isOpen ? 'Show less' : 'Show more'}
                      </Button>
                    ) : null}
                    <div className="flex flex-wrap gap-3 text-muted-foreground">
                      {row.target_price ? <span>Target {row.target_price}</span> : null}
                      {row.stop_loss ? <span>Stop {row.stop_loss}</span> : null}
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </>
      )}
    </div>
  );
};

export default Picks;
