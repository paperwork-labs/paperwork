/**
 * `PricingFAQ` — bottom-of-page FAQ accordion.
 *
 * Each entry maps directly to a recurring conversation we want to
 * pre-empt before a visitor asks (per D106 + the v1 sprint plan
 * "honest paywall" thesis). Built on Radix Collapsible so each item
 * is keyboard-accessible without us re-implementing accordion ARIA.
 *
 * Copy lives in this file because it's deliberately voiceful and
 * editorial — the cost of a CMS for six paragraphs would outweigh the
 * agility benefit at v1.
 */

import * as React from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';

interface FaqEntry {
  question: string;
  /**
   * Body element. Returns JSX so each answer can interleave links and
   * emphasis without resorting to `dangerouslySetInnerHTML`.
   */
  answer: React.ReactNode;
}

const FAQ_ENTRIES: ReadonlyArray<FaqEntry> = [
  {
    question: 'Why is the free tier this generous?',
    answer: (
      <>
        Because most "free" portfolio apps still charge a monthly fee to look
        at your own data, and we don't want to be that. Snowball-class
        visualization, direct connections to Schwab, IBKR, Tastytrade,
        and E*TRADE today (Schwab + Tastytrade via OAuth, IBKR via
        FlexQuery + IB Gateway, E*TRADE via OAuth sandbox; Tradier and
        Coinbase OAuth on the v1 parity track),
        CSV import for every other broker, real-time prices, public
        sharing — all free, forever. The full reasoning lives on{' '}
        <Link
          to="/why-free"
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          our /why-free page
        </Link>
        .
      </>
    ),
  },
  {
    question:
      'How is your pricing different from Personal Capital, Snowball, or Sharesight?',
    answer: (
      <>
        Two ways. First: most competitors hide what their pricing pays
        for. We tell you per tier — "Pro covers the retail-broker
        aggregator's per-user cost with zero markup", "Pro covers
        OpenAI tokens for native unlimited chat", and so on. Second:
        those apps depend on aggregators (Plaid, Yodlee) that charge
        them per connected account every month, so they have to charge
        you to read your own portfolio. We chose CSV + direct broker
        connections (OAuth where the broker supports it, FlexQuery +
        IB Gateway for IBKR) for the free tier so we never have a
        per-user cost we'd need to recover from you.
      </>
    ),
  },
  {
    question: 'Do you sell my data?',
    answer: (
      <>
        No. Never. Not aggregated, not anonymized, not "for research".
        Read the{' '}
        <Link
          to="/why-free"
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          /why-free
        </Link>{' '}
        page for the long version; the short version is the entire
        business model is subscriptions, not data.
      </>
    ),
  },
  {
    question: "Why aren't retail-broker one-click connections on free?",
    answer: (
      <>
        One-click aggregator connections to Robinhood, Webull, Public,
        M1, and SoFi cost us about $2 per connected user per month. The
        math doesn't work on free — at 10,000 free users that's $20K/mo
        of pure cost before we earn a dollar. Pro ($29/mo) covers that
        pass-through with zero markup. Brokers with direct integrations
        (Schwab + Tastytrade via OAuth, IBKR via FlexQuery + IB Gateway,
        E*TRADE via OAuth sandbox today, and soon Tradier + Coinbase
        via OAuth) stay free forever — we don't pay a per-connection
        fee for
        those, so you don't either.
      </>
    ),
  },
  {
    question: 'Can I change tiers anytime?',
    answer: (
      <>
        When self-serve checkout ships, upgrades will take effect
        immediately and the difference will be prorated. Until then,
        contact support to switch tiers.
      </>
    ),
  },
  {
    question: 'What happens if I cancel?',
    answer: (
      <>
        Your data stays. You drop to the Free tier and keep the flagship
        charts, CSV import, and direct broker connections (Schwab +
        Tastytrade OAuth, IBKR FlexQuery + IB Gateway, E*TRADE OAuth
        sandbox today, and every additional direct-OAuth broker we add
        in v1) forever. No "cancel and lose your portfolio" trap.
      </>
    ),
  },
  {
    question: 'How is annual billing different from monthly?',
    answer: (
      <>
        Annual billing on Lite, Pro, Pro+, and Quant Desk gives you
        about 20% off the monthly rate. Same features, billed once a
        year. If you want to switch between monthly and annual billing,
        contact support and we&apos;ll help you make the change.
      </>
    ),
  },
];

interface PricingFAQProps {
  className?: string;
}

export const PricingFAQ: React.FC<PricingFAQProps> = ({ className }) => {
  // Open the first item by default so the section never reads as a
  // wall of titles. Subsequent items remain closed for scannability.
  const [openIndex, setOpenIndex] = React.useState<number | null>(0);

  return (
    <section
      aria-labelledby="pricing-faq-heading"
      className={cn('mx-auto w-full max-w-3xl', className)}
    >
      <header className="mb-8 flex flex-col gap-3 text-center sm:text-left">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Questions
        </p>
        <h2
          id="pricing-faq-heading"
          className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl"
        >
          Things people actually ask
        </h2>
      </header>

      <ul className="flex flex-col gap-2">
        {FAQ_ENTRIES.map((entry, index) => {
          const isOpen = openIndex === index;
          return (
            <li key={entry.question}>
              <Collapsible
                open={isOpen}
                onOpenChange={(next) =>
                  setOpenIndex(next ? index : null)
                }
              >
                <div className="overflow-hidden rounded-xl border border-border bg-card/60">
                  <CollapsibleTrigger
                    className={cn(
                      'flex w-full items-center justify-between gap-3 px-4 py-4 text-left text-sm font-medium transition-colors',
                      'hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      'sm:text-base',
                    )}
                    aria-controls={`faq-panel-${index}`}
                  >
                    <span>{entry.question}</span>
                    <ChevronDown
                      aria-hidden
                      className={cn(
                        'size-4 shrink-0 text-muted-foreground transition-transform duration-200',
                        isOpen && 'rotate-180',
                      )}
                    />
                  </CollapsibleTrigger>
                  <CollapsibleContent
                    id={`faq-panel-${index}`}
                    className="px-4 pb-4 text-sm leading-relaxed text-muted-foreground sm:text-base"
                  >
                    {entry.answer}
                  </CollapsibleContent>
                </div>
              </Collapsible>
            </li>
          );
        })}
      </ul>
    </section>
  );
};

export default PricingFAQ;
