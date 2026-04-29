"use client";

import * as React from "react";

import { ChartContext, ChartSlidePanel } from "@/components/market/SymbolChartUI";
import { Page, TabbedPageShell } from "@paperwork-labs/ui";

const IntelligenceBriefTab = React.lazy(
  () => import("@/components/market-intelligence/tabs/IntelligenceBriefTab"),
);

const INTELLIGENCE_TABS = [
  { id: "daily" as const, label: "Daily Digest", Content: IntelligenceBriefTab },
  { id: "weekly" as const, label: "Weekly Brief", Content: IntelligenceBriefTab },
  { id: "monthly" as const, label: "Monthly Review", Content: IntelligenceBriefTab },
];

export default function MarketIntelligenceClient() {
  const [chartSymbol, setChartSymbol] = React.useState<string | null>(null);
  const openChart = React.useCallback((sym: string) => setChartSymbol(sym), []);

  return (
    <ChartContext.Provider value={openChart}>
      <Page>
        <div className="flex flex-col gap-4">
          <h1 className="font-heading text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
            Intelligence Briefs
          </h1>
          <TabbedPageShell tabs={INTELLIGENCE_TABS} defaultTab="daily" />
        </div>
      </Page>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </ChartContext.Provider>
  );
}
