/**
 * Vite-bundled broker marks (no runtime CDN). Keys must stay aligned with
 * `backend.services.portfolio.broker_catalog` slugs and `BrokerSlug` in
 * `components/connections/brokerCatalog.ts` where applicable.
 */
import coinbase from '@/assets/logos/coinbase.svg';
import etrade from '@/assets/logos/etrade.svg';
import fidelity from '@/assets/logos/fidelity.svg';
import ibkr from '@/assets/logos/interactive-brokers.svg';
import schwab from '@/assets/logos/schwab.svg';
import tastytrade from '@/assets/logos/tastytrade.svg';
import tradier from '@/assets/logos/tradier.svg';

const BROKER_LOGO_BY_SLUG: Record<string, string> = {
  ibkr,
  schwab,
  tastytrade,
  etrade,
  tradier,
  coinbase,
  /** Placeholder F mark — full wordmark is a follow-up (brand licensing). */
  fidelity,
  /** Pro / import flows share Coinbase + Coinbase Pro naming. */
  coinbase_pro: coinbase,
};

export function resolveBrokerLogoUrl(slug: string): string | null {
  const k = (slug || '').toLowerCase();
  return BROKER_LOGO_BY_SLUG[k] ?? null;
}

export const BROKER_LOGO_SLUGS = Object.keys(BROKER_LOGO_BY_SLUG);
