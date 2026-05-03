"use client";

import { useCallback, useEffect, useMemo, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Circle,
  ExternalLink,
  Pencil,
  Plus,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Toaster } from "sonner";
import {
  Badge,
  Progress,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  cn,
} from "@paperwork-labs/ui";

import type { EpicItem, GoalItem, SprintItem, TaskItem } from "@/lib/brain-client";

import { EpicHierarchyCrudModal } from "./epic-crud-modal";
import type { EpicCrudDraft, HierarchyEntityKind } from "./epic-crud-modal";
import { epicHierarchyMutateJson } from "./epic-hierarchy-api";
import { StatusBadge } from "@/components/admin/hq/StatusBadge";
import { StatusDot } from "@/components/admin/hq/StatusDot";
import { STATUS_CLASSES, type StatusLevel } from "@/styles/design-tokens";

const GOAL_STATUS_OPTIONS = ["active", "paused", "completed"] as const;

const EPIC_STATUS_OPTIONS = ["backlog", "in_progress", "blocked", "paused", "done"] as const;

const SPRINT_STATUS_OPTIONS = ["planned", "active", "shipped", "paused"] as const;

const TASK_STATUS_OPTIONS = ["open", "todo", "in_progress", "merged", "done"] as const;

const NEUTRAL_BADGE_BUCKET = new Set([
  "backlog",
  "pending",
  "planned",
  "todo",
  "open",
]);

/** Default monorepo PR base when Brain stores only ``github_pr`` (no URL). */
const STUDIO_DEFAULT_PR_PULL = "https://github.com/paperwork-labs/paperwork/pull";

const WAVE_TITLE_RE = /^wave\s*\d+\s*:/i;

function formatSprintDisplayTitle(sprint: SprintItem): string {
  const raw = (sprint.title ?? "").trim();
  if (WAVE_TITLE_RE.test(raw)) return raw;
  const waveNum = (sprint.ordinal ?? 0) + 1;
  return raw ? `Wave ${waveNum}: ${raw}` : `Wave ${waveNum}`;
}

function taskGithubPrHref(task: TaskItem): string | null {
  const url = task.github_pr_url?.trim();
  if (url) return url;
  const n = task.github_pr;
  if (typeof n === "number" && Number.isFinite(n) && n > 0) {
    return `${STUDIO_DEFAULT_PR_PULL}/${n}`;
  }
  return null;
}

type DraftSetter = Dispatch<SetStateAction<EpicCrudDraft | null>>;

function normStatus(s: string) {
  return s.trim().toLowerCase().replace(/\s+/g, "_");
}

function hierarchyStatusLevel(status: string): StatusLevel {
  const n = normStatus(status);
  if (n === "blocked") return "danger";
  if (
    n === "in_progress" ||
    n === "active" ||
    n === "in-progress" ||
    n === "started"
  ) {
    return "warning";
  }
  if (n === "backlog" || n === "pending" || n === "planned" || n === "todo" || n === "open") {
    return "neutral";
  }
  if (
    n === "done" ||
    n === "shipped" ||
    n === "merged" ||
    n === "complete" ||
    n === "closed"
  ) {
    return "success";
  }
  return "neutral";
}

function taskIsDone(status: string): boolean {
  const n = normStatus(status);
  return (
    n === "merged" ||
    n === "done" ||
    n === "shipped" ||
    n === "complete" ||
    n === "closed"
  );
}

type SortMode = "priority" | "activity" | "percent" | "alpha";

type StatusFilterKey = "active" | "completed" | "blocked" | "draft";

const STATUS_FILTER_KEYS: readonly StatusFilterKey[] = [
  "active",
  "completed",
  "blocked",
  "draft",
] as const;

const STATUS_FILTER_LABEL: Record<StatusFilterKey, string> = {
  active: "Active",
  completed: "Completed",
  blocked: "Blocked",
  draft: "Draft",
};

