"use client";

import { useCallback, useMemo, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Circle,
  ExternalLink,
  Pencil,
  Plus,
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

const GOAL_STATUS_OPTIONS = ["active", "paused", "completed"] as const;

const EPIC_STATUS_OPTIONS = ["backlog", "in_progress", "blocked", "paused", "done"] as const;

const SPRINT_STATUS_OPTIONS = ["planned", "active", "shipped", "paused"] as const;

const TASK_STATUS_OPTIONS = ["todo", "in_progress", "merged", "done"] as const;

type DraftSetter = Dispatch<SetStateAction<EpicCrudDraft | null>>;

function normStatus(s: string) {
  return s.trim().toLowerCase().replace(/\s+/g, "_");
}

function statusDotClass(status: string): string {
  const n = normStatus(status);
  if (n === "blocked") {
    return "bg-[var(--status-danger)] ring-[var(--status-danger)]/40";
  }
  if (
    n === "in_progress" ||
    n === "active" ||
    n === "in-progress" ||
    n === "started"
  ) {
    return "bg-[var(--status-warning)] ring-[var(--status-warning)]/40";
  }
  if (n === "backlog" || n === "pending" || n === "planned" || n === "todo") {
    return "bg-zinc-500 ring-zinc-400/30";
  }
  if (
    n === "done" ||
    n === "shipped" ||
    n === "merged" ||
    n === "complete" ||
    n === "closed"
  ) {
    return "bg-[var(--status-success)] ring-[var(--status-success)]/40";
  }
  return "bg-zinc-500 ring-zinc-400/30";
}

function statusBadgeClass(status: string): string {
  const n = normStatus(status);
  if (n === "blocked") {
    return "border-[var(--status-danger)]/50 bg-[var(--status-danger-bg)] text-[var(--status-danger)]";
  }
  if (
    n === "in_progress" ||
    n === "active" ||
    n === "in-progress" ||
    n === "started"
  ) {
    return "border-[var(--status-warning)]/50 bg-[var(--status-warning-bg)] text-[var(--status-warning)]";
  }
  if (n === "backlog" || n === "pending" || n === "planned" || n === "todo") {
    return "border-zinc-600 bg-zinc-800/70 text-zinc-300";
  }
  if (
    n === "done" ||
    n === "shipped" ||
    n === "merged" ||
    n === "complete" ||
    n === "closed"
  ) {
    return "border-[var(--status-success)]/50 bg-[var(--status-success-bg)] text-[var(--status-success)]";
  }
  return "border-zinc-600 bg-zinc-800/60 text-zinc-400";
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
          className={cn(
            "inline-flex shrink-0 items-center rounded border px-1.5 py-0 capitalize shadow-sm outline-none transition hover:opacity-90 focus-visible:ring-2 focus-visible:ring-[var(--status-info)]",
            statusBadgeClass(status),
            "text-[10px] font-medium tracking-tight",
          )}
        >
          {status.replace(/_/g, " ")}
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
            <span className="font-medium text-zinc-100">
              Goal: {goal.objective}
            </span>
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
      {open ? <div className="mt-1 space-y-0.5">{renderEpics()}</div> : null}
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
  return (
    <div>
      <ToggleRow open={open} onToggle={onToggle} depthClass="pl-4">
        <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
          <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
              <span
                className={cn(
                  "inline-block h-2 w-2 shrink-0 rounded-full ring-2 ring-offset-0 ring-offset-zinc-950",
                  statusDotClass(epic.status),
                )}
                title={epic.status}
                aria-hidden
              />
              <span className="font-mono text-xs text-violet-300">{epic.id}</span>
              <span className="text-sm text-zinc-200">— {epic.title}</span>
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
      {open ? <div>{renderSprints()}</div> : null}
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
            <span className="text-zinc-200">{sprint.title}</span>
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
        <div>
          {renderTasks()}
        </div>
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
  return (
    <div className="flex items-start gap-2 py-1 pl-12 pr-2 text-sm">
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
        <div className="flex flex-wrap items-center gap-x-2 text-xs text-zinc-500">
          {task.github_pr_url ? (
            <a
              href={task.github_pr_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-0.5 text-sky-400 hover:underline"
            >
              #{task.github_pr ?? "PR"}
              <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          ) : task.github_pr != null ? (
            <span>(#{task.github_pr})</span>
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

  const toggle = useCallback((key: string) => {
    setOpen((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

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
      <div className="mb-2 flex justify-end rounded-lg border border-zinc-800/80 bg-zinc-950/30 px-2 py-1.5">
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
          <span className="hidden sm:inline font-medium text-[11px] uppercase tracking-wide text-zinc-500">
            Goal
          </span>
        </button>
      </div>
      <div className="space-y-1 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2">
        {goals.map((goal) => (
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
        ))}
      </div>
    </div>
  );
}
