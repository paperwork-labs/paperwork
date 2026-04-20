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
        Because most "free" portfolio apps cost you $10–20/month to look
        at your own data, and we don't want to be that. Snowball-class
        visualization, three-broker OAuth (Schwab, IBKR, Tastytrade),
        CSV import for any other broker, real-time prices, public
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
        for. We tell you per tier — "Lite covers SnapTrade's $2/user/mo
        cost, zero markup", "Pro covers OpenAI tokens for unlimited
        chat", and so on. Second: those apps depend on aggregators
        (Plaid, Yodlee) that charge them per connected account every
        month, so they have to charge you to read your own portfolio. We
        chose CSV + direct OAuth for the free tier so we never have a
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
    question: "Why isn't there a SnapTrade option on the free tier?",
    answer: (
      <>
        SnapTrade charges us about $2 per connected user per month for
        one-click broker connections to Robinhood, Webull, Public, M1,
        and SoFi. The math doesn't work on free — at 10,000 free users
        that's $20K/month of pure cost before we earn a dollar. Lite
        ($20/mo) covers that pass-through, and we take zero markup on
        the SnapTrade line.
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
        charts, CSV import, and three-broker OAuth (Schwab, IBKR,
        Tastytrade) forever. No "cancel and lose your portfolio" trap.
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
