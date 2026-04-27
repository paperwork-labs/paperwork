"use client";

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

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { MarketingFooter } from "@/components/layout/MarketingFooter";
import { MarketingHeader } from "@/components/layout/MarketingHeader";
import api from "@/services/api";
import { Button } from "@/components/ui/button";
import { TierCard } from "@/components/pricing/TierCard";
import { ComparisonTable } from "@/components/pricing/ComparisonTable";
import { PricingFAQ } from "@/components/pricing/PricingFAQ";
import { PageContainer } from "@/components/ui/Page";
import type { PricingCatalogResponse, PricingTier } from "@/types/pricing";

// Contact-sales mailto target for Enterprise / other high-touch tiers.
// Kept here (not in the catalog payload) so the public pricing API
// doesn't need to leak an exact inbox as part of its wire format.
const CONTACT_SALES_EMAIL = "hello@axiomfolio.com";

export default function PricingPage() {
  const router = useRouter();

  const catalogQuery = useQuery<PricingCatalogResponse>({
    queryKey: ["pricing", "catalog"],
    queryFn: async () => {
      const res = await api.get<PricingCatalogResponse>("/pricing/catalog");
      return res.data;
    },
  });

  const handleCtaClick = React.useCallback(
    (tier: PricingTier) => {
      if (tier.is_contact_sales) {
        const subject = encodeURIComponent(`Interested in ${tier.name}`);
        window.location.href = `mailto:${CONTACT_SALES_EMAIL}?subject=${subject}`;
        return;
      }
      if (tier.cta_route) {
        router.push(tier.cta_route);
        return;
      }
      router.push(`/register?upgrade=${encodeURIComponent(tier.tier)}`);
    },
    [router],
  );

  const renderBody = () => {
    if (catalogQuery.isLoading) return <p className="text-muted-foreground">Loading pricing...</p>;
    if (catalogQuery.isError) return <p className="text-destructive">Could not load pricing catalog.</p>;
    if (!catalogQuery.data?.tiers.length) return <p className="text-muted-foreground">No tiers configured.</p>;

    const tiers = catalogQuery.data.tiers;
    const featured = tiers.find((t) => t.tier === "pro") ?? tiers[0];
    const compact = tiers.filter((t) => t.tier !== featured.tier && t.tier !== "enterprise");
    const enterprise = tiers.find((t) => t.tier === "enterprise");

    return (
      <div className="space-y-8">
        <section>
          <h2 className="mb-4 text-xl font-semibold">Recommended</h2>
          <TierCard
            tier={featured}
            variant="featured"
            currency={catalogQuery.data.currency}
            onCtaClick={() => handleCtaClick(featured)}
          />
        </section>
        <section>
          <h2 className="mb-4 text-xl font-semibold">Plans</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {compact.map((tier) => (
              <TierCard
                key={tier.tier}
                tier={tier}
                variant="compact"
                currency={catalogQuery.data.currency}
                onCtaClick={() => handleCtaClick(tier)}
              />
            ))}
          </div>
        </section>
        {enterprise ? (
          <section>
            <h2 className="mb-4 text-xl font-semibold">Enterprise</h2>
            <TierCard
              tier={enterprise}
              variant="enterprise"
              currency={catalogQuery.data.currency}
              onCtaClick={() => handleCtaClick(enterprise)}
            />
            <p className="text-center text-sm text-muted-foreground">
              Prefer email?{" "}
              <a
                className="font-mono text-foreground underline-offset-4 hover:underline"
                href={`mailto:${CONTACT_SALES_EMAIL}`}
              >
                {CONTACT_SALES_EMAIL}
              </a>
            </p>
          </section>
        ) : null}
        <ComparisonTable catalog={catalogQuery.data} />
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <MarketingHeader />
      <main>
        <PageContainer width="wide" className="space-y-8 py-12">
          <header className="space-y-3 text-center">
            <h1 className="font-heading text-4xl font-semibold tracking-tight">Simple, honest pricing</h1>
            <p className="text-muted-foreground">
              Free forever for core visuals. Upgrade when you need BYOK, advanced MCP scopes, and research tooling.
            </p>
            <div className="flex items-center justify-center gap-3">
              <Button asChild>
                <Link href="/register">Get started</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/why-free">Why free</Link>
              </Button>
            </div>
          </header>
          {renderBody()}
          <PricingFAQ />
        </PageContainer>
      </main>
      <MarketingFooter />
    </div>
  );
}
