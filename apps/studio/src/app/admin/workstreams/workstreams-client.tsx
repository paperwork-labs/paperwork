"use client";

import {
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import { Kanban } from "lucide-react";
import { useMemo, useState } from "react";
import { toast, Toaster } from "sonner";

import type {
  WorkstreamOwner,
  WorkstreamsFile,
  WorkstreamKpis,
  WorkstreamStatus,
} from "@/lib/workstreams/schema";

import { moveOrderedIds } from "./move-order";
import { SortableWorkstreamRow } from "./sortable-workstream-row";

export type WorkstreamsBoardClientProps = {
  parsedFile: WorkstreamsFile;
  kpis: WorkstreamKpis;
};

const reorderEnabled =
  process.env.NEXT_PUBLIC_WORKSTREAMS_REORDER_ENABLED === "true";

export function WorkstreamsBoardClient({
  parsedFile,
  kpis,
}: WorkstreamsBoardClientProps) {
  const byId = useMemo(
    () => new Map(parsedFile.workstreams.map((w) => [w.id, w])),
    [parsedFile.workstreams],
  );

  const [orderedIds, setOrderedIds] = useState<string[]>(() =>
    [...parsedFile.workstreams]
      .sort((a, b) => a.priority - b.priority)
      .map((w) => w.id),
  );

  const [statusFilter, setStatusFilter] = useState<
    "all" | WorkstreamStatus
  >("all");
  const [ownerFilter, setOwnerFilter] = useState<"all" | WorkstreamOwner>(
    "all",
  );
  const [trackFilter, setTrackFilter] = useState<string>("all");

  const tracks = useMemo(() => {
    const s = new Set(parsedFile.workstreams.map((w) => w.track));
    return [...s].sort((a, b) => a.localeCompare(b));
  }, [parsedFile.workstreams]);

  const visibleIds = useMemo(() => {
    return orderedIds.filter((id) => {
      const w = byId.get(id);
      if (!w) return false;
      if (statusFilter !== "all" && w.status !== statusFilter) return false;
      if (ownerFilter !== "all" && w.owner !== ownerFilter) return false;
      if (trackFilter !== "all" && w.track !== trackFilter) return false;
      return true;
    });
  }, [byId, orderedIds, statusFilter, ownerFilter, trackFilter]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  async function persistReorder(nextIds: string[]) {
    const res = await fetch("/api/admin/workstreams/reorder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ordered_ids: nextIds }),
    });
    if (!res.ok) {
      let detail = "";
      try {
        detail = JSON.stringify(await res.json());
      } catch {
        detail = await res.text();
      }
      toast.error("Reorder failed", { description: detail });
      return;
    }
    toast.success("Reorder queued");
  }

  async function onDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    const next = moveOrderedIds(
      orderedIds,
      String(active.id),
      over?.id != null ? String(over.id) : undefined,
    );
    if (!next) return;
    setOrderedIds(next);

    if (!reorderEnabled) {
      toast.message("Reorder shipping in a follow-up PR");
      return;
    }

    await persistReorder(next);
  }

  return (
    <>
      <div className="space-y-6">
        <header className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <Kanban className="h-5 w-5 text-violet-300" />
            <h1 className="text-xl font-semibold text-zinc-100">Workstreams</h1>
            <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
              Track Z · read-only
            </span>
          </div>
          <p className="max-w-3xl text-sm text-zinc-400">
            Prioritized Q2 workstreams. Dispatch reads order from JSON;
            reorder persists via Brain PR when enabled.
          </p>
        </header>

        <div className="flex flex-col gap-8 lg:flex-row lg:items-start">
          <div className="min-w-0 flex-1 space-y-6">
            <KpiStrip kpis={kpis} />

            <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 pb-3">
                <p className="text-sm font-medium text-zinc-200">
                  Board ({visibleIds.length} shown)
                </p>
                <span className="text-[11px] text-zinc-500">
                  Drag handles reorder locally
                  {reorderEnabled ? "; saves to Brain when dropped" : ""}.
                </span>
              </div>

              <DndContext
                collisionDetection={closestCenter}
                modifiers={[restrictToVerticalAxis]}
                sensors={sensors}
                onDragEnd={onDragEnd}
              >
                <SortableContext
                  items={visibleIds}
                  strategy={verticalListSortingStrategy}
                >
                  <ul className="space-y-2" role="list">
                    {visibleIds.map((id, index) => {
                      const ws = byId.get(id);
                      if (!ws) return null;
                      return (
                        <SortableWorkstreamRow
                          key={id}
                          rank={index + 1}
                          ws={ws}
                        />
                      );
                    })}
                  </ul>
                </SortableContext>
              </DndContext>

              {visibleIds.length === 0 ? (
                <p className="py-8 text-center text-sm text-zinc-500">
                  No workstreams match the current filters.
                </p>
              ) : null}
            </section>
          </div>

          <FilterRail
            ownerFilter={ownerFilter}
            statusFilter={statusFilter}
            trackFilter={trackFilter}
            tracks={tracks}
            onOwnerChange={setOwnerFilter}
            onStatusChange={setStatusFilter}
            onTrackChange={setTrackFilter}
          />
        </div>
      </div>
      <Toaster richColors theme="dark" position="bottom-right" />
    </>
  );
}

