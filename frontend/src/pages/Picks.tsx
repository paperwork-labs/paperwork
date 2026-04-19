import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Sparkles } from 'lucide-react';

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

  const q = useQuery({
    queryKey: ['picks-published'],
    queryFn: async () => {
      const res = await api.get<PublishedResponse>('/picks/published?limit=50');
      return res.data;
    },
  });

  if (q.isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-3 p-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (q.isError) {
    return (
      <div className="mx-auto max-w-3xl p-4 text-sm text-destructive">
        Unable to load picks. Check your connection and try again.
      </div>
    );
  }

  const data = q.data;

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <div>
        <h1 className="font-heading text-xl font-semibold tracking-tight">Picks</h1>
        <p className="text-sm text-muted-foreground">Published validator candidates.</p>
      </div>

      {data?.is_preview ? (
        <Card className="border-primary/40 bg-primary/5">
          <CardHeader className="flex flex-row items-start gap-3 pb-2">
            <Sparkles className="mt-0.5 size-5 text-primary" aria-hidden />
            <div className="space-y-1">
              <p className="font-medium text-foreground">Upgrade to Lite to see all picks</p>
              <p className="text-sm text-muted-foreground">
                You are viewing a preview: at most one latest published pick per source. Upgrade to Lite for the full
                feed in real time.
              </p>
              <Button type="button" asChild size="sm" className="mt-2 w-fit">
                <Link to="/settings/profile">View subscription</Link>
              </Button>
            </div>
          </CardHeader>
        </Card>
      ) : null}

      {!data?.items.length ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">No published picks yet.</CardContent>
        </Card>
      ) : (
        data.items.map((row) => {
          const isOpen = expanded[row.id];
          const thesis = row.thesis ?? '';
          const body = isOpen ? thesis : truncate(thesis, 220);
          return (
            <Card key={row.id}>
              <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2 pb-2">
                <div>
                  <p className="font-mono text-xl font-semibold">{row.ticker}</p>
                  <p className="text-xs text-muted-foreground">
                    {row.source}
                    {row.published_at ? ` · ${new Date(row.published_at).toLocaleString()}` : null}
                  </p>
                </div>
                <Badge className={cn('uppercase', actionChipClass(row.action))}>{row.action}</Badge>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="whitespace-pre-wrap text-foreground">{body || '—'}</p>
                {thesis.length > 220 ? (
                  <Button type="button" variant="link" className="h-auto px-0 py-0" onClick={() => setExpanded((m) => ({ ...m, [row.id]: !isOpen }))}>
                    {isOpen ? 'Show less' : 'Read full thesis'}
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
    </div>
  );
};

export default Picks;
