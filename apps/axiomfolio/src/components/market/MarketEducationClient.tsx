"use client";

import * as React from "react";

import { Page, PageHeader } from "@/components/ui/Page";
import { TabbedPageShell } from "@/components/layout/TabbedPageShell";

const GlossaryTab = React.lazy(() => import("@/components/market-education/tabs/GlossaryTab"));
const DeepDivesTab = React.lazy(() => import("@/components/market-education/tabs/DeepDivesTab"));

const EDUCATION_TABS = [
  { id: "deep-dives" as const, label: "System Deep-Dives", Content: DeepDivesTab },
  { id: "glossary" as const, label: "Glossary", Content: GlossaryTab },
];

export default function MarketEducationClient() {
  return (
    <Page>
      <PageHeader
        title="Stage Analysis — Education"
        subtitle="Oliver Kell&apos;s refinement of Weinstein Stage Analysis. SMA150 anchor, 10 sub-stages, Market Regime Engine, Scan Overlay, Exit Cascade, and ATR-based Position Sizing."
      />

      <TabbedPageShell tabs={EDUCATION_TABS} defaultTab="deep-dives" />

      <div className="mt-8 border-t border-border pt-4">
        <p className="text-xs text-muted-foreground italic">
          Reflects the same calculations as the backend. Stage classification: backend/services/market/stage_classifier.py;
          indicators: backend/services/market/indicator_engine.py
        </p>
      </div>
    </Page>
  );
}
