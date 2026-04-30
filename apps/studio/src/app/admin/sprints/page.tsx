import Link from "next/link";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import { loadStudioWorkstreamsBoard, resolveStudioRequestBaseUrl } from "@/lib/cycles-data";
import { loadTrackerIndex } from "@/lib/tracker";
import { isSprintActiveForUi, isSprintShippedForUi } from "@/lib/tracker-reconcile";

import { CyclesBoardTab } from "./cycles-board-tab";
import { SprintsOverviewTab } from "./sprints-overview-tab";

export const dynamic = "force-dynamic";

export default async function SprintsPage() {
  const base = await resolveStudioRequestBaseUrl();
  const wsLoaded = await loadStudioWorkstreamsBoard(base);

  const { sprints } = loadTrackerIndex();
  const active = sprints.filter((s) => isSprintActiveForUi(s));
  const shipped = sprints.filter((s) => isSprintShippedForUi(s));

  const tabs = [
    {
      id: "sprints" as const,
      label: "Sprint logs",
      content: <SprintsOverviewTab />,
    },
    {
      id: "cycles" as const,
      label: "Cycles",
      content: (
        <CyclesBoardTab
          workstreamsFile={wsLoaded.ok ? wsLoaded.file : null}
          workstreamsError={wsLoaded.ok ? null : wsLoaded.error}
        />
      ),
    },
  ] as const;

  return (
    <div className="space-y-6">
      <HqPageHeader
        title="Sprints"
        actions={
          <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
            cross-cutting work logs
          </span>
        }
      />
      <p className="text-sm text-zinc-400">
        Each sprint links the plan that was used and the PRs that landed. Sourced from{" "}
        <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs">docs/sprints/</code>. Per-product
        roadmaps live under{" "}
        <Link href="/admin/products" className="underline hover:text-zinc-200">
          Products
        </Link>
        ; the company tracker is{" "}
        <Link href="/admin/tasks" className="underline hover:text-zinc-200">
          Tasks
        </Link>
        .{" "}
        {active.length > 0 ? (
          <span className="text-[var(--status-warning)]">
            {active.length} active · {shipped.length} shipped
          </span>
        ) : (
          <span>{shipped.length} shipped</span>
        )}
        <span className="ml-2 text-zinc-500">· click any sprint to expand its full brief</span>
      </p>

      <TabbedPageShell tabs={tabs} defaultTab="sprints" />
    </div>
  );
}
