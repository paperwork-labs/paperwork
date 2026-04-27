import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import type { ConnectionsHealthResponse } from '@/services/connectionsHealth';
import { formatRelativeTime } from '@/utils/format';
import { healthBannerClass } from './statusClasses';
import { LIVE_BROKER_TILES } from './brokerCatalog';

export interface HealthCardProps {
  health: ConnectionsHealthResponse;
  onRunSync: () => void;
  syncPending: boolean;
}

function displayNameForSlug(slug: string): string {
  const hit = LIVE_BROKER_TILES.find((t) => t.slug === slug);
  return hit?.displayName ?? slug;
}

export function HealthCard({ health, onRunSync, syncPending }: HealthCardProps) {
  const last = health.last_sync_at ? formatRelativeTime(health.last_sync_at) : null;
  const problemRows = health.by_broker.filter((r) => r.status === 'stale' || r.status === 'error');

  return (
    <Card className="border-border bg-muted/60 shadow-xs">
      <CardContent className="flex flex-col gap-4 p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-3xl font-semibold tabular-nums text-foreground">
              {health.connected}
              <span className="text-lg font-normal text-muted-foreground"> of {health.total} brokers connected</span>
            </div>
            <div className="mt-1 text-sm text-muted-foreground">
              {last ? (
                <>
                  Last successful sync across accounts:{' '}
                  <span className="font-medium text-foreground">{last}</span>
                </>
              ) : (
                'No successful sync recorded yet for linked accounts.'
              )}
            </div>
          </div>
          <Button type="button" className="shrink-0 md:self-start" disabled={syncPending} onClick={onRunSync}>
            {syncPending ? <Loader2 className="mr-2 size-4 animate-spin" aria-hidden /> : null}
            Run sync now
          </Button>
        </div>
        {problemRows.length > 0 ? (
          <div className="flex flex-col gap-2">
            {problemRows.map((row) => (
              <div
                key={row.broker}
                className={healthBannerClass(row.status === 'error' ? 'error' : 'stale')}
              >
                <a href={`#tile-${row.broker}`} className="font-medium underline-offset-2 hover:underline">
                  {displayNameForSlug(row.broker)}
                </a>
                {row.status === 'error' ? ' needs attention (sync or token error).' : ' needs reconnection.'}
                {row.error_message ? (
                  <span className="mt-1 block text-xs opacity-90">{row.error_message}</span>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
