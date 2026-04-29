"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Page, PageHeader, TabbedPageShell } from "@paperwork-labs/ui";

const HoldingsTab = React.lazy(() => import("@/components/portfolio/PortfolioHoldingsClient"));
const OptionsTab = React.lazy(() => import("@/components/portfolio/PortfolioOptionsClient"));
const CategoriesTab = React.lazy(() => import("@/components/portfolio/PortfolioCategoriesClient"));

const POSITIONS_TABS = [
  { id: "holdings" as const, label: "Holdings", Content: HoldingsTab },
  { id: "options" as const, label: "Options", Content: OptionsTab },
  { id: "categories" as const, label: "Categories", Content: CategoriesTab },
];

export type PositionsShellTabId = (typeof POSITIONS_TABS)[number]["id"];

const TAB_ALIASES: Record<string, PositionsShellTabId> = {
  lots: "categories",
};

export default function PositionsTabShellClient() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const rawTab = searchParams.get("tab") ?? "";
  const aliasTarget = TAB_ALIASES[rawTab];
  const spKey = searchParams.toString();

  React.useEffect(() => {
    if (!aliasTarget) return;
    const next = new URLSearchParams(spKey);
    next.set("tab", aliasTarget);
    const q = next.toString();
    router.replace(q ? `${pathname}?${q}` : pathname);
  }, [aliasTarget, pathname, router, spKey]);

  return (
    <Page>
      <div className="flex flex-col gap-4">
        <PageHeader
          title="Positions"
          subtitle="Holdings, options, and category buckets — all the instruments you currently own."
        />
        <TabbedPageShell tabs={POSITIONS_TABS} defaultTab="holdings" />
      </div>
    </Page>
  );
}
