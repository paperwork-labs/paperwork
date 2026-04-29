"use client";

import { lazy, useMemo } from "react";
import Link from "next/link";

import {
  TabbedPageShell,
  type TabbedShellTabDef,
} from "@/components/layout/TabbedPageShellNext";
import type { SelfImprovementPayload } from "@/lib/self-improvement";

export type SelfImprovementClientProps = {
  payload: SelfImprovementPayload;
  brainConfigured: boolean;
};

export function SelfImprovementClient({ payload, brainConfigured }: SelfImprovementClientProps) {
  const tabs = useMemo((): readonly TabbedShellTabDef<
    | "learning"
    | "promotions"
    | "outcomes"
    | "retros"
    | "automation-state"
    | "procedural-memory"
    | "index"
  >[] => {
    const learningTab = lazy(() =>
      import("./_tabs/learning-tab").then((m) => ({
        default: () => <m.LearningTab payload={payload} brainConfigured={brainConfigured} />,
      })),
    );
    const promotionsTab = lazy(() =>
      import("./_tabs/promotions-tab").then((m) => ({
        default: () => <m.PromotionsTab payload={payload} />,
      })),
    );
    const outcomesTab = lazy(() =>
      import("./_tabs/outcomes-tab").then((m) => ({
        default: () => <m.OutcomesTab payload={payload} />,
      })),
    );
    const retrosTab = lazy(() =>
      import("./_tabs/retros-tab").then((m) => ({
        default: () => <m.RetrosTab payload={payload} />,
      })),
    );
    const automationTab = lazy(() =>
      import("./_tabs/automation-state-tab").then((m) => ({
        default: () => <m.AutomationStateTab payload={payload} />,
      })),
    );
    const proceduralTab = lazy(() =>
      import("./_tabs/procedural-memory-tab").then((m) => ({
        default: () => <m.ProceduralMemoryTab payload={payload} />,
      })),
    );
    const indexTab = lazy(() =>
      import("./_tabs/index-tab").then((m) => ({
        default: () => <m.IndexTab payload={payload} brainConfigured={brainConfigured} />,
      })),
    );

    return [
      { id: "learning", label: "Learning", Content: learningTab },
      { id: "promotions", label: "Promotions", Content: promotionsTab },
      { id: "outcomes", label: "Outcomes", Content: outcomesTab },
      { id: "retros", label: "Retros", Content: retrosTab },
      { id: "automation-state", label: "Automation", Content: automationTab },
      { id: "procedural-memory", label: "Procedural memory", Content: proceduralTab },
      { id: "index", label: "Index", Content: indexTab },
    ];
  }, [payload, brainConfigured]);

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
              Self-improvement
            </h1>
            <p className="text-sm text-zinc-400">
              Brain learning loop — dispatch outcomes, promotions, PR horizons, retros, schedulers, and
              procedural memory. PR P appends an Audits tab.
            </p>
          </div>
          <Link
            href="/admin/brain/conversations"
            className="shrink-0 rounded-lg border border-zinc-700 bg-zinc-900/60 px-3 py-2 text-sm text-zinc-200 hover:border-zinc-500"
          >
            Brain inbox →
          </Link>
        </div>
      </header>

      <TabbedPageShell tabs={tabs} defaultTab="learning" />
    </div>
  );
}
