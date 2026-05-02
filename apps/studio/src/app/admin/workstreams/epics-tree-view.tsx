"use client";

import { useMemo, useState, type ReactNode } from "react";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Circle,
  ExternalLink,
} from "lucide-react";
import { Badge, Progress, cn } from "@paperwork-labs/ui";

import type { EpicItem, GoalItem, SprintItem, TaskItem } from "@/lib/brain-client";

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
}: {
  goal: GoalItem;
  open: boolean;
  onToggle: () => void;
  renderEpics: () => ReactNode;
}) {
  return (
    <div className="border-b border-zinc-800/80 pb-2 last:border-b-0">
      <ToggleRow open={open} onToggle={onToggle} depthClass="pl-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-zinc-100">
            Goal: {goal.objective}
          </span>
          <HorizonBadge horizon={goal.horizon} />
          <Badge variant="outline" className={cn("text-[10px] capitalize", statusBadgeClass(goal.status))}>
            {goal.status.replace(/_/g, " ")}
          </Badge>
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
}: {
  epic: EpicItem;
  open: boolean;
  onToggle: () => void;
  renderSprints: () => ReactNode;
}) {
  const pct = Math.min(100, Math.max(0, epic.percent_done ?? 0));
  return (
    <div>
      <ToggleRow open={open} onToggle={onToggle} depthClass="pl-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
            <span
              className={cn("inline-block h-2 w-2 shrink-0 rounded-full ring-2 ring-offset-0 ring-offset-zinc-950", statusDotClass(epic.status))}
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
            <Badge variant="outline" className={cn("text-[10px] capitalize", statusBadgeClass(epic.status))}>
              {epic.status.replace(/_/g, " ")}
            </Badge>
            {epic.owner_employee_slug ? (
              <span className="text-[10px] uppercase tracking-wide text-zinc-500">
                @{epic.owner_employee_slug}
              </span>
            ) : null}
          </div>
        </div>
      </ToggleRow>
      {open ? <div>{renderSprints()}</div> : null}
    </div>
  );
}

function SprintBlock({
  sprint,
  open,
  onToggle,
  renderTasks,
}: {
  sprint: SprintItem;
  open: boolean;
  onToggle: () => void;
  renderTasks: () => ReactNode;
}) {
  const tasks = sprint.tasks ?? [];
  const count = tasks.length;
  return (
    <div>
      <ToggleRow open={open} onToggle={onToggle} depthClass="pl-8">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-zinc-200">{sprint.title}</span>
          <span className="text-xs text-zinc-500">
            ({count} task{count === 1 ? "" : "s"})
          </span>
          <Badge variant="outline" className={cn("text-[10px] capitalize", statusBadgeClass(sprint.status))}>
            {sprint.status.replace(/_/g, " ")}
          </Badge>
        </div>
      </ToggleRow>
      {open ? <div>{renderTasks()}</div> : null}
    </div>
  );
}

function TaskRow({ task }: { task: TaskItem }) {
  const done = taskIsDone(task.status);
  return (
    <div className="flex items-start gap-2 py-1 pl-12 pr-2 text-sm">
      {done ? (
        <CheckCircle2
          className="mt-0.5 h-4 w-4 shrink-0 text-[var(--status-success)]"
          aria-hidden
        />
      ) : (
        <Circle
          className="mt-0.5 h-4 w-4 shrink-0 text-zinc-600"
          aria-hidden
        />
      )}
      <div className="min-w-0 flex-1">
        <span className={cn("text-zinc-200", done && "text-zinc-400 line-through")}>
          {task.title}
        </span>
        {task.github_pr_url ? (
          <>
            {" "}
            <a
              href={task.github_pr_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-0.5 text-xs text-sky-400 hover:underline"
            >
              #{task.github_pr ?? "PR"}
              <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          </>
        ) : task.github_pr != null ? (
          <span className="text-xs text-zinc-500"> (#{task.github_pr})</span>
        ) : null}
        <span className="text-xs text-zinc-500"> — {task.status}</span>
        {task.owner_employee_slug ? (
          <span className="ml-2 text-[10px] uppercase tracking-wide text-zinc-500">
            @{task.owner_employee_slug}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export type EpicsTreeViewProps = {
  goals: GoalItem[];
};

export function EpicsTreeView({ goals }: EpicsTreeViewProps) {
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

  const toggle = (key: string) => {
    setOpen((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (!goals.length) {
    return (
      <p className="text-sm text-zinc-500" data-testid="epics-tree-empty">
        No goals returned from Brain.
      </p>
    );
  }

  return (
    <div className="space-y-1 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2" data-testid="epics-tree">
      {goals.map((goal) => (
        <GoalBlock
          key={goal.id}
          goal={goal}
          open={open[`g:${goal.id}`] ?? true}
          onToggle={() => toggle(`g:${goal.id}`)}
          renderEpics={() =>
            (goal.epics ?? []).map((epic) => (
              <EpicBlock
                key={epic.id}
                epic={epic}
                open={open[`e:${epic.id}`] ?? true}
                onToggle={() => toggle(`e:${epic.id}`)}
                renderSprints={() =>
                  (epic.sprints ?? []).map((sprint) => (
                    <SprintBlock
                      key={sprint.id}
                      sprint={sprint}
                      open={open[`s:${sprint.id}`] ?? true}
                      onToggle={() => toggle(`s:${sprint.id}`)}
                      renderTasks={() =>
                        (sprint.tasks ?? []).map((task) => (
                          <TaskRow key={task.id} task={task} />
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
  );
}