function fuzzyMatch(query: string, haystack: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const h = haystack.trim().toLowerCase();
  if (!h) return false;
  if (h.includes(q)) return true;
  let qi = 0;
  for (let i = 0; i < h.length && qi < q.length; i++) {
    if (h[i] === q[qi]) qi++;
  }
  return qi === q.length;
}

function filterEpicBySearch(epic: EpicItem, goal: GoalItem, query: string): EpicItem | null {
  const trimmed = query.trim();
  if (!trimmed) return epic;
  if (fuzzyMatch(trimmed, goal.objective) || fuzzyMatch(trimmed, epic.title)) {
    return epic;
  }
  const nextSprints: SprintItem[] = [];
  for (const sp of epic.sprints ?? []) {
    if (fuzzyMatch(trimmed, sp.title)) {
      nextSprints.push(sp);
      continue;
    }
    const tasks = (sp.tasks ?? []).filter((t) => fuzzyMatch(trimmed, t.title));
    if (tasks.length) {
      nextSprints.push({ ...sp, tasks });
    }
  }
  if (!nextSprints.length) return null;
  return { ...epic, sprints: nextSprints };
}

function epicStatusFilterKey(status: string): StatusFilterKey {
  const n = normStatus(status);
  if (n === "blocked") return "blocked";
  if (n === "done" || n === "complete" || n === "closed") return "completed";
  if (n === "backlog") return "draft";
  return "active";
}

function epicActivityMs(epic: EpicItem): number {
  const raw = epic.last_activity;
  if (typeof raw === "string" && raw.length > 0) {
    const t = Date.parse(raw);
    if (!Number.isNaN(t)) return t;
  }
  return 0;
}

function sortEpicList(epics: EpicItem[], mode: SortMode): EpicItem[] {
  const out = [...epics];
  out.sort((a, b) => {
    if (mode === "priority") {
      const d = a.priority - b.priority;
      if (d !== 0) return d;
      return a.title.localeCompare(b.title);
    }
    if (mode === "activity") {
      const d = epicActivityMs(b) - epicActivityMs(a);
      if (d !== 0) return d;
      return a.title.localeCompare(b.title);
    }
    if (mode === "percent") {
      const d = (b.percent_done ?? 0) - (a.percent_done ?? 0);
      if (d !== 0) return d;
      return a.title.localeCompare(b.title);
    }
    return a.title.localeCompare(b.title);
  });
  return out;
}

function buildOpenMap(goals: GoalItem[], expandEpicAndSprint: boolean): Record<string, boolean> {
  const o: Record<string, boolean> = {};
  for (const g of goals) {
    o[`g:${g.id}`] = true;
    for (const e of g.epics ?? []) {
      o[`e:${e.id}`] = expandEpicAndSprint;
      for (const s of e.sprints ?? []) {
        o[`s:${s.id}`] = expandEpicAndSprint;
      }
    }
  }
  return o;
}

function collectOwners(goals: GoalItem[]): string[] {
  const slugs = new Set<string>();
  for (const g of goals) {
    for (const e of g.epics ?? []) {
      const slug = (e.owner_employee_slug ?? "").trim();
      if (slug) slugs.add(slug);
    }
  }
  return [...slugs].sort((a, b) => a.localeCompare(b));
}

function quickStatusChoices(entity: HierarchyEntityKind): readonly string[] {
  if (entity === "goal") return GOAL_STATUS_OPTIONS;
  if (entity === "epic") return EPIC_STATUS_OPTIONS;
  if (entity === "sprint") return SPRINT_STATUS_OPTIONS;
  return TASK_STATUS_OPTIONS;
}

function ghostIconButtonCls() {
  return "flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-zinc-600 hover:bg-zinc-900/80 hover:text-zinc-200";
}

async function proxyPatchStatus(entity: HierarchyEntityKind, id: string, status: string) {
  let pathSegments: string[];
  if (entity === "goal") pathSegments = ["goals", id];
  else if (entity === "epic") pathSegments = ["epics", id];
  else if (entity === "sprint") pathSegments = ["sprints", id];
  else pathSegments = ["tasks", id];
  return epicHierarchyMutateJson(pathSegments, "PATCH", { status });
}

