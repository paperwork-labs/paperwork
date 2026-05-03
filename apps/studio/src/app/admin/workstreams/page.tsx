import { Suspense } from "react";
import { ListTree } from "lucide-react";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import { BrainClient, BrainClientError } from "@/lib/brain-client";

import { PrPipelineContent } from "../pr-pipeline/page";
import { EpicsTreeView } from "./epics-tree-view";

export const dynamic = "force-dynamic";

function brainHierarchyErrorMessage(err: unknown): string {
  if (err instanceof BrainClientError) {
    return err.message;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return "Failed to load epic hierarchy from Brain.";
}

export default async function AdminWorkstreamsPage() {
  const client = BrainClient.fromEnv();
  let hierarchyError: string | null = null;
  let goals = null as Awaited<ReturnType<BrainClient["getEpicHierarchy"]>> | null;

  if (!client) {
    hierarchyError =
      "Brain admin API not configured (BRAIN_API_URL / BRAIN_API_SECRET).";
  } else {
    try {
      goals = await client.getEpicHierarchy();
    } catch (e) {
      hierarchyError = brainHierarchyErrorMessage(e);
    }
  }

  const treePanel =
    hierarchyError != null ? (
      <div
        role="alert"
        className="rounded-lg border border-rose-900/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-100"
        data-testid="epics-brain-error"
      >
        {hierarchyError}
      </div>
    ) : (
      <EpicsTreeView goals={goals ?? []} />
    );

  const tabs = [
    {
      id: "tree" as const,
      label: "Tree",
      content: treePanel,
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
        title="Epics"
        subtitle="Goals → Epics → Sprints → Tasks — your project hierarchy"
        actions={
          <>
            <ListTree className="h-5 w-5 text-violet-300" aria-hidden />
            <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
              Brain
            </span>
          </>
        }
      />
      <Suspense
        fallback={
          <div className="animate-pulse text-sm text-zinc-500">Loading…</div>
        }
      >
        <TabbedPageShell tabs={tabs} defaultTab="tree" />
      </Suspense>
    </div>
  );
}
