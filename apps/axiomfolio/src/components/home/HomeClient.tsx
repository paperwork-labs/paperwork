"use client";

/**
 * Home — the warm companion landing page (J4).
 *
 * Composition:
 *   <HomeHero />      NAV + 30d sparkline + regime-tinted greeting
 *   <NerveCenter />   Up to 5 attention items (stops, ex-div, runners)
 *   <YourBook />      Top 5–8 positions by market value
 *   <QuietFooter />   YTD income, YTD realized, heat, concentration top-5
 *
 * Broker presence is derived live from `useAccountBalances().data?.length > 0`
 * — #448 deleted the previous `appSettings` / `get_portfolio_user` gate.
 * When no broker is connected, the hero inlines a "Connect a broker" CTA and
 * the other sections render their own quiet empty states.
 *
 * Each section is `React.memo`'d so regime refetches don't re-render the
 * whole composition. Hovering a section header prefetches the matching deep
 * page query.
 */
import * as React from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";

import { HomeHeroGated } from "@/components/home/HomeHero";
import { NerveCenter } from "@/components/home/NerveCenter";
import { QuietFooter } from "@/components/home/QuietFooter";
import { YourBook } from "@/components/home/YourBook";
import { Page } from "@paperwork-labs/ui";
import { portfolioApi } from "@/services/api";

interface SectionHeadingProps {
  children: React.ReactNode;
  href?: string;
  onMouseEnter?: () => void;
}

function SectionHeading({ children, href, onMouseEnter }: SectionHeadingProps) {
  const content = (
    <span className="inline-flex items-center gap-1 font-heading text-sm font-medium tracking-tight text-muted-foreground hover:text-foreground">
      {children}
    </span>
  );
  if (href) {
    return (
      <Link href={href} onMouseEnter={onMouseEnter} className="inline-flex">
        {content}
      </Link>
    );
  }
  return (
    <span onMouseEnter={onMouseEnter} className="inline-flex">
      {content}
    </span>
  );
}

export default function HomeClient() {
  const queryClient = useQueryClient();

  const prefetchPositions = React.useCallback(() => {
    void queryClient.prefetchQuery({
      queryKey: ["portfolioStocks", undefined],
      queryFn: async () => portfolioApi.getStocks(),
    });
  }, [queryClient]);

  const prefetchDashboard = React.useCallback(() => {
    void queryClient.prefetchQuery({
      queryKey: ["home-hero-dashboard"],
      queryFn: () => portfolioApi.getDashboard(),
    });
  }, [queryClient]);

  const prefetchPnl = React.useCallback(() => {
    void queryClient.prefetchQuery({
      queryKey: ["portfolio-pnl-summary", undefined],
      queryFn: () => portfolioApi.getPnlSummary(),
    });
  }, [queryClient]);

  return (
    <Page>
      <div className="flex flex-col gap-5">
        <section aria-label="Portfolio overview" onMouseEnter={prefetchDashboard}>
          <HomeHeroGated />
        </section>

        <section aria-label="Attention feed">
          <div className="mb-2 flex items-center justify-between">
            <SectionHeading href="/portfolio" onMouseEnter={prefetchPositions}>
              Attention
            </SectionHeading>
          </div>
          <NerveCenter />
        </section>

        <section aria-label="Top holdings">
          <div className="mb-2 flex items-center justify-between">
            <SectionHeading href="/portfolio/holdings" onMouseEnter={prefetchPositions}>
              Book
            </SectionHeading>
          </div>
          <YourBook />
        </section>

        <section aria-label="Portfolio stats">
          <div className="mb-2 flex items-center justify-between">
            <SectionHeading onMouseEnter={prefetchPnl}>Stats</SectionHeading>
          </div>
          <QuietFooter />
        </section>
      </div>
    </Page>
  );
}
