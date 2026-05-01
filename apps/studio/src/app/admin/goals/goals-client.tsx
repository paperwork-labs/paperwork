"use client";

import {
  AlertTriangle,
  Crosshair,
  ExternalLink,
  ListTree,
  MoreHorizontal,
  Plus,
  Target,
  TrendingUp,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";
import type { GoalsJson, KeyResult, Objective } from "@/lib/goals-metrics";
import {
  computeGoalsRollup,
  krProgressPct,
  objectiveProgressPct,
  progressBarToneClass,
} from "@/lib/goals-metrics";
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  Input,
  Label,
} from "@paperwork-labs/ui";

import {
  archiveGoalAction,
  createGoalAction,
  updateGoalAction,
  updateKRProgressAction,
} from "./actions";

type KeyResultRow = KeyResult & { progress_pct?: number };

function effectiveKrPct(kr: KeyResultRow): number {
  if (typeof kr.progress_pct === "number" && Number.isFinite(kr.progress_pct)) {
    return kr.progress_pct;
  }
  return krProgressPct(kr);
}

function objectivesWithStalledKrs(objectives: Objective[]): Objective[] {
  return objectives.filter((obj) =>
    obj.key_results.some((kr) => effectiveKrPct(kr as KeyResultRow) < 25),
  );
}

