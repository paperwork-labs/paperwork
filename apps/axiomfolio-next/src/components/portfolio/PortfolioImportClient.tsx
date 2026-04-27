"use client";

/**
 * PortfolioImport (`/portfolio/import?broker=<slug>`) — placeholder shell.
 *
 * The full CSV import flow may ship in a follow-up. This stub renders the
 * right copy so Connect hub CTAs do not 404.
 */
import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { ChartGlassCard } from "@/components/ui/ChartGlassCard";
import { Page, PageHeader } from "@/components/ui/Page";

import { BrokerLogo } from "@/components/connect/BrokerLogo";

const PRETTY_NAME: Record<string, string> = {
  fidelity: "Fidelity",
  vanguard: "Vanguard",
  robinhood: "Robinhood",
  jpmorgan: "JPMorgan Self-Directed",
  merrill: "Merrill Edge",
  wells_fargo: "Wells Fargo Advisors",
  webull: "Webull",
  m1_finance: "M1 Finance",
  sofi: "SoFi Invest",
  public: "Public",
  generic_csv: "Generic CSV",
  wealthfront: "Wealthfront",
  betterment: "Betterment",
  coinbase_pro: "Coinbase Pro (Advanced)",
};

export default function PortfolioImportClient() {
  const searchParams = useSearchParams();
  const slug = searchParams.get("broker") ?? "generic_csv";
  const brokerName = PRETTY_NAME[slug] ?? "your broker";

  return (
    <Page>
      <PageHeader
        title="Import accounts"
        subtitle="Bring positions and trades from any broker — CSV, statement PDF, or guided template."
      />

      <ChartGlassCard level="resting" padding="lg">
        <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
          <BrokerLogo
            slug={slug}
            name={brokerName}
            remoteLogoUrl={`/broker-logos/${slug}.svg`}
            size={56}
          />
          <div className="min-w-0 flex-1">
            <h2 className="font-heading text-lg font-medium text-foreground">{brokerName} import</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Beautiful CSV import is on the way — expected this week. We&apos;re wiring up template
              detection, dry-run previews, and a one-click re-import on every CSV update so your
              positions stay fresh.
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <Button asChild type="button" variant="outline">
            <Link href="/connect">Back to Connect</Link>
          </Button>
          <Button asChild type="button" variant="ghost">
            <Link href="/why-free">Why CSV?</Link>
          </Button>
        </div>
      </ChartGlassCard>
    </Page>
  );
}
