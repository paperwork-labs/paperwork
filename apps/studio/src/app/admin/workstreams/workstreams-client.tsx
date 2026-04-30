"use client";

import type * as React from "react";
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
import { useMemo, useCallback, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { toast, Toaster } from "sonner";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";
import type {
  WorkstreamOwner,
  WorkstreamsFile,
  WorkstreamKpis,
  WorkstreamStatus,
} from "@/lib/workstreams/schema";
import {
  WorkstreamOwnerSchema,
  WorkstreamStatusSchema,
} from "@/lib/workstreams/schema";

import { moveOrderedIds } from "./move-order";
import { SortableWorkstreamRow } from "./sortable-workstream-row";

export type WorkstreamsBoardClientProps = {
  parsedFile: WorkstreamsFile;
  kpis: WorkstreamKpis;
  /** Shown when live Brain fetch failed or returned invalid data (build snapshot in use). */
  staleDataBanner?: string | null;
  /** When Brain returned a freshness envelope — relative time since ``generated_at``. */
  brainFreshnessBanner?: string | null;
  /** Brain proxy error / timeout — Studio is using bundled ``workstreams.json``. */
  bundledFallbackBanner?: string | null;
  /** Brain returned file shape without provenance envelope. */
  legacyBrainShapeBanner?: string | null;
};

const reorderEnabled =
  process.env.NEXT_PUBLIC_WORKSTREAMS_REORDER_ENABLED === "true";

const STATUS_OPTIONS: ("all" | WorkstreamStatus)[] = [
  "all",
  "pending",
  "in_progress",
  "blocked",
  "completed",
  "cancelled",
];

const OWNER_OPTIONS: ("all" | WorkstreamOwner)[] = [
  "all",
  "brain",
  "founder",
  "opus",
];

function chipClass(active: boolean) {
  return active
    ? "border-violet-500/60 bg-violet-500/15 text-violet-100"
    : "border-zinc-700/80 bg-zinc-950/50 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200";
}

export function WorkstreamsBoardClient({
  parsedFile,
  kpis,
  staleDataBanner = null,
  brainFreshnessBanner = null,
  bundledFallbackBanner = null,
  legacyBrainShapeBanner = null,
}: WorkstreamsBoardClientProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const byId = useMemo(
    () => new Map(parsedFile.workstreams.map((w) => [w.id, w])),
    [parsedFile.workstreams],
  );

  const [orderedIds, setOrderedIds] = useState<string[]>(() =>
    [...parsedFile.workstreams]
      .sort((a, b) => {
        const aDone = a.status === "completed" ? 1 : 0;
        const bDone = b.status === "completed" ? 1 : 0;
        if (aDone !== bDone) return aDone - bDone;
        if (aDone === 1) {
          const aT = new Date(a.last_activity).getTime();
          const bT = new Date(b.last_activity).getTime();
          return bT - aT;
        }
        return a.priority - b.priority;
      })
      .map((w) => w.id),
  );

  const tracks = useMemo(() => {
    const s = new Set(parsedFile.workstreams.map((w) => w.track));
    return [...s].sort((a, b) => a.localeCompare(b));
  }, [parsedFile.workstreams]);

  const rawStatus = searchParams.get("status") ?? "";
  const statusFilter: "all" | WorkstreamStatus =
    rawStatus === "" || rawStatus === "all"
      ? "all"
      : WorkstreamStatusSchema.safeParse(rawStatus).success
        ? (rawStatus as WorkstreamStatus)
        : "all";

  const rawOwner = searchParams.get("owner") ?? "";
  const ownerFilter: "all" | WorkstreamOwner =
    rawOwner === "" || rawOwner === "all"
      ? "all"
      : WorkstreamOwnerSchema.safeParse(rawOwner).success
        ? (rawOwner as WorkstreamOwner)
        : "all";

  const rawTrack = searchParams.get("track") ?? "";
  const trackFilter =
    rawTrack === "" || rawTrack === "all"
      ? "all"
      : tracks.includes(rawTrack)
        ? rawTrack
        : "all";

  const setQuery = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === "" || value === "all") {
          next.delete(key);
        } else {
          next.set(key, value);
        }
      }
      const q = next.toString();
      router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  const pickStatus = useCallback(
    (opt: (typeof STATUS_OPTIONS)[number]) => {
      if (opt === "all") {
        setQuery({ status: null });
        return;
      }
      if (statusFilter === opt) setQuery({ status: null });
      else setQuery({ status: opt });
    },
    [setQuery, statusFilter],
  );

  const pickOwner = useCallback(
    (opt: (typeof OWNER_OPTIONS)[number]) => {
      if (opt === "all") {
        setQuery({ owner: null });
        return;
      }
      if (ownerFilter === opt) setQuery({ owner: null });
      else setQuery({ owner: opt });
    },
    [ownerFilter, setQuery],
  );

  const pickTrack = useCallback(
    (t: "all" | string) => {
      if (t === "all") {
        setQuery({ track: null });
        return;
      }
      if (trackFilter === t) setQuery({ track: null });
      else setQuery({ track: t });
    },
    [setQuery, trackFilter],
  );

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
        <HqPageHeader
          title="Workstreams"
          subtitle="Cross-cutting work logs across the company"
          actions={
            <>
              <Kanban className="h-5 w-5 text-violet-300" aria-hidden />
              <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
                Track Z · read-only
              </span>
            </>
          }
        />

        {bundledFallbackBanner ? (
          <div
            data-testid="workstreams-bundled-fallback-banner"
            aria-live="polite"
            className="rounded-lg border border-[var(--status-warning)]/40 bg-[var(--status-warning-bg)] px-3 py-2 text-sm text-[color-mix(in_srgb,var(--status-warning)_90%,white)]"
          >
            {bundledFallbackBanner}
          </div>
        ) : null}

        {brainFreshnessBanner ? (
          <div
            data-testid="workstreams-brain-freshness-banner"
            aria-live="polite"
            className="rounded-lg border border-[var(--status-success)]/35 bg-[var(--status-success-bg)] px-3 py-2 text-sm text-[color-mix(in_srgb,var(--status-success)_88%,white)]"
          >
            {brainFreshnessBanner}
          </div>
        ) : null}

        {legacyBrainShapeBanner ? (
          <div
            data-testid="workstreams-legacy-brain-banner"
            aria-live="polite"
            className="rounded-lg border border-[var(--status-warning)]/40 bg-[var(--status-warning-bg)] px-3 py-2 text-sm text-[color-mix(in_srgb,var(--status-warning)_88%,white)]"
          >
            {legacyBrainShapeBanner}
          </div>
        ) : null}

        {staleDataBanner ? (
          <div
            data-testid="workstreams-stale-banner"
            aria-live="polite"
            className="rounded-lg border border-[var(--status-warning)]/40 bg-[var(--status-warning-bg)] px-3 py-2 text-sm text-[color-mix(in_srgb,var(--status-warning)_88%,white)]"
          >
            {staleDataBanner}
          </div>
        ) : null}

        <div className="space-y-3 rounded-xl border border-zinc-800/80 bg-zinc-950/30 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
            Filters · URL shareable
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="mr-1 self-center text-[11px] text-zinc-500">Status</span>
            {STATUS_OPTIONS.map((opt) => {
              const active =
                opt === "all" ? statusFilter === "all" : statusFilter === opt;
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => pickStatus(opt)}
                  className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${chipClass(active)}`}
                >
                  {opt === "all" ? "All" : opt}
                </button>
              );
            })}
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="mr-1 self-center text-[11px] text-zinc-500">Owner</span>
            {OWNER_OPTIONS.map((opt) => {
              const active =
                opt === "all" ? ownerFilter === "all" : ownerFilter === opt;
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => pickOwner(opt)}
                  className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${chipClass(active)}`}
                >
                  {opt === "all" ? "All" : opt}
                </button>
              );
            })}
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="mr-1 self-center text-[11px] text-zinc-500">Track</span>
            <button
              type="button"
              onClick={() => pickTrack("all")}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${chipClass(trackFilter === "all")}`}
            >
              All
            </button>
            {tracks.map((t) => {
              const active = trackFilter === t;
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => pickTrack(t)}
                  className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${chipClass(active)}`}
                >
                  {t}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <HqStatCard variant="compact" label="Total" value={kpis.total} />
          <HqStatCard variant="compact" label="Active workstreams" value={kpis.active} />
          <HqStatCard variant="compact" label="Blocked" value={kpis.blocked} status="danger" />
          <HqStatCard variant="compact" label="Cancelled" value={kpis.cancelled} />
          <HqStatCard variant="compact" label="Completed" value={kpis.completed} status="success" />
          <HqStatCard
            variant="compact"
            label="Avg % done"
            value={`${kpis.avg_percent_done}%`}
            status="info"
          />
        </div>

        <section
          data-testid="workstreams-board"
          className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4"
        >
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
                {(() => {
                  let completedSeen = false;
                  let activeRank = 0;
                  let completedRank = 0;
                  const activeTotal = visibleIds.filter(
                    (id) => byId.get(id)?.status !== "completed",
                  ).length;
                  const completedTotal = visibleIds.length - activeTotal;
                  const rendered: React.ReactNode[] = [];
                  for (const id of visibleIds) {
                    const ws = byId.get(id);
                    if (!ws) continue;
                    const isDone = ws.status === "completed";
                    if (isDone && !completedSeen) {
                      completedSeen = true;
                      rendered.push(
                        <li
                          key="__completed_divider"
                          aria-hidden="true"
                          className="!mt-6 list-none border-t border-zinc-800/70 pt-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-500"
                        >
                          Completed · {completedTotal} shipped
                        </li>,
                      );
                    }
                    if (isDone) completedRank += 1;
                    else activeRank += 1;
                    rendered.push(
                      <SortableWorkstreamRow
                        key={id}
                        rank={isDone ? completedRank : activeRank}
                        ws={ws}
                      />,
                    );
                  }
                  if (!completedSeen && activeTotal === 0) {
                    return null;
                  }
                  void completedTotal;
                  return rendered;
                })()}
              </ul>
            </SortableContext>
          </DndContext>

          {visibleIds.length === 0 ? (
            <p className="py-8 text-center text-sm text-zinc-500">
              No workstreams match the current filters.
            </p>
          ) : null}

          <div className="mt-6 border-t border-zinc-800/80 pt-4">
            <button
              type="button"
              disabled
              title="Coming soon — edit workstreams.json in a PR for now"
              className="w-full cursor-not-allowed rounded-lg border border-zinc-700/80 bg-zinc-900/80 px-3 py-2 text-sm font-medium text-zinc-500"
            >
              Add workstream
            </button>
            <p className="mt-2 text-center text-[11px] text-zinc-500">
              Coming soon — edit workstreams.json in a PR for now.
            </p>
          </div>
        </section>
      </div>
      <Toaster richColors theme="dark" position="bottom-right" />
    </>
  );
}