function KpiStrip({ kpis }: { kpis: WorkstreamKpis }) {
  const cards: {
    label: string;
    value: string | number;
    tabular?: boolean;
  }[] = [
    { label: "Total", value: kpis.total },
    { label: "Active", value: kpis.active },
    { label: "Blocked", value: kpis.blocked },
    { label: "Completed", value: kpis.completed },
    { label: "Avg % done", value: `${kpis.avg_percent_done}%`, tabular: true },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
      {cards.map((c) => (
        <div
          key={c.label}
          className="rounded-xl border border-zinc-800 bg-zinc-950/40 px-4 py-3 ring-1 ring-zinc-800/60"
        >
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            {c.label}
          </p>
          <p
            className={`mt-1 text-2xl font-semibold text-zinc-100 ${c.tabular ? "tabular-nums" : ""}`}
          >
            {c.value}
          </p>
        </div>
      ))}
    </div>
  );
}

type FilterRailProps = {
  statusFilter: "all" | WorkstreamStatus;
  ownerFilter: "all" | WorkstreamOwner;
  trackFilter: string;
  tracks: string[];
  onStatusChange: (v: "all" | WorkstreamStatus) => void;
  onOwnerChange: (v: "all" | WorkstreamOwner) => void;
  onTrackChange: (v: string) => void;
};

function FilterRail({
  statusFilter,
  ownerFilter,
  trackFilter,
  tracks,
  onStatusChange,
  onOwnerChange,
  onTrackChange,
}: FilterRailProps) {
  const selectClass =
    "w-full rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-sm text-zinc-100 outline-none ring-1 ring-zinc-800/80 focus:border-zinc-600 focus:ring-zinc-600";

  return (
    <aside className="w-full shrink-0 space-y-4 lg:sticky lg:top-8 lg:w-72">
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 ring-1 ring-zinc-800/60">
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
          Filters
        </p>
        <div className="space-y-3">
          <label className="block space-y-1">
            <span className="text-xs text-zinc-400">Status</span>
            <select
              aria-label="Filter by status"
              className={selectClass}
              value={statusFilter}
              onChange={(e) =>
                onStatusChange(e.target.value as typeof statusFilter)
              }
            >
              <option value="all">All statuses</option>
              <option value="pending">pending</option>
              <option value="in_progress">in_progress</option>
              <option value="blocked">blocked</option>
              <option value="completed">completed</option>
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs text-zinc-400">Owner</span>
            <select
              aria-label="Filter by owner"
              className={selectClass}
              value={ownerFilter}
              onChange={(e) =>
                onOwnerChange(e.target.value as typeof ownerFilter)
              }
            >
              <option value="all">All owners</option>
              <option value="brain">brain</option>
              <option value="founder">founder</option>
              <option value="opus">opus</option>
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs text-zinc-400">Track</span>
            <select
              aria-label="Filter by track"
              className={selectClass}
              value={trackFilter}
              onChange={(e) => onTrackChange(e.target.value)}
            >
              <option value="all">All tracks</option>
              {tracks.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 ring-1 ring-zinc-800/60">
        <button
          type="button"
          disabled
          title="Coming soon — edit workstreams.json in a PR for now"
          className="w-full cursor-not-allowed rounded-lg border border-zinc-700/80 bg-zinc-900/80 px-3 py-2 text-sm font-medium text-zinc-500"
        >
          Add workstream
        </button>
        <p className="mt-2 text-[11px] text-zinc-500">
          Coming soon — edit workstreams.json in a PR for now.
        </p>
      </div>
    </aside>
  );
}
