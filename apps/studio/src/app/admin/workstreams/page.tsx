import { Suspense } from "react";
import { Kanban } from "lucide-react";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import { computeWorkstreamsBoardKpis } from "@/lib/tracker-reconcile";
import {
  loadStudioWorkstreamsBoard,
  resolveStudioRequestBaseUrl,
} from "@/lib/cycles-data";

import { PrPipelineContent } from "../pr-pipeline/page";
import { CyclesBoardTab } from "../sprints/cycles-board-tab";
import { SprintsOverviewTab } from "../sprints/sprints-overview-tab";
import { WorkstreamsBoardClient } from "./workstreams-client";

export const dynamic = "force-dynamic";

export default async function AdminWorkstreamsPage() {
  const base = await resolveStudioRequestBaseUrl();
  const loaded = await loadStudioWorkstreamsBoard(base);

  if (!loaded.ok) {
    return (
      <div className="space-y-6">
        <HqPageHeader
          title="Workstreams"
          subtitle="Cross-cutting work logs across the company"
        />
        <div
          role="alert"
          className="rounded-lg border border-rose-900/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-100"
        >
          {loaded.error}
        </div>
      </div>
    );
  }

  const kpis = computeWorkstreamsBoardKpis(loaded.file);
  const tabs = [
    {
      id: "board" as const,
      label: "Board",
      content: (
        <WorkstreamsBoardClient
          kpis={kpis}
          parsedFile={loaded.file}
          showHeader={false}
          staleDataBanner={loaded.staleDataBanner}
          brainFreshnessBanner={loaded.brainFreshnessBanner}
          bundledFallbackBanner={loaded.bundledFallbackBanner}
          legacyBrainShapeBanner={loaded.legacyBrainShapeBanner}
        />
      ),
    },
    {
      id: "sprints" as const,
      label: "Sprints",
      content: <SprintsOverviewTab />,
    },
    {
      id: "cycles" as const,
      label: "Cycles",
      content: (
        <CyclesBoardTab
          workstreamsFile={loaded.file}
          workstreamsError={null}
        />
      ),
    },
    {
      id: "pr-pipeline" as const,
      label: "PR Pipeline",
      content: <PrPipelineContent showHeader={false} />,
    },
  ] as const;

  return (
    <div className="space-y-6">
      <HqPageHeader
        title="Workstreams"
        subtitle="Company work in one place: board, sprint logs, cycles, and PR pipeline."
        actions={
          <>
            <Kanban className="h-5 w-5 text-violet-300" aria-hidden />
            <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
              Track Z · unified
            </span>
          </>
        }
      />
      <Suspense fallback={<div className="animate-pulse text-sm text-zinc-500">Loading workstreams…</div>}>
        <TabbedPageShell tabs={tabs} defaultTab="board" />
      </Suspense>
    </div>
  );
}
