export type BrokerSlug =
  | 'ibkr'
  | 'schwab'
  | 'tastytrade'
  | 'etrade'
  | 'tradier'
  | 'coinbase'
  | 'plaid';

export type WizardBrokerKey =
  | 'SCHWAB'
  | 'TASTYTRADE'
  | 'IBKR'
  | 'ETRADE'
  | 'TRADIER'
  | 'COINBASE'
  | 'PLAID';

export type ConnectionMethodKind =
  | 'OAuth'
  | 'OAuth 1.0a'
  | 'FlexQuery'
  | 'Manual'
  | 'Aggregator';

/**
 * Capability matrix for a tile. Used by the UI to decide what the CTA
 * offers and by the tax-lot table to surface aggregator-sourced lots
 * as "—" rather than "$0.00" (plan §Frontend, tax-lot rendering rule).
 */
export interface BrokerCapabilities {
  /** True when AxiomFolio can pull positions/balances for this connection. */
  sync: boolean;
  /** Order-entry capability: 'full' | 'read' | 'none'. */
  trade: 'full' | 'read' | 'none';
  /** Data source attribution — 'direct' from broker API, 'aggregator' via Plaid. */
  source: 'direct' | 'aggregator';
}

export interface BrokerTileDefinition {
  slug: BrokerSlug;
  wizardBroker: WizardBrokerKey;
  displayName: string;
  tagline: string;
  method: ConnectionMethodKind;
  category: 'brokerage' | 'crypto' | 'aggregator';
  /** Tile-level capability hint. Only 'aggregator' category rows vary. */
  capabilities?: BrokerCapabilities;
  /**
   * Optional feature gate key. When present, the tile is wrapped in
   * <TierGate feature={...}> upstream so Free users see a locked state.
   */
  featureKey?: string;
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
  // Plaid Investments — read-only aggregator covering 401(k), 403(b), IRA,
  // and held-away brokerage accounts via plaid.com Link flow. No order
  // entry. See plan `docs/plans/PLAID_FIDELITY_401K.md` and feature
  // catalog key `broker.plaid_investments` (Pro tier).
  {
    slug: 'plaid',
    wizardBroker: 'PLAID',
    displayName: 'Plaid (401k / IRA / held-away)',
    tagline: 'Read-only via Plaid — positions and balances only',
    method: 'Aggregator',
    category: 'aggregator',
    capabilities: { sync: true, trade: 'none', source: 'aggregator' },
    featureKey: 'broker.plaid_investments',
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
  // Plaid is not an OAuth broker row — connections live in the separate
  // ``plaid_connections`` table, so the OAuth revoke/detail path is empty.
  plaid: [],
};
