"use client";

import * as React from "react";

import { Page, PageHeader } from "@paperwork-labs/ui";
import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import SentimentBanner from "@/components/regime/SentimentBanner";
import { SyncStatusStrip } from "@/components/portfolio/SyncStatusStrip";

const OverviewTab = React.lazy(() => import("@/components/portfolio/tabs/OverviewTabClient"));
const AllocationTab = React.lazy(() => import("@/components/portfolio/tabs/AllocationTabClient"));
const PerformanceTab = React.lazy(() => import("@/components/portfolio/tabs/PerformanceTabClient"));
const RiskTab = React.lazy(() => import("@/components/portfolio/tabs/RiskTabClient"));

const PORTFOLIO_TABS = [
  { id: "overview" as const, label: "Overview", Content: OverviewTab },
  { id: "allocation" as const, label: "Allocation", Content: AllocationTab },
  { id: "performance" as const, label: "Performance", Content: PerformanceTab },
  { id: "risk" as const, label: "Risk", Content: RiskTab },
];

export type PortfolioShellTabId = (typeof PORTFOLIO_TABS)[number]["id"];

export default function PortfolioTabShellClient() {
  return (
    <Page>
      <div className="flex flex-col gap-4">
        <PageHeader
          title="Portfolio"
          subtitle="Overview, allocation, performance history, and risk metrics"
          rightContent={<SyncStatusStrip />}
        />

        <SentimentBanner />

        <TabbedPageShell tabs={PORTFOLIO_TABS} defaultTab="overview" />
      </div>
    </Page>
  );
}
