import React from 'react';
import { Check, X } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';

import { MarketingFooter } from '@/components/layout/MarketingFooter';
import { MarketingHeader } from '@/components/layout/MarketingHeader';
import PublicStatsStrip from '@/components/transparency/PublicStatsStrip';
import { cn } from '@/lib/utils';
import api from '@/services/api';
import type { PricingCatalogResponse } from '@/types/pricing';

// Note: there is no hard-coded ``freeForeverItems`` fallback here on
// purpose. The free-tier feature list is owned by the Ladder-3 tier
// catalog on the backend (``backend/services/billing/tier_catalog.py``)
// and returned by ``/pricing/catalog``. Hard-coding it in two places
// invites drift (Copilot flagged this shadow in PR #397); the page
// renders loading/error/empty states explicitly per
// ``no-silent-fallback.mdc``.

// ``neverItems`` intentionally stays hard-coded. These are founder
// commitments — not a tier feature list — and the pricing catalog is
// not the right source of truth for them. A change here is a
// deliberate content update reviewed as part of the PR, not a
// configuration knob in the backend.
const neverItems = [
  'Sell your data, ever',
  'Show ads',
  'Share aggregated portfolios with hedge funds',
  'Change pricing on the free tier',
  'Limit free-tier users to a "preview" of features',
];

const Section: React.FC<{ id?: string; className?: string; children: React.ReactNode }> = ({
  id,
  className,
  children,
}) => (
  <section id={id} className={cn('mx-auto max-w-4xl px-4 py-16 sm:px-6 sm:py-20', className)}>
    {children}
  </section>
);

const WhyFree: React.FC = () => {
  const catalogQuery = useQuery<PricingCatalogResponse>({
    queryKey: ['pricing', 'catalog'],
    queryFn: async () => {
      const res = await api.get<PricingCatalogResponse>('/pricing/catalog');
      return res.data;
    },
  });
  const freeTier = catalogQuery.data?.tiers.find((tier) => tier.tier === 'free');
  const freeForeverItems = freeTier?.features ?? [];

  return (
      <div className="min-h-screen bg-background text-foreground">
        <MarketingHeader />

        <main>
          <Section className="pt-12 pb-8 sm:pt-16 sm:pb-12">
            <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">Transparency</p>
            <h1 className="mt-3 font-heading text-4xl font-semibold tracking-tight sm:text-5xl">
              AxiomFolio is free because we want it to be.
            </h1>
            <p className="mt-6 max-w-2xl text-lg text-muted-foreground">
              Most portfolio apps charge a monthly fee to look at your own data. Here&apos;s why we don&apos;t charge for
              that.
            </p>
          </Section>

          <Section className="border-t border-border bg-muted/20">
            <h2 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">What&apos;s free, forever</h2>
            {catalogQuery.isLoading ? <p className="mt-8 text-sm text-muted-foreground">Loading free tier catalog...</p> : null}
            {catalogQuery.isError ? <p className="mt-8 text-sm text-destructive">Could not load free tier catalog.</p> : null}
            {!catalogQuery.isLoading && !catalogQuery.isError && freeForeverItems.length === 0 ? (
              <p className="mt-8 text-sm text-muted-foreground">No free-tier features configured.</p>
            ) : null}
            <ul className="mt-8 flex flex-col gap-4">
              {freeForeverItems.map((feature) => (
                <li key={feature.key} className="flex gap-3 text-sm sm:text-base">
                  <Check className="mt-0.5 size-5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
                  <span>{feature.title}</span>
                </li>
              ))}
            </ul>
          </Section>

          <Section>
            <h2 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">
              Why we use CSV instead of Plaid
            </h2>
            <div className="mt-8 flex flex-col gap-5 text-sm leading-relaxed text-muted-foreground sm:text-base">
              <p>
                Plaid charges portfolio aggregators per connected account per month. Source:{' '}
                <a
                  href="https://plaid.com/docs/account/billing"
                  className="font-medium text-primary underline-offset-4 hover:underline"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Plaid billing docs
                </a>
                .
              </p>
              <p>
                At 10,000 users with two accounts each, that&apos;s substantial monthly cost before we earn a
                dollar.
              </p>
              <p>
                That&apos;s why aggregator-based competitors charge a subscription to look at your own portfolio.
                They&apos;re paying Plaid out of your subscription.
              </p>
              <p>
                We chose differently. CSV (and email-statement parsing) is the only zero-cost path to Fidelity, Vanguard,
                JPMorgan, Merrill, and Wells — none of whom expose APIs to anyone, regardless of how much you pay.
              </p>
              <p className="text-foreground font-medium">We choose CSV because we choose you.</p>
            </div>

            <div className="mt-10 overflow-x-auto rounded-xl border border-border">
              <table className="w-full min-w-[520px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="px-4 py-3 font-medium"> </th>
                    <th className="px-4 py-3 font-medium">AxiomFolio</th>
                    <th className="px-4 py-3 font-medium">Aggregator-style app</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-border">
                    <td className="px-4 py-3 font-medium text-foreground">Cost to you (core portfolio view)</td>
                    <td className="px-4 py-3">No subscription fee</td>
                    <td className="px-4 py-3">Typically paid subscription</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="px-4 py-3 font-medium text-foreground">Fidelity / Vanguard / big banks</td>
                    <td className="px-4 py-3">CSV + statements</td>
                    <td className="px-4 py-3">Plaid-linked where supported; gaps otherwise</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="px-4 py-3 font-medium text-foreground">Direct broker connections</td>
                    <td className="px-4 py-3">Schwab + Tastytrade + Tradier + Coinbase (OAuth), IBKR (FlexQuery + Gateway), E*TRADE (OAuth sandbox)</td>
                    <td className="px-4 py-3">Varies by vendor</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 font-medium text-foreground">Sells your data</td>
                    <td className="px-4 py-3">No</td>
                    <td className="px-4 py-3">Check their terms — many do</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Section>

          <Section>
            <h2 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">
              What we&apos;ll never do
            </h2>
            <ul className="mt-8 flex flex-col gap-4">
              {neverItems.map((item) => (
                <li key={item} className="flex gap-3 text-sm sm:text-base">
                  <X className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </Section>

          <Section>
            <h2 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">Live pulse</h2>
            <p className="mt-3 max-w-xl text-sm text-muted-foreground">
              Small counters we can stand behind — no internal cost dashboard yet; that comes once there&apos;s revenue
              worth talking about.
            </p>
            <div className="mt-8">
              <PublicStatsStrip />
            </div>
          </Section>

          <Section className="border-t border-border pb-24">
            <h2 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">Like it? Tell a friend.</h2>
            <p className="mt-3 max-w-2xl text-sm text-muted-foreground sm:text-base">
              Tips will open once our Stripe Checkout integration lands. Until then, the single best thing you can do
              is share AxiomFolio with another investor who&apos;s paying a subscription just to look at their own
              holdings.
            </p>
          </Section>
        </main>
        <MarketingFooter />
      </div>
  );
};

export default WhyFree;
