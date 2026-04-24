import React from 'react';
import { BrokerTile, type BrokerTileCta } from './BrokerTile';
import { LIVE_BROKER_TILES, type BrokerSlug, type BrokerTileDefinition } from './brokerCatalog';
import type { ConnectionsBrokerHealthStatus, ConnectionsHealthBrokerRow } from '@/services/connectionsHealth';
import { cn } from '@/lib/utils';

export interface BrokerPickerGridProps {
  byBroker: ConnectionsHealthBrokerRow[];
  hasAccountsBySlug: Record<BrokerSlug, boolean>;
  relativeLastSyncBySlug: Record<BrokerSlug, string | null>;
  dimmed?: boolean;
  onConnect: (def: BrokerTileDefinition) => void;
  onReconnect: (def: BrokerTileDefinition) => void;
  onManage: (def: BrokerTileDefinition) => void;
  schwabConfigured?: boolean;
}

function healthForSlug(rows: ConnectionsHealthBrokerRow[], slug: string): ConnectionsBrokerHealthStatus {
  const row = rows.find((r) => r.broker === slug);
  return row?.status ?? 'disconnected';
}

function pickCta(args: {
  hasAccounts: boolean;
  health: ConnectionsBrokerHealthStatus;
}): BrokerTileCta {
  const { hasAccounts, health } = args;
  if (!hasAccounts) return 'connect';
  if (health === 'stale') return 'reconnect';
  return 'manage';
}

type SectionKey = 'brokerage' | 'crypto' | 'aggregator';

const SECTIONS: { title: string; key: SectionKey; tiles: BrokerTileDefinition[] }[] = (() => {
  const brokerage = LIVE_BROKER_TILES.filter((t) => t.category === 'brokerage');
  const crypto = LIVE_BROKER_TILES.filter((t) => t.category === 'crypto');
  const aggregator = LIVE_BROKER_TILES.filter((t) => t.category === 'aggregator');
  return [
    { title: 'Brokerage (equities and options)', key: 'brokerage', tiles: brokerage },
    { title: 'Crypto', key: 'crypto', tiles: crypto },
    // Read-only aggregator connections (Plaid). Shown last because they
    // expose less than a direct broker link (no cost basis, no trade).
    { title: 'Held-away / 401(k) via aggregator', key: 'aggregator', tiles: aggregator },
  ];
})();

export function BrokerPickerGrid({
  byBroker,
  hasAccountsBySlug,
  relativeLastSyncBySlug,
  dimmed,
  onConnect,
  onReconnect,
  onManage,
  schwabConfigured,
}: BrokerPickerGridProps) {
  const onPrimary = (def: BrokerTileDefinition, cta: BrokerTileCta) => {
    if (cta === 'manage') onManage(def);
    else if (cta === 'reconnect') onReconnect(def);
    else onConnect(def);
  };

  return (
    <div id="broker-picker-grid" className="flex flex-col gap-8">
      {SECTIONS.map((section) => (
        <div key={section.key}>
          <h3 className="mb-3 text-sm font-semibold text-foreground">{section.title}</h3>
          <div
            className={cn(
              'grid gap-4',
              'grid-cols-2 md:grid-cols-3 xl:grid-cols-4',
            )}
          >
            {section.tiles.map((def) => {
              const health = healthForSlug(byBroker, def.slug);
              const hasAccounts = hasAccountsBySlug[def.slug] ?? false;
              const cta = pickCta({ hasAccounts, health });
              const schwabBlocked = def.slug === 'schwab' && schwabConfigured === false && cta === 'connect';
              return (
                <BrokerTile
                  key={def.slug}
                  definition={def}
                  healthStatus={health}
                  hasAccounts={hasAccounts}
                  relativeLastSync={relativeLastSyncBySlug[def.slug] ?? null}
                  cta={cta}
                  dimmed={dimmed}
                  disabled={schwabBlocked}
                  onPrimary={() => onPrimary(def, cta)}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