function StatusBadgeInteractive({
  entity,
  entityId,
  status,
}: {
  entity: HierarchyEntityKind;
  entityId: string;
  status: string;
}) {
  const router = useRouter();
  const level = hierarchyStatusLevel(status);

  const onPick = async (next: string) => {
    if (next === status) return;
    const res = await proxyPatchStatus(entity, entityId, next);
    if (!res.ok) {
      toast.error(res.errorMessage ?? "Status update failed.");
      return;
    }
    toast.success("Status updated.");
    router.refresh();
  };

  const choices = quickStatusChoices(entity);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          title="Change status"
          onPointerDown={(e) => e.stopPropagation()}
          className="inline-flex shrink-0 outline-none transition hover:opacity-90 focus-visible:ring-2 focus-visible:ring-[var(--status-info)]"
        >
          <StatusBadge
            status={level}
            size="sm"
            className={cn(
              level === "neutral" &&
                !NEUTRAL_BADGE_BUCKET.has(normStatus(status)) &&
                "bg-zinc-800/60 text-zinc-400",
            )}
          >
            {status.replace(/_/g, " ")}
          </StatusBadge>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="border-zinc-800 bg-zinc-950 text-zinc-100 shadow-xl"
      >
        {choices.map((c) => (
          <DropdownMenuItem
            key={c}
            className={cn(
              "cursor-pointer capitalize focus:bg-zinc-900 focus:text-zinc-100",
              normStatus(c) === normStatus(status) && "text-[var(--status-info)]",
            )}
            onSelect={() => void onPick(c)}
          >
            {c.replace(/_/g, " ")}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ToggleRow({
  open,
  onToggle,
  depthClass,
  children,
}: {
  open: boolean;
  onToggle: () => void;
  depthClass: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex items-start gap-1 py-1.5", depthClass)}>
      <button
        type="button"
        onClick={onToggle}
        className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
        aria-expanded={open}
      >
        {open ? (
          <ChevronDown className="h-4 w-4" aria-hidden />
        ) : (
          <ChevronRight className="h-4 w-4" aria-hidden />
        )}
      </button>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

function HorizonBadge({ horizon }: { horizon: string }) {
  return (
    <Badge variant="outline" className="ml-2 shrink-0 border-zinc-600 text-[10px] text-zinc-300">
      {horizon}
    </Badge>
  );
}

function GoalBlock({
  goal,
  open,
  onToggle,
  renderEpics,
  setDraft,
}: {
  goal: GoalItem;
  open: boolean;
  onToggle: () => void;
  renderEpics: () => ReactNode;
  setDraft: DraftSetter;
}) {
  return (
    <div className="border-b border-zinc-800/80 pb-2 last:border-b-0">
      <ToggleRow open={open} onToggle={onToggle} depthClass="pl-0">
        <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
          <div className="flex min-w-[12rem] flex-1 flex-wrap items-center gap-2">
            <span className="text-base leading-none" aria-hidden>
              🎯
            </span>
            <span className="font-medium text-zinc-100">{goal.objective}</span>
            <HorizonBadge horizon={goal.horizon} />
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <StatusBadgeInteractive
              entity="goal"
              entityId={goal.id}
              status={goal.status}
            />
            <button
              type="button"
              title="Edit goal"
              onPointerDown={(e) => e.stopPropagation()}
              className={ghostIconButtonCls()}
              onClick={() =>
                setDraft({
                  mode: "edit",
                  entity: "goal",
                  defaults: {
                    id: goal.id,
                    objective: goal.objective,
                    horizon: goal.horizon,
                    status: goal.status,
                  },
                })
              }
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden />
            </button>
            <button
              type="button"
              title="Add epic under this goal"
              onPointerDown={(e) => e.stopPropagation()}
              className={ghostIconButtonCls()}
              onClick={() =>
                setDraft({
                  mode: "create",
                  entity: "epic",
                  parentGoalId: goal.id,
                })
              }
            >
              <Plus className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
        </div>
      </ToggleRow>
      {open ? (
        <div className="ml-1 space-y-0.5 border-l border-zinc-800/70 pl-3">{renderEpics()}</div>
      ) : null}
    </div>
  );
}

function EpicBlock({
  epic,
  open,
  onToggle,
  renderSprints,
  setDraft,
}: {
  epic: EpicItem;
  open: boolean;
  onToggle: () => void;
  renderSprints: () => ReactNode;
  setDraft: DraftSetter;
}) {
  const pct = Math.min(100, Math.max(0, epic.percent_done ?? 0));
  const epicLevel = hierarchyStatusLevel(epic.status);
  return (
    <div>
      <ToggleRow open={open} onToggle={onToggle} depthClass="pl-4">
        <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
          <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
              <span className="text-base leading-none" aria-hidden>
                📋
              </span>
              <span title={epic.status} aria-hidden>
                <StatusDot
                  status={epicLevel}
                  size="md"
                  className={cn(
                    "ring-2 ring-offset-0 ring-offset-zinc-950",
                    STATUS_CLASSES[epicLevel].ring,
                  )}
                />
              </span>
              <span className="font-mono text-xs text-violet-300">{epic.id}</span>
              <span className="text-sm text-zinc-200">{epic.title}</span>
              <span className="text-xs tabular-nums text-zinc-500">[{pct}%]</span>
            </div>
            <div className="flex max-w-xs min-w-[6rem] flex-1 items-center gap-2 sm:max-w-[12rem]">
              <Progress value={pct} className="h-1.5 flex-1 bg-zinc-800" />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {epic.owner_employee_slug ? (
                <span className="text-[10px] uppercase tracking-wide text-zinc-500">
                  @{epic.owner_employee_slug}
                </span>
              ) : null}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-1">
            <StatusBadgeInteractive
              entity="epic"
              entityId={epic.id}
              status={epic.status}
            />
            <button
              type="button"
              title="Edit epic"
              onPointerDown={(e) => e.stopPropagation()}
              className={ghostIconButtonCls()}
              onClick={() =>
                setDraft({
                  mode: "edit",
                  entity: "epic",
                  defaults: {
                    id: epic.id,
                    title: epic.title,
                    priority: epic.priority,
                    status: epic.status,
                    owner_employee_slug: epic.owner_employee_slug ?? "",
                    brief_tag: epic.brief_tag ?? "",
                  },
                })
              }
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden />
            </button>
            <button
              type="button"
              title="Add sprint under this epic"
              onPointerDown={(e) => e.stopPropagation()}
              className={ghostIconButtonCls()}
              onClick={() =>
                setDraft({
                  mode: "create",
                  entity: "sprint",
                  parentEpicId: epic.id,
                })
              }
            >
              <Plus className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
        </div>
      </ToggleRow>
      {open ? <div className="border-l border-zinc-800/50 pl-2">{renderSprints()}</div> : null}
    </div>
  );
}

function SprintBlock({
  sprint,
  epicId,
  open,
  onToggle,
  renderTasks,
  setDraft,
}: {
  sprint: SprintItem;
  epicId: string;
  open: boolean;
  onToggle: () => void;
  renderTasks: () => ReactNode;
  setDraft: DraftSetter;
}) {
  const tasks = sprint.tasks ?? [];
  const count = tasks.length;
  const nextOrdinal =
    sprint.ordinal != null ? sprint.ordinal + 1 : tasks.length > 0 ? tasks.length : 0;

  return (
    <div>
      <ToggleRow open={open} onToggle={onToggle} depthClass="pl-8">
        <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2 text-sm">
            <span className="text-base leading-none" aria-hidden>
              🏃
            </span>
            <span className="text-zinc-200">{formatSprintDisplayTitle(sprint)}</span>
            <span className="text-xs text-zinc-500">
              ({count} task{count === 1 ? "" : "s"})
            </span>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-1">
            <StatusBadgeInteractive
              entity="sprint"
              entityId={sprint.id}
              status={sprint.status}
            />
            <button
              type="button"
              title="Edit sprint"
              onPointerDown={(e) => e.stopPropagation()}
              className={ghostIconButtonCls()}
              onClick={() =>
                setDraft({
                  mode: "edit",
                  entity: "sprint",
                  defaults: {
                    id: sprint.id,
                    title: sprint.title,
                    ordinal: sprint.ordinal,
                    status: sprint.status,
                  },
                })
              }
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden />
            </button>
            <button
              type="button"
              title="Add task under this sprint"
              onPointerDown={(e) => e.stopPropagation()}
              className={ghostIconButtonCls()}
              onClick={() =>
                setDraft({
                  mode: "create",
                  entity: "task",
                  parentSprintId: sprint.id,
                  epicIdForTasks: epicId,
                  defaults: { ordinal: nextOrdinal },
                })
              }
            >
              <Plus className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
        </div>
      </ToggleRow>
      {open ? (
        <div className="ml-2 border-l border-zinc-800/50 pl-2">{renderTasks()}</div>
      ) : null}
    </div>
  );
}

function TaskRow({
  task,
  epicId,
  sprintId,
  setDraft,
}: {
  task: TaskItem;
  epicId: string;
  sprintId: string;
  setDraft: DraftSetter;
}) {
  const done = taskIsDone(task.status);
  const prHref = taskGithubPrHref(task);
  return (
    <div className="flex items-start gap-2 py-1.5 pl-[2.75rem] pr-2 text-sm sm:pl-14">
      {done ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--status-success)]" aria-hidden />
      ) : (
        <Circle className="mt-0.5 h-4 w-4 shrink-0 text-zinc-600" aria-hidden />
      )}
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className={cn("text-zinc-200", done && "text-zinc-400 line-through")}>
            {task.title}
          </span>
          <div className="flex shrink-0 items-center gap-1">
            <StatusBadgeInteractive
              entity="task"
              entityId={task.id}
              status={task.status}
            />
            <button
              type="button"
              title="Edit task"
              className={ghostIconButtonCls()}
              onClick={() =>
                setDraft({
                  mode: "edit",
                  entity: "task",
                  parentEpicId: epicId,
                  parentSprintId: sprintId,
                  epicIdForTasks: epicId,
                  defaults: {
                    id: task.id,
                    title: task.title,
                    status: task.status,
                    github_pr: task.github_pr ?? undefined,
                    github_pr_url: task.github_pr_url ?? undefined,
                    owner_employee_slug: task.owner_employee_slug ?? "",
                  },
                })
              }
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-zinc-500">
          {prHref ? (
            <a
              href={prHref}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-0.5 font-mono text-sky-400 hover:underline"
            >
              #{task.github_pr ?? "PR"}
              <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          ) : null}
          {task.owner_employee_slug ? (
            <span className="text-[10px] uppercase tracking-wide text-zinc-500">
              @{task.owner_employee_slug}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export type EpicsTreeViewProps = {
  goals: GoalItem[];
};

export function EpicsTreeView({ goals }: EpicsTreeViewProps) {
  const [draft, setDraft] = useState<EpicCrudDraft | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("priority");
  const [ownerFilter, setOwnerFilter] = useState("");
  const [statusFilters, setStatusFilters] = useState<Set<StatusFilterKey>>(() => new Set());

  const statusFilterDep = [...statusFilters].sort().join(",");

  const ownerOptions = useMemo(() => collectOwners(goals), [goals]);

  const filteredGoals = useMemo(() => {
    const result: GoalItem[] = [];
    for (const g of goals) {
      let epics = (g.epics ?? []).filter((e) => {
        if (ownerFilter && (e.owner_employee_slug ?? "").trim() !== ownerFilter) return false;
        if (statusFilters.size && !statusFilters.has(epicStatusFilterKey(e.status))) {
          return false;
        }
        return true;
      });
      epics = epics
        .map((e) => filterEpicBySearch(e, g, searchQuery))
        .filter((e): e is EpicItem => e != null);
      epics = sortEpicList(epics, sortMode);
      if (epics.length) {
        result.push({ ...g, epics });
      }
    }
    if (sortMode === "alpha") {
      result.sort((a, b) => a.objective.localeCompare(b.objective));
    }
    return result;
  }, [goals, searchQuery, sortMode, ownerFilter, statusFilterDep]);

  const totalEpicCount = useMemo(
    () => goals.reduce((n, g) => n + (g.epics?.length ?? 0), 0),
    [goals],
  );
  const filteredEpicCount = useMemo(
    () => filteredGoals.reduce((n, g) => n + (g.epics?.length ?? 0), 0),
    [filteredGoals],
  );

  const searchOrConstraintActive =
    searchQuery.trim().length > 0 || statusFilters.size > 0 || ownerFilter.length > 0;

  const initialOpen = useMemo(() => {
    const o: Record<string, boolean> = {};
    for (const g of goals) {
      o[`g:${g.id}`] = true;
      for (const e of g.epics ?? []) {
        o[`e:${e.id}`] = true;
        for (const s of e.sprints ?? []) {
          o[`s:${s.id}`] = true;
        }
      }
    }
    return o;
  }, [goals]);

  const [open, setOpen] = useState(initialOpen);

  useEffect(() => {
    setOpen((prev) => {
      const next: Record<string, boolean> = { ...initialOpen };
      for (const key of Object.keys(next)) {
        if (key in prev) next[key] = prev[key]!;
      }
      return next;
    });
  }, [initialOpen]);

  const toggle = useCallback((key: string) => {
    setOpen((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const toggleStatusFilter = useCallback((key: StatusFilterKey) => {
    setStatusFilters((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const clearStatusFilters = useCallback(() => setStatusFilters(new Set()), []);

  const expandAll = useCallback(() => {
    setOpen(buildOpenMap(filteredGoals, true));
  }, [filteredGoals]);

  const collapseAll = useCallback(() => {
    setOpen(buildOpenMap(filteredGoals, false));
  }, [filteredGoals]);

  const clearSearch = useCallback(() => setSearchQuery(""), []);

  const closeDraft = useCallback(() => setDraft(null), []);

  if (!goals.length) {
    return (
      <p className="text-sm text-zinc-500" data-testid="epics-tree-empty">
        No goals returned from Brain.
      </p>
    );
  }

  return (
    <div data-testid="epics-tree" className="space-y-1">
      <Toaster richColors theme="dark" position="bottom-right" />
      <EpicHierarchyCrudModal draft={draft} onClose={closeDraft} />

      <div className="mb-3 flex flex-col gap-3 rounded-lg border border-zinc-800/80 bg-zinc-950/40 px-3 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[12rem] flex-1">
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search goals, epics, sprints, tasks…"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 py-1.5 pl-3 pr-9 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-zinc-600 focus:outline-none focus:ring-2 focus:ring-violet-500/40"
              aria-label="Search epics tree"
            />
            {searchQuery ? (
              <button
                type="button"
                onClick={clearSearch}
                className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                aria-label="Clear search"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            ) : null}
          </div>
          <span className="text-xs tabular-nums text-zinc-500">
            {searchOrConstraintActive && totalEpicCount > 0
              ? `${filteredEpicCount} of ${totalEpicCount} epics match`
              : `${totalEpicCount} epic${totalEpicCount === 1 ? "" : "s"}`}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
            Status
          </span>
          <button
            type="button"
            onClick={clearStatusFilters}
            className={cn(
              "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
              statusFilters.size === 0
                ? "border-violet-500 bg-violet-500/20 text-violet-200"
                : "border-zinc-700 bg-zinc-800 text-zinc-300 hover:border-zinc-600",
            )}
          >
            All
          </button>
          {STATUS_FILTER_KEYS.map((k) => {
            const on = statusFilters.has(k);
            return (
              <button
                key={k}
                type="button"
                onClick={() => toggleStatusFilter(k)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                  on
                    ? "border-violet-500 bg-violet-500/20 text-violet-200"
                    : "border-zinc-700 bg-zinc-800 text-zinc-300 hover:border-zinc-600",
                )}
              >
                {STATUS_FILTER_LABEL[k]}
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="sr-only" htmlFor="epics-owner-filter">
            Owner
          </label>
          <select
            id="epics-owner-filter"
            value={ownerFilter}
            onChange={(e) => setOwnerFilter(e.target.value)}
            className="h-8 min-w-[10rem] rounded-md border border-zinc-700 bg-zinc-900 px-2 text-xs text-zinc-100 focus:border-zinc-600 focus:outline-none focus:ring-2 focus:ring-violet-500/40"
          >
            <option value="">All owners</option>
            {ownerOptions.map((slug) => (
              <option key={slug} value={slug}>
                @{slug}
              </option>
            ))}
          </select>

          <label className="sr-only" htmlFor="epics-sort">
            Sort
          </label>
          <select
            id="epics-sort"
            value={sortMode}
            onChange={(e) => setSortMode(e.target.value as SortMode)}
            className="h-8 min-w-[9.5rem] rounded-md border border-zinc-700 bg-zinc-900 px-2 text-xs text-zinc-100 focus:border-zinc-600 focus:outline-none focus:ring-2 focus:ring-violet-500/40"
          >
            <option value="priority">Priority</option>
            <option value="activity">Recent activity</option>
            <option value="percent">Percent done</option>
            <option value="alpha">Alphabetical</option>
          </select>

          <div className="ml-auto flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              onClick={expandAll}
              className="rounded-md border border-zinc-700 bg-zinc-800 px-2 py-1 text-[11px] font-medium text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/80"
            >
              Expand all
            </button>
            <button
              type="button"
              onClick={collapseAll}
              className="rounded-md border border-zinc-700 bg-zinc-800 px-2 py-1 text-[11px] font-medium text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/80"
            >
              Collapse all
            </button>
            <button
              type="button"
              title="Add goal"
              className={cn(ghostIconButtonCls(), "h-8 w-8 gap-1 text-xs")}
              onClick={() =>
                setDraft({
                  mode: "create",
                  entity: "goal",
                  defaults: {},
                })
              }
            >
              <Plus className="h-4 w-4" aria-hidden />
              <span className="hidden font-medium text-[11px] uppercase tracking-wide text-zinc-500 sm:inline">
                Goal
              </span>
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-1 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2">
        {!filteredGoals.length ? (
          <p className="text-sm text-zinc-500" data-testid="epics-tree-filtered-empty">
            No epics match the current filters.
          </p>
        ) : (
          filteredGoals.map((goal) => (
            <GoalBlock
              key={goal.id}
              goal={goal}
              open={open[`g:${goal.id}`] ?? true}
              onToggle={() => toggle(`g:${goal.id}`)}
              setDraft={setDraft}
              renderEpics={() =>
                (goal.epics ?? []).map((epic) => (
                  <EpicBlock
                    key={epic.id}
                    epic={epic}
                    open={open[`e:${epic.id}`] ?? true}
                    onToggle={() => toggle(`e:${epic.id}`)}
                    setDraft={setDraft}
                    renderSprints={() =>
                      (epic.sprints ?? []).map((sprint) => (
                        <SprintBlock
                          key={sprint.id}
                          sprint={sprint}
                          epicId={epic.id}
                          open={open[`s:${sprint.id}`] ?? true}
                          onToggle={() => toggle(`s:${sprint.id}`)}
                          setDraft={setDraft}
                          renderTasks={() =>
                            (sprint.tasks ?? []).map((task) => (
                              <TaskRow
                                key={task.id}
                                task={task}
                                epicId={epic.id}
                                sprintId={sprint.id}
                                setDraft={setDraft}
                              />
                            ))
                          }
                        />
                      ))
                    }
                  />
                ))
              }
            />
          ))
        )}
      </div>
    </div>
  );
}
