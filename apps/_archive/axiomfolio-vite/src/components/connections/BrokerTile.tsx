import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { BrokerLogo } from '@/components/brokers/BrokerLogo';
import { cn } from '@/lib/utils';
import type { BrokerTileDefinition } from './brokerCatalog';
import type { ConnectionsBrokerHealthStatus } from '@/services/connectionsHealth';
import { connectionStatusDotClass, connectionStatusLabel } from './statusClasses';

export type BrokerTileCta = 'connect' | 'reconnect' | 'manage';

export interface BrokerTileProps {
  definition: BrokerTileDefinition;
  healthStatus: ConnectionsBrokerHealthStatus;
  hasAccounts: boolean;
  relativeLastSync: string | null;
  disabled?: boolean;
  cta: BrokerTileCta;
  onPrimary: () => void;
  dimmed?: boolean;
}

export function BrokerTile({
  definition,
  healthStatus,
  hasAccounts,
  relativeLastSync,
  disabled,
  cta,
  onPrimary,
  dimmed,
}: BrokerTileProps) {
  const oauthExpired = healthStatus === 'stale' && hasAccounts;
  const label = connectionStatusLabel({
    status: healthStatus,
    hasAccounts,
    relativeLastSync,
    oauthExpired,
  });
  const dotStatus: ConnectionsBrokerHealthStatus | 'not_connected' = !hasAccounts ? 'disconnected' : healthStatus;

  const ctaLabel = cta === 'connect' ? 'Connect' : cta === 'reconnect' ? 'Reconnect' : 'Manage';

  return (
    <Card
      id={`tile-${definition.slug}`}
      className={cn(
        'h-full border-border shadow-xs transition-opacity scroll-mt-24',
        hasAccounts && healthStatus === 'connected' && 'border-l-[3px] border-l-emerald-500',
        hasAccounts && healthStatus === 'stale' && 'border-l-[3px] border-l-amber-500',
        hasAccounts && healthStatus === 'error' && 'border-l-[3px] border-l-destructive',
        dimmed && 'opacity-50',
      )}
    >
      <CardContent className="flex h-full flex-col gap-3 p-4">
        <div className="flex flex-row items-start gap-3">
          <BrokerLogo
            slug={definition.slug}
            name={definition.displayName}
            size={32}
            className="h-8 w-8 p-0.5"
          />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold leading-tight text-foreground">{definition.displayName}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">{definition.tagline}</div>
            <div className="mt-2 flex flex-wrap gap-1">
              <Badge variant="secondary" className="text-[10px] font-normal">
                {definition.method}
              </Badge>
            </div>
          </div>
        </div>
        <div className="flex flex-row items-center gap-2 text-xs">
          <span className={cn('size-2 shrink-0 rounded-full', connectionStatusDotClass(dotStatus))} aria-hidden />
          <span className="font-medium text-foreground">{label}</span>
        </div>
        <div className="mt-auto">
          <Button
            type="button"
            size="sm"
            className="w-full"
            variant={cta === 'reconnect' ? 'default' : 'secondary'}
            disabled={disabled}
            onClick={onPrimary}
          >
            {ctaLabel}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
