/**
 * PortfolioImport (`/portfolio/import?broker=<slug>`) — placeholder shell.
 *
 * The actual CSV import flow ships in PR 3h-ii (depends on this PR's
 * connection-hub UX). This stub renders the right copy so the buttons
 * on the Connect hub never lead to a 404 mid-launch.
 */
import * as React from "react";
import { Link, useSearchParams } from "react-router-dom";

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

export default function PortfolioImport() {
  const [params] = useSearchParams();
  const slug = params.get("broker") ?? "generic_csv";
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
            src={`/broker-logos/${slug}.svg`}
            alt={`${brokerName} logo`}
            monogram={brokerName}
            size={56}
          />
          <div className="min-w-0 flex-1">
            <h2 className="font-heading text-lg font-medium text-foreground">
              {brokerName} import
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Beautiful CSV import is on the way — expected this week. We&apos;re
              wiring up template detection, dry-run previews, and a one-click
              re-import on every CSV update so your positions stay fresh.
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <Button asChild type="button" variant="outline">
            <Link to="/connect">Back to Connect</Link>
          </Button>
          <Button asChild type="button" variant="ghost">
            <Link to="/why-free">Why CSV?</Link>
          </Button>
        </div>
      </ChartGlassCard>
    </Page>
  );
}
