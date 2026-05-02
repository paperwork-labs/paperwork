"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@paperwork-labs/ui";

import type {
  HierarchyGoalCreateInput,
  HierarchyGoalPatchInput,
  HierarchyEpicCreateInput,
  HierarchyEpicPatchInput,
  HierarchySprintCreateInput,
  HierarchySprintPatchInput,
  HierarchyTaskCreateInput,
  HierarchyTaskPatchInput,
} from "@/lib/brain-client";

import { epicHierarchyMutateJson } from "./epic-hierarchy-api";

export type HierarchyEntityKind = "goal" | "epic" | "sprint" | "task";

export type EpicCrudDraft = {
  mode: "create" | "edit";
  entity: HierarchyEntityKind;
  parentGoalId?: string;
  parentEpicId?: string;
  parentSprintId?: string;
  /** When creating tasks under a sprint, epic FK for Brain `Task.epic_id`. */
  epicIdForTasks?: string;
  defaults?: {
    id?: string;
    objective?: string;
    horizon?: string;
    status?: string;
    title?: string;
    priority?: number;
    owner_employee_slug?: string;
    brief_tag?: string;
    ordinal?: number;
    github_pr?: number | null;
    github_pr_url?: string | null;
  };
};

const GOAL_STATUSES = ["active", "paused", "completed"] as const;

const EPIC_STATUSES = ["backlog", "in_progress", "blocked", "paused", "done"] as const;

const SPRINT_STATUSES = ["planned", "active", "shipped", "paused"] as const;

const TASK_STATUSES = ["todo", "in_progress", "merged", "done"] as const;

function studioEntityId(kind: string) {
  const r =
    typeof globalThis.crypto !== "undefined" && "randomUUID" in globalThis.crypto
      ? globalThis.crypto.randomUUID().replace(/-/g, "").slice(0, 10)
      : `${Date.now()}`;
  return `studio-${kind}-${r}`;
}

function normStatus(sel: unknown, fallback: string) {
  if (typeof sel !== "string" || !sel.trim()) return fallback;
  return sel.trim();
}

type EpicHierarchyCrudModalProps = {
  draft: EpicCrudDraft | null;
  onClose: () => void;
};

