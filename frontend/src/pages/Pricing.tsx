/**
 * `Pricing` — public `/pricing` page.
 *
 * Renders the 6-tier comparison sourced from
 * `GET /api/v1/pricing/catalog` (which itself reads from
 * `feature_catalog.py` + `tier_catalog.py` — the single sources of
 * truth for what a user gets at what price). Mobile-stacked, desktop
 * side-by-side. Honest "Your subscription covers X" microcopy per
 * D106 + the v1 sprint plan section 3l-iii.
 *
 * Stripe Checkout note
 * --------------------
 * No new Stripe surface lives in this PR (per the v1 sprint plan
 * constraint "no NEW Stripe routes"). For paid CTAs we route
 * unauthenticated visitors to `/register?upgrade=<tier>` and show a
 * "Checkout coming online" disabled state for already-signed-in users.
 * The actual checkout-session creation route lands in a follow-up PR;
 * once it does, the `handleCtaClick` branch flips to call that
 * endpoint without any other change to this page.
 */

import * as React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, ShieldCheck, Sparkles } from 'lucide-react';

import api from '@/services/api';
import { useAuthOptional } from '@/context/AuthContext';
import useEntitlement from '@/hooks/useEntitlement';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { TierCard } from '@/components/pricing/TierCard';
import { PricingFAQ } from '@/components/pricing/PricingFAQ';
import type {
  PricingCatalogResponse,
  PricingTier,
} from '@/types/pricing';
import type { SubscriptionTier } from '@/types/entitlement';
import { tierRank } from '@/types/entitlement';

const HEADLINE = 'Gorgeous charts. Forever free.';
const SUBHEAD =
  "Pay only when you want broker connections we don't yet build for free, AI chat, autotrade, or backtests. We never markup third-party costs — your subscription covers them at cost.";

/** Tier we visually highlight as "recommended" when the visitor is on Free. */
const HIGHLIGHTED_TIER: SubscriptionTier = 'pro';

/**
 * Note shown under disabled paid CTAs while checkout-session creation
 * is still being wired (intentionally honest — no fake spinner, no fake
 * "Coming soon" without context).
 */
const CHECKOUT_PENDING_NOTE =
  'Self-serve checkout is rolling out shortly. Email founders@axiomfolio.com to upgrade today.';

