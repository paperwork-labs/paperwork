/**
 * `TierCard` — one column on the public pricing page.
 *
 * Wraps `<ChartGlassCard>` so the card frame inherits the same depth +
 * inset-highlight treatment as every flagship chart on the site (the
 * pricing page is itself a marketing artifact, so it should feel like
 * the rest of the product).
 *
 * Renders, from top to bottom:
 *   1. tier name + tagline
 *   2. price ($/mo with optional annual badge if a discount exists)
 *   3. the transparent "your subscription covers X" microcopy (D106)
 *   4. CTA (Get started / Upgrade / Contact sales / Your plan)
 *   5. feature checklist sourced from the pricing catalog
 *
 * The card never decides the CTA target itself — the parent page wires
 * routes/handlers via `onCtaClick` so all auth/checkout logic stays in
 * one place.
 */

import * as React from 'react';
import { Check } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { PricingTier } from '@/types/pricing';
import { formatPrice } from '@/components/pricing/format';

interface TierCardProps {
  tier: PricingTier;
  variant?: 'featured' | 'compact' | 'enterprise';
  /** True when this tier matches the signed-in user's effective tier. */
  isCurrent?: boolean;
  /** True when this tier should visually pop as the recommended pick. */
  isHighlighted?: boolean;
  /** Disable the CTA (rendered with explanatory text below). */
  ctaDisabled?: boolean;
  /** Optional explanatory note shown under a disabled CTA. */
  ctaNote?: string;
  /** Click handler for the CTA. Parent decides where it actually goes. */
  onCtaClick?: () => void;
  /** Currency code from the catalog (currently always `"USD"`). */
  currency: string;
}

export const TierCard: React.FC<TierCardProps> = ({
  tier,
  variant = 'compact',
  isCurrent = false,
  isHighlighted = false,
  ctaDisabled = false,
  ctaNote,
  onCtaClick,
  currency,
}) => {
  const monthlyDisplay = tier.monthly_price_usd
    ? formatPrice(tier.monthly_price_usd, currency)
    : 'Custom';
  const ctaLabel = isCurrent ? 'Your plan' : tier.cta_label;
  const ctaVariant: React.ComponentProps<typeof Button>['variant'] =
    isCurrent ? 'outline' : isHighlighted ? 'default' : 'secondary';
  const compactFeatures = variant === 'compact' ? tier.new_features : tier.features;

  return (
    <article
      className={cn(
        'rounded-2xl border border-border bg-card p-6',
        variant === 'featured' && 'border-primary/40 shadow-lg',
        variant === 'enterprise' && 'bg-muted/30',
      )}
    >
      <header className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-heading text-xl font-semibold tracking-tight">
            {tier.name}
          </h3>
          {variant === 'featured' ? (
            <span className="text-xs text-primary">Most popular</span>
          ) : null}
          {isCurrent ? (
            <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
              Current plan
            </span>
          ) : null}
        </div>
        <p className="text-sm text-muted-foreground">{tier.tagline}</p>
      </header>

      <div className="mt-2 flex flex-col gap-3">
        <div className="flex items-baseline gap-1">
          <span className="font-heading text-4xl font-semibold tracking-tight tabular-nums">
            {monthlyDisplay}
          </span>
          {tier.monthly_price_usd ? <span className="text-sm text-muted-foreground">/mo</span> : null}
        </div>
        <p className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs leading-relaxed text-muted-foreground sm:text-sm">
          {tier.covers_copy}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <Button
          type="button"
          variant={ctaVariant}
          size="lg"
          disabled={ctaDisabled || isCurrent}
          onClick={onCtaClick}
          className="w-full justify-center"
          aria-label={`${ctaLabel} — ${tier.name} plan`}
        >
          {ctaLabel}
        </Button>
        {ctaNote && !isCurrent ? (
          <p className="text-center text-xs text-muted-foreground">
            {ctaNote}
          </p>
        ) : null}
      </div>

      <ul className="mt-4 flex flex-col gap-2.5 border-t border-border pt-5 text-sm">
        {compactFeatures.length === 0 ? (
          <li className="text-xs text-muted-foreground">
            Everything in this plan is rolling out soon.
          </li>
        ) : (
          compactFeatures.map((feature) => {
            const isNew = tier.new_features.some((f) => f.key === feature.key);
            return (
              <li
                key={feature.key}
                className="flex items-start gap-2.5"
                data-new={isNew || undefined}
              >
                <Check
                  aria-hidden
                  className={cn(
                    'mt-0.5 size-4 shrink-0',
                    isNew ? 'text-primary' : 'text-[rgb(var(--status-success)/1)]',
                  )}
                />
                <span>
                  <span className="font-medium text-foreground">
                    {feature.title}
                  </span>
                  <span className="ml-2 text-muted-foreground">
                    {feature.description}
                  </span>
                </span>
              </li>
            );
          })
        )}
      </ul>
    </article>
  );
};

export default TierCard;