export function EpicHierarchyCrudModal({ draft, onClose }: EpicHierarchyCrudModalProps) {
  const router = useRouter();

  const [busy, setBusy] = useState(false);

  const [objective, setObjective] = useState("");
  const [horizon, setHorizon] = useState("");
  const [goalStatus, setGoalStatus] = useState<string>("active");

  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState("0");
  const [ownerSlug, setOwnerSlug] = useState("");
  const [briefTag, setBriefTag] = useState("studio");

  const [epicStatus, setEpicStatus] = useState<string>("in_progress");
  const [sprintStatus, setSprintStatus] = useState<string>("planned");
  const [taskStatus, setTaskStatus] = useState<string>("todo");

  const [ordinal, setOrdinal] = useState("0");

  const [githubPr, setGithubPr] = useState("");
  const [githubPrUrl, setGithubPrUrl] = useState("");

  const [recordId, setRecordId] = useState<string | null>(null);

  useEffect(() => {
    if (!draft) return;
    const d = draft.defaults ?? {};
    setRecordId(d.id ?? null);
    setObjective(d.objective ?? "");
    setHorizon(d.horizon ?? "");
    setGoalStatus(normStatus(d.status, GOAL_STATUSES[0]));

    setTitle(d.title ?? "");
    setPriority(String(Number.isFinite(d.priority) ? d.priority : 0));
    setOwnerSlug(d.owner_employee_slug ?? "");
    setBriefTag(d.brief_tag ?? "studio");
    setGoalStatus(
      draft.entity === "goal"
        ? normStatus(d.status, GOAL_STATUSES[0])
        : GOAL_STATUSES[0],
    );
    setEpicStatus(
      draft.entity === "epic"
        ? normStatus(d.status, EPIC_STATUSES[1])
        : EPIC_STATUSES[1],
    );
    setSprintStatus(
      draft.entity === "sprint"
        ? normStatus(d.status, SPRINT_STATUSES[0])
        : SPRINT_STATUSES[0],
    );
    setTaskStatus(
      draft.entity === "task"
        ? normStatus(d.status, TASK_STATUSES[0])
        : TASK_STATUSES[0],
    );
    setOrdinal(String(Number.isFinite(d.ordinal) ? d.ordinal : 0));
    setGithubPr(d.github_pr != null && d.github_pr > 0 ? String(d.github_pr) : "");
    setGithubPrUrl(d.github_pr_url ?? "");
  }, [draft]);

  const open = Boolean(draft);
  const mode = draft?.mode ?? "create";
  const entity = draft?.entity ?? "goal";

  const handleSubmit = async () => {
    if (!draft) return;
    setBusy(true);
    try {
      if (draft.entity === "goal") {
        if (!objective.trim() || !horizon.trim()) {
          toast.error("Objective and horizon are required.");
          return;
        }
        if (draft.mode === "create") {
          const body: HierarchyGoalCreateInput = {
            id: studioEntityId("goal"),
            objective: objective.trim(),
            horizon: horizon.trim(),
            metric: "(studio)",
            target: "manual",
            status: goalStatus,
            written_at: new Date().toISOString(),
          };
          const r = await epicHierarchyMutateJson(["goals"], "POST", body);
          if (!r.ok) throw new Error(r.errorMessage ?? "Create goal failed");
        } else if (recordId) {
          const patch: HierarchyGoalPatchInput = {
            objective: objective.trim(),
            horizon: horizon.trim(),
            status: goalStatus,
          };
          const r = await epicHierarchyMutateJson(
            ["goals", recordId],
            "PATCH",
            patch,
          );
          if (!r.ok) throw new Error(r.errorMessage ?? "Update goal failed");
        }
      } else if (draft.entity === "epic") {
        const gid = draft.parentGoalId;
        if (draft.mode === "create" && !gid) {
          toast.error("Missing parent goal.");
          return;
        }
        const pr = Number.parseInt(priority, 10);
        if (draft.mode === "create") {
          const body: HierarchyEpicCreateInput = {
            id: studioEntityId("ws"),
            title: title.trim() || "Untitled epic",
            goal_id: gid!,
            owner_employee_slug: ownerSlug.trim() || "unassigned",
            status: epicStatus,
            priority: Number.isFinite(pr) && pr >= 0 ? pr : 0,
            brief_tag: briefTag.trim() || "studio",
            percent_done: 0,
          };
          const r = await epicHierarchyMutateJson(["epics"], "POST", body);
          if (!r.ok) throw new Error(r.errorMessage ?? "Create epic failed");
        } else if (recordId) {
          const patch: HierarchyEpicPatchInput = {
            ...(title.trim() ? { title: title.trim() } : {}),
            ...(Number.isFinite(pr) && pr >= 0 ? { priority: pr } : {}),
            status: epicStatus,
            ...(ownerSlug.trim()
              ? { owner_employee_slug: ownerSlug.trim() }
              : {}),
            ...(briefTag.trim() ? { brief_tag: briefTag.trim() } : {}),
          };
          const r = await epicHierarchyMutateJson(
            ["epics", recordId],
            "PATCH",
            patch,
          );
          if (!r.ok) throw new Error(r.errorMessage ?? "Update epic failed");
        }
      } else if (draft.entity === "sprint") {
        const eid = draft.parentEpicId;
        if (draft.mode === "create" && !eid) {
          toast.error("Missing parent epic.");
          return;
        }
        const ord = Number.parseInt(ordinal, 10);
        if (draft.mode === "create") {
          const body: HierarchySprintCreateInput = {
            id: studioEntityId("sprint"),
            epic_id: eid!,
            title: title.trim() || "Untitled sprint",
            status: sprintStatus,
            ordinal: Number.isFinite(ord) ? ord : 0,
          };
          const r = await epicHierarchyMutateJson(["sprints"], "POST", body);
          if (!r.ok) throw new Error(r.errorMessage ?? "Create sprint failed");
        } else if (recordId) {
          const patch: HierarchySprintPatchInput = {
            ...(title.trim() ? { title: title.trim() } : {}),
            ...(Number.isFinite(ord) ? { ordinal: ord } : {}),
            status: sprintStatus,
          };
          const r = await epicHierarchyMutateJson(
            ["sprints", recordId],
            "PATCH",
            patch,
          );
          if (!r.ok) throw new Error(r.errorMessage ?? "Update sprint failed");
        }
      } else if (draft.entity === "task") {
        const sid = draft.parentSprintId;
        const eTask = draft.epicIdForTasks ?? draft.parentEpicId;
        if (draft.mode === "create" && (!sid || !eTask)) {
          toast.error("Missing sprint or epic reference for task.");
          return;
        }
        const prParsed = githubPr.trim() !== "" ? Number.parseInt(githubPr, 10) : NaN;
        const gh =
          Number.isFinite(prParsed) && prParsed > 0 ? prParsed : null;
        if (draft.mode === "create") {
          const body: HierarchyTaskCreateInput = {
            id: studioEntityId("task"),
            sprint_id: sid!,
            epic_id: eTask!,
            title: title.trim() || "Untitled task",
            status: taskStatus,
            github_pr: gh,
            github_pr_url: githubPrUrl.trim() ? githubPrUrl.trim() : null,
            owner_employee_slug: ownerSlug.trim() ? ownerSlug.trim() : null,
          };
          const r = await epicHierarchyMutateJson(["tasks"], "POST", body);
          if (!r.ok) throw new Error(r.errorMessage ?? "Create task failed");
        } else if (recordId) {
          const patch: HierarchyTaskPatchInput = {
            ...(title.trim() ? { title: title.trim() } : {}),
            status: taskStatus,
            github_pr: gh,
            github_pr_url: githubPrUrl.trim() ? githubPrUrl.trim() : null,
            ...(ownerSlug.trim()
              ? { owner_employee_slug: ownerSlug.trim() }
              : {}),
          };
          const r = await epicHierarchyMutateJson(
            ["tasks", recordId],
            "PATCH",
            patch,
          );
          if (!r.ok) throw new Error(r.errorMessage ?? "Update task failed");
        }
      }

      toast.success(draft.mode === "create" ? "Created." : "Saved.");
      onClose();
      router.refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Mutation failed.");
    } finally {
      setBusy(false);
    }
  };

  const titleLabel =
    entity === "goal"
      ? "Goal"
      : entity === "epic"
        ? "Epic"
        : entity === "sprint"
          ? "Sprint"
          : "Task";

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto border-zinc-800 bg-zinc-950 text-zinc-100 sm:max-w-lg [&_select]:cursor-pointer [&_select]:rounded-md [&_select]:border [&_select]:border-zinc-700 [&_select]:bg-zinc-900 [&_select]:py-2 [&_select]:text-sm [&_select]:text-zinc-100">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? `Add ${titleLabel}` : `Edit ${titleLabel}`}
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            Changes sync to Brain through the Studio admin proxy.
          </DialogDescription>
        </DialogHeader>

        {draft && draft.entity === "goal" ? (
          <div className="grid gap-3 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="ep-crud-objective" className="text-zinc-300">
                Objective
              </Label>
              <Input
                id="ep-crud-objective"
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                className="border-zinc-700 bg-zinc-900 text-zinc-100"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ep-crud-horizon" className="text-zinc-300">
                Horizon (e.g. Q2-2026)
              </Label>
              <Input
                id="ep-crud-horizon"
                value={horizon}
                onChange={(e) => setHorizon(e.target.value)}
                className="border-zinc-700 bg-zinc-900 text-zinc-100"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-zinc-300">Status</Label>
              <Select value={goalStatus} onValueChange={setGoalStatus}>
                <SelectTrigger className="border-zinc-700 bg-zinc-900 text-zinc-100 [&>span]:capitalize">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="border-zinc-800 bg-zinc-950">
                  {GOAL_STATUSES.map((s) => (
                    <SelectItem
                      key={s}
                      value={s}
                      className="capitalize focus:bg-zinc-900 focus:text-zinc-100"
                    >
                      {s.replace(/_/g, " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        ) : null}

        {draft && draft.entity === "epic" ? (
          <div className="grid gap-3 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="ep-crud-title" className="text-zinc-300">
                Title
              </Label>
              <Input
                id="ep-crud-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="border-zinc-700 bg-zinc-900 text-zinc-100"
              />
            </div>
            <div className="flex gap-2">
              <div className="min-w-0 flex-1 space-y-1.5">
                <Label htmlFor="ep-crud-priority" className="text-zinc-300">
                  Priority (number)
                </Label>
                <Input
                  id="ep-crud-priority"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="border-zinc-700 bg-zinc-900 text-zinc-100"
                />
              </div>
              <div className="flex-1 space-y-1.5">
                <Label className="text-zinc-300">Status</Label>
                <Select value={epicStatus} onValueChange={setEpicStatus}>
                  <SelectTrigger className="border-zinc-700 bg-zinc-900 text-zinc-100 [&>span]:capitalize">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="border-zinc-800 bg-zinc-950">
                    {EPIC_STATUSES.map((s) => (
                      <SelectItem
                        key={s}
                        value={s}
                        className="capitalize focus:bg-zinc-900 focus:text-zinc-100"
                      >
                        {s.replace(/_/g, " ")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ep-crud-owner-epic" className="text-zinc-300">
                Owner employee slug
              </Label>
              <Input
                id="ep-crud-owner-epic"
                value={ownerSlug}
                onChange={(e) => setOwnerSlug(e.target.value)}
                placeholder="Optional"
                className="border-zinc-700 bg-zinc-900 text-zinc-100"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ep-crud-tag" className="text-zinc-300">
                Brief tag
              </Label>
              <Input
                id="ep-crud-tag"
                value={briefTag}
                onChange={(e) => setBriefTag(e.target.value)}
                className="border-zinc-700 bg-zinc-900 text-zinc-100"
              />
            </div>
          </div>
        ) : null}

        {draft && draft.entity === "sprint" ? (
          <div className="grid gap-3 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="sp-title" className="text-zinc-300">
                Title
              </Label>
              <Input
                id="sp-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="border-zinc-700 bg-zinc-900 text-zinc-100"
              />
            </div>
            <div className="flex gap-2">
              <div className="flex-1 space-y-1.5">
                <Label htmlFor="sp-ordinal" className="text-zinc-300">
                  Ordinal
                </Label>
                <Input
                  id="sp-ordinal"
                  type="number"
                  inputMode="numeric"
                  value={ordinal}
                  onChange={(e) => setOrdinal(e.target.value)}
                  className="border-zinc-700 bg-zinc-900 text-zinc-100"
                />
              </div>
              <div className="flex-1 space-y-1.5">
                <Label className="text-zinc-300">Status</Label>
                <Select value={sprintStatus} onValueChange={setSprintStatus}>
                  <SelectTrigger className="border-zinc-700 bg-zinc-900 text-zinc-100 [&>span]:capitalize">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="border-zinc-800 bg-zinc-950">
                    {SPRINT_STATUSES.map((s) => (
                      <SelectItem
                        key={s}
                        value={s}
                        className="capitalize focus:bg-zinc-900 focus:text-zinc-100"
                      >
                        {s.replace(/_/g, " ")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        ) : null}

        {draft && draft.entity === "task" ? (
          <div className="grid gap-3 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="tsk-title" className="text-zinc-300">
                Title
              </Label>
              <Input
                id="tsk-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="border-zinc-700 bg-zinc-900 text-zinc-100"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-zinc-300">Status</Label>
              <Select value={taskStatus} onValueChange={setTaskStatus}>
                <SelectTrigger className="border-zinc-700 bg-zinc-900 text-zinc-100 [&>span]:capitalize">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="border-zinc-800 bg-zinc-950">
                  {TASK_STATUSES.map((s) => (
                    <SelectItem
                      key={s}
                      value={s}
                      className="capitalize focus:bg-zinc-900 focus:text-zinc-100"
                    >
                      {s.replace(/_/g, " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-2">
              <div className="flex-1 space-y-1.5">
                <Label htmlFor="tsk-pr" className="text-zinc-300">
                  GitHub PR (optional)
                </Label>
                <Input
                  id="tsk-pr"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  value={githubPr}
                  onChange={(e) => setGithubPr(e.target.value)}
                  className="border-zinc-700 bg-zinc-900 text-zinc-100"
                  placeholder=""
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tsk-pr-url" className="text-zinc-300">
                GitHub PR URL (optional)
              </Label>
              <Input
                id="tsk-pr-url"
                value={githubPrUrl}
                onChange={(e) => setGithubPrUrl(e.target.value)}
                placeholder="https://github.com/…"
                className="border-zinc-700 bg-zinc-900 text-zinc-100"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tsk-owner" className="text-zinc-300">
                Owner employee slug (optional)
              </Label>
              <Input
                id="tsk-owner"
                value={ownerSlug}
                onChange={(e) => setOwnerSlug(e.target.value)}
                className="border-zinc-700 bg-zinc-900 text-zinc-100"
              />
            </div>
          </div>
        ) : null}

        <DialogFooter className="gap-2 border-t border-zinc-900 pt-4 sm:gap-3">
          <Button
            type="button"
            variant="ghost"
            onClick={() => onClose()}
            disabled={busy}
            className="text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={busy || !draft}
            className="border border-zinc-600 bg-zinc-800 text-zinc-100 hover:bg-zinc-700"
          >
            {busy ? "Saving…" : mode === "create" ? "Create" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
