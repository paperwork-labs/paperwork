import React from 'react';
import { Link } from 'react-router-dom';
import { Check, X } from 'lucide-react';

import PublicStatsStrip from '@/components/transparency/PublicStatsStrip';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

const freeForeverItems = [
  'The flagship holding chart (with stages, RS, ATR — every overlay)',
  'Portfolio equity curve + drawdown',
  'Allocation treemap, income calendar, sentiment overlay',
  'Connect Schwab, IBKR, Tastytrade via OAuth (and E*TRADE/Tradier/Coinbase when v1.1 ships)',
  'Import any other broker via beautiful CSV (Fidelity, Vanguard, Robinhood, M1, SoFi, Public, Webull, JPMorgan, Merrill, Wells, Wealthfront, Betterment)',
  'Email-statement parsing (forward your monthly statement → we parse it)',
  'Public portfolio sharing with rich social previews',
  'Daily AI narrative ("today: AAPL ex-div, NVDA flipped Stage 2A → 3A")',
  'Real-time prices (most apps charge $10/mo for this)',
];

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
  <section id={id} className={cn('mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-20', className)}>
    {children}
  </section>
);

const WhyFree: React.FC = () => {
  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background text-foreground">
        <header className="border-b border-border bg-card/60 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
            <span className="font-heading text-lg font-semibold tracking-tight">AxiomFolio</span>
            <div className="flex items-center gap-4 text-sm">
              <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
                Sign in
              </Link>
              <Link to="/register" className="font-medium text-primary underline-offset-4 hover:underline">
                Register
              </Link>
            </div>
          </div>
        </header>

        <main>
          <Section className="max-w-4xl pt-12 pb-8 sm:pt-16 sm:pb-12">
            <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">Transparency</p>
            <h1 className="mt-3 font-heading text-4xl font-semibold tracking-tight sm:text-5xl">
              AxiomFolio is free because we want it to be.
            </h1>
            <p className="mt-6 max-w-2xl text-lg text-muted-foreground">
              Most portfolio apps cost $10–20/month to look at your own data. Here&apos;s why we don&apos;t charge for
              that.
            </p>
          </Section>

          <Section className="border-t border-border bg-muted/20">
            <h2 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">What&apos;s free, forever</h2>
            <ul className="mt-8 flex flex-col gap-4">
              {freeForeverItems.map((item) => (
                <li key={item} className="flex gap-3 text-sm sm:text-base">
                  <Check className="mt-0.5 size-5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
                  <span>{item}</span>
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
                Plaid charges portfolio aggregators roughly $1–3 per connected account per month. Source:{' '}
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
                At 10,000 users with two accounts each, that&apos;s $40,000/month of pure cost — before we earn a
                dollar.
              </p>
              <p>
                That&apos;s why aggregator-based competitors charge you $5–15/month to look at your own portfolio.
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
                    <td className="px-4 py-3">$0</td>
                    <td className="px-4 py-3">Often $5–15/mo</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="px-4 py-3 font-medium text-foreground">Fidelity / Vanguard / big banks</td>
                    <td className="px-4 py-3">CSV + statements</td>
                    <td className="px-4 py-3">Plaid-linked where supported; gaps otherwise</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="px-4 py-3 font-medium text-foreground">Direct OAuth where available</td>
                    <td className="px-4 py-3">Schwab, IBKR, Tastytrade</td>
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

          <Section className="border-t border-border bg-muted/20">
            <h2 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">When we&apos;ll charge</h2>
            <div className="mt-10 flex flex-col gap-10">
              <article>
                <h3 className="text-lg font-semibold">Lite ($20/mo)</h3>
                <p className="mt-3 text-sm text-muted-foreground sm:text-base">
                  One-click connections to Robinhood, Webull, Public, M1, SoFi via SnapTrade. SnapTrade charges us
                  about $2/user/month — your subscription covers that and our compute. We take zero markup on the
                  SnapTrade line.
                </p>
                <p className="mt-3 rounded-lg border border-border bg-background/80 px-3 py-2 text-xs text-muted-foreground sm:text-sm">
                  Your $20 covers the SnapTrade pass-through plus infrastructure — not a hidden skim.
                </p>
              </article>
              <article>
                <h3 className="text-lg font-semibold">Pro ($50/mo)</h3>
                <p className="mt-3 text-sm text-muted-foreground sm:text-base">
                  AI portfolio chat (OpenAI tokens cost real money — about $0.40 per session). Walk-forward backtests
                  (compute-intensive). Multi-portfolio.
                </p>
                <p className="mt-3 rounded-lg border border-border bg-background/80 px-3 py-2 text-xs text-muted-foreground sm:text-sm">
                  Your $50 covers model usage and heavy compute — not vanity features.
                </p>
              </article>
              <article>
                <h3 className="text-lg font-semibold">Pro+ ($150/mo)</h3>
                <p className="mt-3 text-sm text-muted-foreground sm:text-base">
                  Autotrade, advanced execution, options chain analytics, dedicated infra.
                </p>
                <p className="mt-3 rounded-lg border border-border bg-background/80 px-3 py-2 text-xs text-muted-foreground sm:text-sm">
                  Your $150 covers serious execution and capacity — not a logo on a slide deck.
                </p>
              </article>
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

          <Section className="border-t border-border bg-muted/20">
            <h2 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">Built by a solo founder</h2>
            <div className="mt-8 flex flex-col gap-6 sm:flex-row sm:items-start">
              <div
                className="flex size-14 shrink-0 items-center justify-center rounded-full border border-border bg-primary text-lg font-semibold text-primary-foreground"
                aria-hidden
              >
                AF
              </div>
              <div className="flex flex-col gap-4 text-sm leading-relaxed text-muted-foreground sm:text-base">
                <p>
                  AxiomFolio is built by one person who got tired of paying Personal Capital $19.99/month to look at
                  their own portfolio.
                </p>
                <p>No VCs. No growth team. No data-sale revenue. Just a product I wanted to exist.</p>
              </div>
            </div>
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
            <h2 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">Tip jar</h2>
            <p className="mt-3 max-w-xl text-sm text-muted-foreground sm:text-base">
              If this saved you a Personal Capital subscription, consider a coffee.
            </p>
            {/* TODO: Wire Stripe Checkout session URLs when tip / donation products exist in Stripe. */}
            <div className="mt-6 flex flex-wrap gap-3">
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0} role="button" aria-disabled="true">
                    <Button type="button" variant="secondary" disabled>
                      $5
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent>Coming soon</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0} role="button" aria-disabled="true">
                    <Button type="button" variant="secondary" disabled>
                      $20
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent>Coming soon</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0} role="button" aria-disabled="true">
                    <Button type="button" variant="outline" disabled>
                      Custom
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent>Coming soon</TooltipContent>
              </Tooltip>
            </div>
          </Section>
        </main>
      </div>
    </TooltipProvider>
  );
};

export default WhyFree;