const Pricing: React.FC = () => {
  const auth = useAuthOptional();
  const isAuthenticated = Boolean(auth?.token);

  const {
    tier: currentTier,
    isLoading: entitlementLoading,
    isError: entitlementError,
  } = useEntitlement();

  const catalogQuery = useQuery<PricingCatalogResponse | null>({
    queryKey: ['pricing', 'catalog'],
    queryFn: async () => {
      const res = await api.get<PricingCatalogResponse>(
        '/pricing/catalog',
      );
      return res?.data ?? null;
    },
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    retry: 2,
  });

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-card/60 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
          <Link
            to="/"
            className="font-heading text-lg font-semibold tracking-tight"
          >
            AxiomFolio
          </Link>
          <nav aria-label="Primary" className="flex items-center gap-4 text-sm">
            <Link
              to="/why-free"
              className="font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            >
              Why free
            </Link>
            <Link
              to="/login"
              className="font-medium text-primary underline-offset-4 hover:underline"
            >
              Sign in
            </Link>
            <Link
              to="/register"
              className="font-medium text-primary underline-offset-4 hover:underline"
            >
              Register
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <PricingHero />

        <section
          aria-labelledby="pricing-tiers-heading"
          className="mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 sm:pb-24"
        >
          <h2 id="pricing-tiers-heading" className="sr-only">
            Subscription tiers
          </h2>

          {catalogQuery.isLoading ? (
            <PricingTiersSkeleton />
          ) : catalogQuery.isError || !catalogQuery.data ? (
            <PricingErrorState
              onRetry={() => {
                void catalogQuery.refetch();
              }}
            />
          ) : (
            <PricingTiersGrid
              catalog={catalogQuery.data}
              currentTier={isAuthenticated ? currentTier : null}
              entitlementLoading={
                isAuthenticated ? entitlementLoading : false
              }
              entitlementError={
                isAuthenticated ? entitlementError : false
              }
              isAuthenticated={isAuthenticated}
            />
          )}
        </section>

        <section className="border-t border-border bg-muted/20 py-16 sm:py-20">
          <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
            <PricingFAQ />
          </div>
        </section>

        <PricingFooter />
      </main>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

const PricingHero: React.FC = () => (
  <section className="mx-auto w-full max-w-4xl px-4 pb-12 pt-16 text-center sm:px-6 sm:pb-16 sm:pt-20">
    <p className="inline-flex items-center justify-center gap-1.5 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
      <Sparkles aria-hidden className="size-3" />
      Pricing
    </p>
    <h1 className="mt-6 font-heading text-4xl font-semibold tracking-tight sm:text-5xl md:text-6xl">
      {HEADLINE}
    </h1>
    <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
      {SUBHEAD}
    </p>
    <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
      <Button asChild size="lg">
        <Link to="/register">
          Get started free
          <ArrowRight aria-hidden className="size-4" />
        </Link>
      </Button>
      <Button asChild variant="outline" size="lg">
        <Link to="/why-free">
          <ShieldCheck aria-hidden className="size-4" />
          Why we're free
        </Link>
      </Button>
    </div>
  </section>
);

// ---------------------------------------------------------------------------
// Tier grid (responsive)
// ---------------------------------------------------------------------------

interface PricingTiersGridProps {
  catalog: PricingCatalogResponse;
  /** Effective tier for an authenticated visitor; `null` for logged-out. */
  currentTier: SubscriptionTier | null;
  entitlementLoading: boolean;
  entitlementError: boolean;
  isAuthenticated: boolean;
}

const PricingTiersGrid: React.FC<PricingTiersGridProps> = ({
  catalog,
  currentTier,
  entitlementLoading,
  entitlementError,
  isAuthenticated,
}) => {
  // While we know the visitor is authenticated but their entitlement
  // hasn't loaded yet, swap the tier cards for skeletons rather than
  // rendering CTAs that might briefly say "Upgrade" on the user's own
  // current plan.
  if (entitlementLoading) {
    return <PricingTiersSkeleton />;
  }

  return (
    <>
      {entitlementError ? (
        <p className="mb-6 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-center text-sm text-destructive">
          We couldn't load your current plan. Tier-specific buttons are
          unavailable until you reload, but the pricing details below
          are accurate.
        </p>
      ) : null}

      <div
        className={cn(
          'grid gap-4',
          // 6 tiers don't fit comfortably side-by-side at most widths.
          // Stack on small, 2-up on md, 3-up on lg, 6-up on 2xl.
          'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6',
        )}
      >
        {catalog.tiers.map((tier) => (
          <TierCardWithCheckout
            key={tier.tier}
            tier={tier}
            currentTier={currentTier}
            isAuthenticated={isAuthenticated}
            currency={catalog.currency}
          />
        ))}
      </div>
    </>
  );
};

// ---------------------------------------------------------------------------
// Per-tier CTA wiring
// ---------------------------------------------------------------------------

interface TierCardWithCheckoutProps {
  tier: PricingTier;
  currentTier: SubscriptionTier | null;
  isAuthenticated: boolean;
  currency: string;
}

const TierCardWithCheckout: React.FC<TierCardWithCheckoutProps> = ({
  tier,
  currentTier,
  isAuthenticated,
  currency,
}) => {
  const navigate = useNavigate();
  const isCurrent = currentTier === tier.tier;

  // Highlight a single recommended tier ONLY for visitors who aren't
  // signed in yet (or who are still on Free). Once a user has actually
  // upgraded, the highlight would just be visual noise.
  const isHighlighted =
    tier.tier === HIGHLIGHTED_TIER &&
    (!isAuthenticated || tierRank(currentTier) <= tierRank('free'));

  const handleClick = React.useCallback(() => {
    if (isCurrent) return;

    // Free tier (or any tier with an explicit public route) routes to
    // that destination — no auth or checkout machinery involved.
    if (tier.cta_route) {
      navigate(tier.cta_route);
      return;
    }

    // Enterprise: contact sales.
    if (tier.is_contact_sales) {
      window.location.assign(
        `mailto:founders@axiomfolio.com?subject=${encodeURIComponent(
          `AxiomFolio Enterprise inquiry — ${tier.name}`,
        )}`,
      );
      return;
    }

    // Paid self-serve tier: route unauthenticated visitors to the
    // signup flow with the intended tier carried in the URL so the
    // post-signup experience can pick checkout up where we left off.
    if (!isAuthenticated) {
      navigate(`/register?upgrade=${encodeURIComponent(tier.tier)}`);
      return;
    }

    // Authenticated paid CTA falls through to the disabled state with
    // the explanatory note (`ctaDisabled` below). Intentional: there
    // is no checkout-session route in this PR (see file header).
  }, [isCurrent, tier, isAuthenticated, navigate]);

  // Determine whether to disable the CTA + show the checkout-pending
  // note.
  const isPaidSelfServe = !tier.is_contact_sales && !tier.cta_route;
  const ctaDisabled = isAuthenticated && isPaidSelfServe && !isCurrent;
  const ctaNote = ctaDisabled ? CHECKOUT_PENDING_NOTE : undefined;

  return (
    <TierCard
      tier={tier}
      isCurrent={isCurrent}
      isHighlighted={isHighlighted}
      ctaDisabled={ctaDisabled}
      ctaNote={ctaNote}
      onCtaClick={handleClick}
      currency={currency}
    />
  );
};

// ---------------------------------------------------------------------------
// Loading + error states
// ---------------------------------------------------------------------------

const PricingTiersSkeleton: React.FC = () => (
  <div
    aria-busy="true"
    aria-label="Loading pricing tiers"
    className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6"
  >
    {Array.from({ length: 6 }).map((_, i) => (
      <div
        key={i}
        className="flex h-[480px] flex-col gap-4 rounded-2xl border border-border bg-card/40 p-6"
      >
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="mt-2 h-10 w-1/2" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="mt-2 h-10 w-full" />
        <div className="mt-4 flex flex-col gap-2 border-t border-border pt-4">
          {Array.from({ length: 5 }).map((__, k) => (
            <Skeleton key={k} className="h-3 w-full" />
          ))}
        </div>
      </div>
    ))}
  </div>
);

interface PricingErrorStateProps {
  onRetry: () => void;
}

const PricingErrorState: React.FC<PricingErrorStateProps> = ({
  onRetry,
}) => (
  <div
    role="alert"
    className="mx-auto flex max-w-md flex-col items-center gap-4 rounded-2xl border border-border bg-card/60 p-8 text-center"
  >
    <h2 className="font-heading text-lg font-semibold">
      We couldn't load pricing right now.
    </h2>
    <p className="text-sm text-muted-foreground">
      Reload the page or come back in a moment. The catalog is served
      directly from the same source the in-app upgrade prompts use, so
      this is almost always a transient network issue.
    </p>
    <Button type="button" onClick={onRetry}>
      Try again
    </Button>
  </div>
);

// ---------------------------------------------------------------------------
// Footer
// ---------------------------------------------------------------------------

const PricingFooter: React.FC = () => (
  <footer className="border-t border-border bg-card/40">
    <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-4 py-8 text-xs text-muted-foreground sm:flex-row sm:items-center sm:px-6">
      <p>
        Built so we can stay free. No ads. No data sale. Ever. Read the
        full reasoning on{' '}
        <Link
          to="/why-free"
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          /why-free
        </Link>
        .
      </p>
      <div className="flex items-center gap-4">
        <Link
          to="/why-free"
          className="font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          Why free
        </Link>
        <Link
          to="/login"
          className="font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          Sign in
        </Link>
        <Link
          to="/register"
          className="font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          Register
        </Link>
      </div>
    </div>
  </footer>
);

export default Pricing;