function OkrProgressBar({
  label,
  progressPct,
  detail,
}: {
  label: ReactNode;
  progressPct: number;
  detail: string;
}) {
  const width = Math.min(100, Math.max(0, progressPct));
  const tone = progressBarToneClass(progressPct);
  return (
    <div className="space-y-1" data-testid="okr-progress-bar">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="min-w-0 truncate text-zinc-300">{label}</span>
        <span className="shrink-0 tabular-nums text-zinc-500">{detail}</span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-zinc-800/80"
        role="progressbar"
        aria-valuenow={Math.round(width)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${tone}`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function ownerBadgeClass(owner: string): string {
  const o = owner.toLowerCase();
  if (o === "brain") {
    return "border-fuchsia-500/35 bg-fuchsia-500/10 text-fuchsia-200";
  }
  return "border-zinc-600 bg-zinc-800/80 text-zinc-300";
}

const QUARTER_PRESETS = ["2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"] as const;

function quarterSelectOptions(currentQuarter: string): string[] {
  const set = new Set<string>(QUARTER_PRESETS);
  if (currentQuarter) set.add(currentQuarter);
  return Array.from(set).sort();
}

export type KrFormRow = {
  id?: string;
  title: string;
  target: string;
  unit: string;
  current: number;
  source_url: string;
};

function emptyKrRow(): KrFormRow {
  return { title: "", target: "", unit: "", current: 0, source_url: "" };
}

function goalToFormRows(obj: Objective): KrFormRow[] {
  if (obj.key_results.length === 0) return [emptyKrRow()];
  return obj.key_results.map((kr) => ({
    id: kr.id,
    title: kr.title,
    target: String(kr.target),
    unit: kr.unit,
    current: kr.current,
    source_url: kr.source_url ?? "",
  }));
}

/** Shown when Brain has no goals endpoint, returns an error, or Studio env is missing Brain. */
export function GoalsBrainDisconnected({
  brainConfigured,
}: {
  /** True when BRAIN_API_URL / secret are set but goals could not be loaded. */
  brainConfigured: boolean;
}) {
  return (
    <div className="space-y-8">
      <HqPageHeader
        title="Goals & OKRs"
        subtitle="Q2 2026 objectives and key results"
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "Goals & OKRs" },
        ]}
      />

      <div
        role="status"
        data-testid="goals-not-wired"
        className="rounded-2xl border border-zinc-800/90 bg-zinc-950/80 p-8 ring-1 ring-zinc-800"
      >
        <p className="text-sm font-medium text-zinc-200">Not connected to Brain yet</p>
        <p className="mt-3 text-sm leading-relaxed text-zinc-400">
          This page will show live objectives and key results when the Brain API exposes{" "}
          <code className="rounded bg-zinc-900 px-1.5 py-0.5 font-mono text-xs text-zinc-300">
            GET /api/v1/admin/goals
          </code>{" "}
          and Studio can load it successfully.
        </p>
        <p className="mt-3 text-sm text-zinc-500">
          {brainConfigured
            ? "Brain is configured, but goals could not be loaded (missing route, auth, or server error). Check Brain logs and deployment."
            : "Set BRAIN_API_URL and BRAIN_API_SECRET in this environment so Studio can call Brain."}
        </p>
        <p className="mt-4 text-xs text-zinc-600">
          Static demo data is no longer shown here so the dashboard does not look live when it is not.
        </p>
      </div>
    </div>
  );
}

export function GoalsClient({ data }: { data: GoalsJson }) {
  const router = useRouter();
  const activeFromProps = data.objectives;
  const [objectives, setObjectives] = useState<Objective[]>(activeFromProps);

  useEffect(() => {
    setObjectives(activeFromProps);
  }, [activeFromProps]);

  const rollup = useMemo(() => computeGoalsRollup(objectives), [objectives]);
  const stalledObjectives = useMemo(() => objectivesWithStalledKrs(objectives), [objectives]);

  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editGoalId, setEditGoalId] = useState<string | null>(null);
  const [formObjective, setFormObjective] = useState("");
  const [formOwner, setFormOwner] = useState("");
  const [formQuarter, setFormQuarter] = useState(data.quarter || "2026-Q2");
  const [krFormRows, setKrFormRows] = useState<KrFormRow[]>([emptyKrRow()]);
  const [dialogBusy, setDialogBusy] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);

  const quarterOptions = useMemo(() => quarterSelectOptions(data.quarter || ""), [data.quarter]);

  const scrollToGoal = useCallback((goalId: string) => {
    document.getElementById(`goal-${goalId}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const openCreateDialog = useCallback(() => {
    setFormObjective("");
    setFormOwner("");
    setFormQuarter(data.quarter || "2026-Q2");
    setKrFormRows([emptyKrRow()]);
    setDialogError(null);
    setAddOpen(true);
  }, [data.quarter]);

  const openEditDialog = useCallback((obj: Objective) => {
    setEditGoalId(obj.id);
    setFormObjective(obj.title);
    setFormOwner(obj.owner);
    setFormQuarter(data.quarter || "2026-Q2");
    setKrFormRows(goalToFormRows(obj));
    setDialogError(null);
    setEditOpen(true);
  }, [data.quarter]);

  const submitCreate = async () => {
    setDialogBusy(true);
    setDialogError(null);
    const key_results = krFormRows
      .filter((r) => r.title.trim() && r.target.trim())
      .map((r) => ({
        title: r.title.trim(),
        target: Number(r.target),
        current: 0,
        unit: r.unit.trim(),
        source_url: r.source_url.trim() || null,
      }));

    const res = await createGoalAction({
      objective: formObjective.trim(),
      owner: formOwner.trim(),
      quarter: formQuarter.trim(),
      key_results,
    });
    setDialogBusy(false);
    if (!res.ok) {
      setDialogError(res.error);
      return;
    }
    setAddOpen(false);
    router.refresh();
  };

  const submitEdit = async () => {
    if (!editGoalId) return;
    setDialogBusy(true);
    setDialogError(null);
    const key_results = krFormRows
      .filter((r) => r.title.trim() && r.target.trim())
      .map((r) => ({
        id: r.id,
        title: r.title.trim(),
        target: Number(r.target),
        current: r.current,
        unit: r.unit.trim(),
        source_url: r.source_url.trim() || null,
      }));

    const res = await updateGoalAction(editGoalId, {
      objective: formObjective.trim(),
      owner: formOwner.trim(),
      quarter: formQuarter.trim(),
      key_results,
    });
    setDialogBusy(false);
    if (!res.ok) {
      setDialogError(res.error);
      return;
    }
    setEditOpen(false);
    setEditGoalId(null);
    router.refresh();
  };

  const onArchive = async (goalId: string) => {
    if (!globalThis.confirm("Archive this objective? It will be hidden from this view.")) {
      return;
    }
    const res = await archiveGoalAction(goalId);
    if (!res.ok) {
      globalThis.alert(res.error);
      return;
    }
    router.refresh();
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <HqPageHeader
          title="Goals & OKRs"
          subtitle="Q2 2026 objectives and key results"
          breadcrumbs={[
            { label: "Admin", href: "/admin" },
            { label: "Goals & OKRs" },
          ]}
        />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="shrink-0 gap-1.5"
          data-testid="goals-add-button"
          onClick={openCreateDialog}
        >
          <Plus className="h-4 w-4" /> Add goal
        </Button>
      </div>

      {stalledObjectives.length > 0 ? (
        <div
          data-testid="goals-stalled-alert"
          className="rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-100 ring-1 ring-amber-500/20"
        >
          <p className="font-medium text-amber-200">
            {stalledObjectives.length} objective
            {stalledObjectives.length === 1 ? "" : "s"} with key results under 25% progress
          </p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-amber-100/90">
            {stalledObjectives.map((o) => (
              <li key={o.id}>
                <button
                  type="button"
                  className="text-left underline decoration-amber-500/50 underline-offset-2 hover:text-white"
                  onClick={() => scrollToGoal(o.id)}
                >
                  {o.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto border-zinc-800 bg-zinc-950 text-zinc-100 sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Add objective</DialogTitle>
            <DialogDescription className="text-zinc-500">
              Creates a goal in Brain and refreshes this page.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label htmlFor="goal-objective">Objective</Label>
              <Input
                id="goal-objective"
                value={formObjective}
                onChange={(e) => setFormObjective(e.target.value)}
                className="mt-1 border-zinc-700 bg-zinc-900"
                placeholder="What we will achieve"
              />
            </div>
            <div>
              <Label htmlFor="goal-owner">Owner</Label>
              <Input
                id="goal-owner"
                value={formOwner}
                onChange={(e) => setFormOwner(e.target.value)}
                className="mt-1 border-zinc-700 bg-zinc-900"
                placeholder="Team or role"
              />
            </div>
            <div>
              <Label htmlFor="goal-quarter">Quarter</Label>
              <select
                id="goal-quarter"
                value={formQuarter}
                onChange={(e) => setFormQuarter(e.target.value)}
                className="mt-1 w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
              >
                {quarterOptions.map((q) => (
                  <option key={q} value={q}>
                    {q}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Key results</Label>
              {krFormRows.map((row, i) => (
                <div
                  key={i}
                  className="grid gap-2 rounded-lg border border-zinc-800/80 bg-zinc-900/40 p-3 md:grid-cols-3"
                >
                  <Input
                    placeholder="Title"
                    value={row.title}
                    onChange={(e) =>
                      setKrFormRows((rows) =>
                        rows.map((r, j) => (j === i ? { ...r, title: e.target.value } : r)),
                      )
                    }
                    className="border-zinc-700 bg-zinc-900 md:col-span-3"
                  />
                  <Input
                    placeholder="Target"
                    inputMode="decimal"
                    value={row.target}
                    onChange={(e) =>
                      setKrFormRows((rows) =>
                        rows.map((r, j) => (j === i ? { ...r, target: e.target.value } : r)),
                      )
                    }
                    className="border-zinc-700 bg-zinc-900"
                  />
                  <Input
                    placeholder="Unit"
                    value={row.unit}
                    onChange={(e) =>
                      setKrFormRows((rows) =>
                        rows.map((r, j) => (j === i ? { ...r, unit: e.target.value } : r)),
                      )
                    }
                    className="border-zinc-700 bg-zinc-900 md:col-span-2"
                  />
                  {krFormRows.length > 1 ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-zinc-400 md:col-span-3"
                      onClick={() => setKrFormRows((rows) => rows.filter((_, j) => j !== i))}
                    >
                      Remove row
                    </Button>
                  ) : null}
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="border-zinc-700"
                onClick={() => setKrFormRows((rows) => [...rows, emptyKrRow()])}
              >
                Add key result row
              </Button>
            </div>
            {dialogError ? <p className="text-sm text-red-400">{dialogError}</p> : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setAddOpen(false)}>
              Cancel
            </Button>
            <Button type="button" disabled={dialogBusy} onClick={() => void submitCreate()}>
              {dialogBusy ? "Saving…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={(o) => { setEditOpen(o); if (!o) setEditGoalId(null); }}>
        <DialogContent className="max-h-[90vh] overflow-y-auto border-zinc-800 bg-zinc-950 text-zinc-100 sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit objective</DialogTitle>
            <DialogDescription className="text-zinc-500">
              Updates the goal in Brain. Replacing all key results when you save.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label htmlFor="edit-goal-objective">Objective</Label>
              <Input
                id="edit-goal-objective"
                value={formObjective}
                onChange={(e) => setFormObjective(e.target.value)}
                className="mt-1 border-zinc-700 bg-zinc-900"
              />
            </div>
            <div>
              <Label htmlFor="edit-goal-owner">Owner</Label>
              <Input
                id="edit-goal-owner"
                value={formOwner}
                onChange={(e) => setFormOwner(e.target.value)}
                className="mt-1 border-zinc-700 bg-zinc-900"
              />
            </div>
            <div>
              <Label htmlFor="edit-goal-quarter">Quarter</Label>
              <select
                id="edit-goal-quarter"
                value={formQuarter}
                onChange={(e) => setFormQuarter(e.target.value)}
                className="mt-1 w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
              >
                {quarterOptions.map((q) => (
                  <option key={q} value={q}>
                    {q}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Key results</Label>
              {krFormRows.map((row, i) => (
                <div
                  key={i}
                  className="grid gap-2 rounded-lg border border-zinc-800/80 bg-zinc-900/40 p-3 md:grid-cols-2"
                >
                  <Input
                    placeholder="Title"
                    value={row.title}
                    onChange={(e) =>
                      setKrFormRows((rows) =>
                        rows.map((r, j) => (j === i ? { ...r, title: e.target.value } : r)),
                      )
                    }
                    className="border-zinc-700 bg-zinc-900 md:col-span-2"
                  />
                  <Input
                    placeholder="Target"
                    inputMode="decimal"
                    value={row.target}
                    onChange={(e) =>
                      setKrFormRows((rows) =>
                        rows.map((r, j) => (j === i ? { ...r, target: e.target.value } : r)),
                      )
                    }
                    className="border-zinc-700 bg-zinc-900"
                  />
                  <Input
                    placeholder="Unit"
                    value={row.unit}
                    onChange={(e) =>
                      setKrFormRows((rows) =>
                        rows.map((r, j) => (j === i ? { ...r, unit: e.target.value } : r)),
                      )
                    }
                    className="border-zinc-700 bg-zinc-900"
                  />
                  <Input
                    placeholder="Source URL (optional)"
                    value={row.source_url}
                    onChange={(e) =>
                      setKrFormRows((rows) =>
                        rows.map((r, j) => (j === i ? { ...r, source_url: e.target.value } : r)),
                      )
                    }
                    className="border-zinc-700 bg-zinc-900 md:col-span-2"
                  />
                  {krFormRows.length > 1 ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-zinc-400 md:col-span-2"
                      onClick={() => setKrFormRows((rows) => rows.filter((_, j) => j !== i))}
                    >
                      Remove row
                    </Button>
                  ) : null}
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="border-zinc-700"
                onClick={() => setKrFormRows((rows) => [...rows, emptyKrRow()])}
              >
                Add key result row
              </Button>
            </div>
            {dialogError ? <p className="text-sm text-red-400">{dialogError}</p> : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button type="button" disabled={dialogBusy} onClick={() => void submitEdit()}>
              {dialogBusy ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <HqStatCard
          label="Objectives"
          value={rollup.objectiveCount}
          icon={<Crosshair className="h-3.5 w-3.5 text-zinc-500" />}
        />
        <HqStatCard
          label="KRs on track"
          value={rollup.krOnTrack}
          status="success"
          helpText=">50% progress"
          icon={<TrendingUp className="h-3.5 w-3.5 text-zinc-500" />}
        />
        <HqStatCard
          label="KRs at risk"
          value={rollup.krAtRisk}
          status={rollup.krAtRisk > 0 ? "warning" : "neutral"}
          helpText="<25% progress"
          icon={<AlertTriangle className="h-3.5 w-3.5 text-zinc-500" />}
        />
        <HqStatCard
          label="Overall progress"
          value={`${rollup.overallPct}%`}
          icon={<Target className="h-3.5 w-3.5 text-zinc-500" />}
        />
      </div>

      <div className="space-y-5">
        {objectives.map((obj) => (
          <GoalCard
            key={obj.id}
            obj={obj}
            onArchive={() => void onArchive(obj.id)}
            onEdit={() => openEditDialog(obj)}
            onKRsChange={setObjectives}
            refresh={() => router.refresh()}
          />
        ))}
      </div>
    </div>
  );
}

function GoalCard({
  obj,
  onArchive,
  onEdit,
  onKRsChange,
  refresh,
}: {
  obj: Objective;
  onArchive: () => void;
  onEdit: () => void;
  onKRsChange: Dispatch<SetStateAction<Objective[]>>;
  refresh: () => void;
}) {
  const objPct = objectiveProgressPct(obj);

  return (
    <section
      id={`goal-${obj.id}`}
      data-testid="okr-objective-card"
      className="rounded-2xl border border-zinc-800/80 bg-zinc-900/50 p-5 shadow-sm ring-1 ring-black/5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-zinc-100">{obj.title}</h2>
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${ownerBadgeClass(obj.owner)}`}
            >
              {obj.owner}
            </span>
          </div>
          <p className="text-[10px] uppercase tracking-wide text-zinc-500">
            Objective progress (avg. of key results)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="tabular-nums text-sm font-medium text-zinc-400">
            {Math.round(objPct)}%
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-zinc-400"
                aria-label="Goal actions"
                data-testid={`goal-menu-${obj.id}`}
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="border-zinc-800 bg-zinc-950 text-zinc-100"
            >
              <DropdownMenuItem
                className="focus:bg-zinc-900"
                data-testid={`goal-edit-${obj.id}`}
                onSelect={() => onEdit()}
              >
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem
                className="focus:bg-zinc-900 text-amber-200"
                data-testid={`goal-archive-${obj.id}`}
                onSelect={() => onArchive()}
              >
                Archive
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      <div className="mt-3">
        <OkrProgressBar
          label="Objective"
          progressPct={objPct}
          detail={`${obj.key_results.length} key result${obj.key_results.length === 1 ? "" : "s"}`}
        />
      </div>

      <div className="mt-5 space-y-4 border-t border-zinc-800/60 pt-5">
        <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
          <ListTree className="h-3 w-3" /> Key results
        </p>
        <ul className="space-y-4">
          {obj.key_results.map((kr) => (
            <KrRow
                  key={kr.id}
                  objectiveId={obj.id}
                  kr={kr as KeyResultRow}
                  onKRsChange={onKRsChange}
                  refresh={refresh}
                />
          ))}
        </ul>
      </div>
    </section>
  );
}

function KrRow({
  objectiveId,
  kr,
  onKRsChange,
  refresh,
}: {
  objectiveId: string;
  kr: KeyResultRow;
  onKRsChange: Dispatch<SetStateAction<Objective[]>>;
  refresh: () => void;
}) {
  const pct = effectiveKrPct(kr);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(kr.current));
  const [krError, setKrError] = useState<string | null>(null);

  useEffect(() => {
    if (!editing) setDraft(String(kr.current));
  }, [kr.current, editing]);

  const labelNode =
    kr.source_url ? (
      <a
        href={kr.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex max-w-full items-center gap-1 text-zinc-200 underline decoration-zinc-600 underline-offset-2 hover:text-white"
      >
        <span className="truncate">{kr.title}</span>
        <ExternalLink className="h-3 w-3 shrink-0 opacity-70" aria-hidden />
      </a>
    ) : (
      kr.title
    );

  const applyOptimistic = (nextCurrent: number, nextPct?: number) => {
    onKRsChange((prev) =>
      prev.map((o) => {
        if (o.id !== objectiveId) return o;
        return {
          ...o,
          key_results: o.key_results.map((k) =>
            k.id === kr.id
              ? ({
                  ...k,
                  current: nextCurrent,
                  ...(typeof nextPct === "number" ? { progress_pct: nextPct } : {}),
                } as KeyResult)
              : k,
          ),
        };
      }),
    );
  };

  const saveProgress = async () => {
    const v = Number(draft);
    if (!Number.isFinite(v)) {
      setKrError("Enter a valid number");
      return;
    }
    setKrError(null);
    const prevSnapshot = kr.current;
    const prevPct = effectiveKrPct(kr);
    applyOptimistic(v);
    setEditing(false);
    const res = await updateKRProgressAction(objectiveId, kr.id, v);
    if (!res.ok) {
      applyOptimistic(prevSnapshot, prevPct);
      setKrError(res.error);
      setEditing(true);
      setDraft(String(prevSnapshot));
      return;
    }
    refresh();
  };

  return (
    <li>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:gap-3">
        <div className="min-w-0 flex-1">
          <OkrProgressBar
            label={labelNode}
            progressPct={pct}
            detail={`${kr.current} / ${kr.target} ${kr.unit}`}
          />
        </div>
        {editing ? (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Input
              type="number"
              inputMode="decimal"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="h-8 w-24 border-zinc-700 bg-zinc-900 text-xs"
              data-testid={`kr-progress-input-${kr.id}`}
            />
            <Button type="button" size="sm" className="h-8" onClick={() => void saveProgress()}>
              Save
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8"
              onClick={() => {
                setEditing(false);
                setDraft(String(kr.current));
                setKrError(null);
              }}
            >
              Cancel
            </Button>
          </div>
        ) : (
          <button
            type="button"
            className="shrink-0 tabular-nums text-xs font-medium text-zinc-300 underline decoration-zinc-600 underline-offset-2 hover:text-white"
            data-testid={`kr-progress-trigger-${kr.id}`}
            onClick={() => {
              setKrError(null);
              setEditing(true);
            }}
          >
            {Math.round(pct)}%
          </button>
        )}
      </div>
      {krError ? <p className="text-xs text-red-400">{krError}</p> : null}
    </li>
  );
}
