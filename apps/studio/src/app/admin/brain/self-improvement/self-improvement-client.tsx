"use client";

import { createContext, lazy, useContext } from "react";
import Link from "next/link";

import { TabbedPageShell, type StudioTabDef } from "@/components/layout/TabbedPageShellNext";
import type { SelfImprovementPayload } from "@/lib/self-improvement";

export type SelfImprovementClientProps = {
  payload: SelfImprovementPayload;
  brainConfigured: boolean;
};

const SelfImprovementShellContext = createContext<{
  payload: SelfImprovementPayload;
  brainConfigured: boolean;
} | null>(null);

function useSelfImprovementShell() {
  const v = useContext(SelfImprovementShellContext);
  if (!v) {
    throw new Error("Self-improvement tab panels require SelfImprovementShellContext");
  }
  return v;
}

const LearningTabLazy = lazy(() =>
  import("./_tabs/learning-tab").then((m) => ({
    default: function LearningTabHost() {
      const { payload, brainConfigured } = useSelfImprovementShell();
      return <m.LearningTab payload={payload} brainConfigured={brainConfigured} />;
    },
  })),
);

const PromotionsTabLazy = lazy(() =>
  import("./_tabs/promotions-tab").then((m) => ({
    default: function PromotionsTabHost() {
      const { payload } = useSelfImprovementShell();
      return <m.PromotionsTab payload={payload} />;
    },
  })),
);

const OutcomesTabLazy = lazy(() =>
  import("./_tabs/outcomes-tab").then((m) => ({
    default: function OutcomesTabHost() {
      const { payload } = useSelfImprovementShell();
      return <m.OutcomesTab payload={payload} />;
    },
  })),
);

const RetrosTabLazy = lazy(() =>
  import("./_tabs/retros-tab").then((m) => ({
    default: function RetrosTabHost() {
      const { payload } = useSelfImprovementShell();
      return <m.RetrosTab payload={payload} />;
    },
  })),
);

const AutomationStateTabLazy = lazy(() =>
  import("./_tabs/automation-state-tab").then((m) => ({
    default: function AutomationStateTabHost() {
      const { payload } = useSelfImprovementShell();
      return <m.AutomationStateTab payload={payload} />;
    },
  })),
);

const ProceduralMemoryTabLazy = lazy(() =>
  import("./_tabs/procedural-memory-tab").then((m) => ({
    default: function ProceduralMemoryTabHost() {
      const { payload } = useSelfImprovementShell();
      return <m.ProceduralMemoryTab payload={payload} />;
    },
  })),
);

const AuditsTabLazy = lazy(() =>
  import("./_tabs/audits-tab").then((m) => ({
    default: function AuditsTabHost() {
      return (
        <m.AuditsTab
          brainApiUrl={process.env.NEXT_PUBLIC_BRAIN_API_URL ?? null}
          brainApiSecret={process.env.NEXT_PUBLIC_BRAIN_API_SECRET ?? null}
        />
      );
    },
  })),
);

const IndexTabLazy = lazy(() =>
  import("./_tabs/index-tab").then((m) => ({
    default: function IndexTabHost() {
      const { payload, brainConfigured } = useSelfImprovementShell();
      return <m.IndexTab payload={payload} brainConfigured={brainConfigured} />;
    },
  })),
);

const SELF_IMPROVEMENT_TABS: readonly StudioTabDef<
  | "learning"
  | "promotions"
  | "outcomes"
  | "retros"
  | "automation-state"
  | "procedural-memory"
  | "audits"
  | "index"
>[] = [
  { id: "learning", label: "Learning", Content: LearningTabLazy },
  { id: "promotions", label: "Promotions", Content: PromotionsTabLazy },
  { id: "outcomes", label: "Outcomes", Content: OutcomesTabLazy },
  { id: "retros", label: "Retros", Content: RetrosTabLazy },
  { id: "automation-state", label: "Automation", Content: AutomationStateTabLazy },
  { id: "procedural-memory", label: "Procedural memory", Content: ProceduralMemoryTabLazy },
  { id: "audits", label: "Audits", Content: AuditsTabLazy },
  { id: "index", label: "Index", Content: IndexTabLazy },
];

export function SelfImprovementClient({ payload, brainConfigured }: SelfImprovementClientProps) {
  return (
    <SelfImprovementShellContext.Provider value={{ payload, brainConfigured }}>
      <div className="space-y-6">
        <header className="space-y-2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
                Self-improvement
              </h1>
              <p className="text-sm text-zinc-400">
                Brain learning loop — dispatch outcomes, promotions, PR horizons, retros, schedulers,
                and procedural memory. PR P appends an Audits tab.
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

        <TabbedPageShell tabs={SELF_IMPROVEMENT_TABS} defaultTab="learning" />
      </div>
    </SelfImprovementShellContext.Provider>
  );
}
