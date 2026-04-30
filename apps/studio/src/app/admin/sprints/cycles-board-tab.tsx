import Link from "next/link";
import type { Workstream, WorkstreamsFile } from "@/lib/workstreams/schema";
import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { loadTrackerIndex } from "@/lib/tracker";
import { buildCyclesFromSprints } from "@/lib/cycles";

function boardColumnForStatus(status: Workstream["status"]): "active" | "backlog" | "done" | null {
  if (status === "in_progress" || status === "blocked") return "active";
  if (status === "pending") return "backlog";
  if (status === "completed") return "done";
  return null;
}

function WorkstreamCycleCard({ ws }: { ws: Workstream }) {
  return (
    <article
      data-testid="workstream-cycle-card"
      className="rounded-lg border border-zinc-800/90 bg-zinc-950/50 px-3 py-2.5 shadow-sm"
    >
      <p className="text-sm font-medium leading-snug text-zinc-100">{ws.title}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-zinc-700 bg-zinc-900/80 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-400">
          {ws.owner}
        </span>
        <span className="rounded-full border border-zinc-700/80 bg-zinc-900/60 px-2 py-0.5 text-[10px] font-medium text-zinc-300">
          Track {ws.track}
        </span>
        <span className="text-[10px] font-medium tabular-nums text-zinc-500">{ws.percent_done}%</span>
      </div>
    </article>
  );
}

type ColumnKey = "active" | "backlog" | "done";

const COLUMN_LABEL: Record<ColumnKey, string> = {
  active: "Active",
  backlog: "Backlog",
  done: "Done",
};

type CyclesBoardTabProps = {
  workstreamsFile: WorkstreamsFile | null;
  workstreamsError: string | null;
};

export function CyclesBoardTab({ workstreamsFile, workstreamsError }: CyclesBoardTabProps) {
  const { sprints } = loadTrackerIndex();
  const cycles = buildCyclesFromSprints(sprints);
  const currentCycle = cycles.find((c) => c.status === "active") ?? cycles[1];

  const byColumn: Record<ColumnKey, Workstream[]> = {
    active: [],
    backlog: [],
    done: [],
  };

  if (workstreamsFile) {
    for (const ws of workstreamsFile.workstreams) {
      const col = boardColumnForStatus(ws.status);
      if (col) byColumn[col].push(ws);
    }
  }

  return (
    <div className="space-y-6">
      {workstreamsError ? (
        <div
          role="alert"
          className="rounded-lg border border-rose-900/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-100"
        >
          {workstreamsError}
        </div>
      ) : null}

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-3">
        <p className="text-[10px] font-medium uppercase tracking-[0.15em] text-zinc-500">
          Current cycle
        </p>
        <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="text-lg font-semibold text-zinc-50">{currentCycle.name}</h2>
          <span className="text-xs text-zinc-500">
            {currentCycle.start_date} → {currentCycle.end_date}
          </span>
          <span className="rounded-full border border-[var(--status-warning)]/40 bg-[var(--status-warning-bg)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--status-warning)]">
            Active window
          </span>
        </div>
        <p className="mt-2 text-xs text-zinc-500">
          Two-week rhythm anchored from{" "}
          <code className="rounded bg-zinc-950 px-1 py-0.5 text-zinc-400">docs/sprints/</code> active
          sprint dates. Previous: <span className="text-zinc-400">{cycles[0]?.name}</span> · Next:{" "}
          <span className="text-zinc-400">{cycles[2]?.name}</span>
          <span className="text-zinc-600"> · </span>
          Workstreams match the{" "}
          <Link href="/admin/workstreams" className="text-[var(--status-info)] hover:opacity-90">
            Workstreams
          </Link>{" "}
          board (same Brain / bundled loader as that page). Read-only board (v1).
        </p>
      </div>

      <div
        className="grid grid-cols-1 gap-4 lg:grid-cols-3"
        data-testid="cycles-board"
        aria-label="Cycles planning board"
      >
        {(Object.keys(byColumn) as ColumnKey[]).map((key) => {
          const items = byColumn[key];
          return (
            <section
              key={key}
              className="flex min-h-[120px] flex-col rounded-xl border border-zinc-800/80 bg-zinc-950/30 p-3"
              data-testid={`cycles-column-${key}`}
              aria-labelledby={`cycles-col-${key}`}
            >
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 id={`cycles-col-${key}`} className="text-sm font-semibold text-zinc-100">
                  {COLUMN_LABEL[key]}
                </h3>
                <span className="rounded-full border border-zinc-700 bg-zinc-900/60 px-2 py-0.5 text-[10px] font-semibold tabular-nums text-zinc-400">
                  {items.length}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-2">
                {items.length === 0 ? (
                  <HqEmptyState
                    title={`No ${COLUMN_LABEL[key].toLowerCase()} workstreams`}
                    description={
                      workstreamsError
                        ? "Fix the load error above to show workstreams here."
                        : "Nothing in this column right now."
                    }
                  />
                ) : (
                  items.map((ws) => <WorkstreamCycleCard key={ws.id} ws={ws} />)
                )}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
