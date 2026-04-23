export type BrokerSlug =
  | 'ibkr'
  | 'schwab'
  | 'tastytrade'
  | 'etrade'
  | 'tradier'
  | 'coinbase';

export type WizardBrokerKey =
  | 'SCHWAB'
  | 'TASTYTRADE'
  | 'IBKR'
  | 'ETRADE'
  | 'TRADIER'
  | 'COINBASE';

export type ConnectionMethodKind = 'OAuth' | 'OAuth 1.0a' | 'FlexQuery' | 'Manual';

export interface BrokerTileDefinition {
  slug: BrokerSlug;
  wizardBroker: WizardBrokerKey;
  displayName: string;
  tagline: string;
  method: ConnectionMethodKind;
  category: 'brokerage' | 'crypto';
}

/** Live direct-connect brokers shown in the picker (order within category). */
export const LIVE_BROKER_TILES: BrokerTileDefinition[] = [
  {
    slug: 'ibkr',
    wizardBroker: 'IBKR',
    displayName: 'Interactive Brokers',
    tagline: 'Equities, options, futures, forex',
    method: 'FlexQuery',
    category: 'brokerage',
  },
  {
    slug: 'schwab',
    wizardBroker: 'SCHWAB',
    displayName: 'Charles Schwab',
    tagline: 'Equities and options',
    method: 'OAuth',
    category: 'brokerage',
  },
  {
    slug: 'tastytrade',
    wizardBroker: 'TASTYTRADE',
    displayName: 'Tastytrade',
    tagline: 'Equities and options',
    method: 'Manual',
    category: 'brokerage',
  },
  {
    slug: 'etrade',
    wizardBroker: 'ETRADE',
    displayName: 'E*TRADE',
    tagline: 'Equities and options (sandbox)',
    method: 'OAuth 1.0a',
    category: 'brokerage',
  },
  {
    slug: 'tradier',
    wizardBroker: 'TRADIER',
    displayName: 'Tradier',
    tagline: 'Equities and options',
    method: 'OAuth',
    category: 'brokerage',
  },
  {
    slug: 'coinbase',
    wizardBroker: 'COINBASE',
    displayName: 'Coinbase',
    tagline: 'Crypto spot',
    method: 'OAuth',
    category: 'crypto',
  },
];

export const SLUG_TO_WIZARD: Record<BrokerSlug, WizardBrokerKey> = LIVE_BROKER_TILES.reduce(
  (acc, t) => {
    acc[t.slug] = t.wizardBroker;
    return acc;
  },
  {} as Record<BrokerSlug, WizardBrokerKey>,
);

/** OAuth `broker` column values that belong to a picker slug (for revoke / detail sheet). */
export const OAUTH_KEYS_BY_SLUG: Record<BrokerSlug, string[]> = {
  ibkr: ['ibkr'],
  schwab: ['schwab'],
  tastytrade: [],
  etrade: ['etrade_sandbox', 'etrade'],
  tradier: ['tradier', 'tradier_sandbox'],
  coinbase: ['coinbase'],
};
