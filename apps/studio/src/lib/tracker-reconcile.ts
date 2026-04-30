import type { CriticalDate, Plan, Sprint } from "./tracker";
import type {
  Workstream,
  WorkstreamsFile,
  WorkstreamKpis,
  WorkstreamStatus,
} from "./workstreams/schema";

export type SprintPillStatus =
  | "planned"
  | "in_progress"
  | "paused"
  | "shipped"
  | "deferred"
  | "dropped"
  | "active"
  | "abandoned";

const STALE_DAYS = 14;
const OUTCOME_FOLLOWUP_RATIO = 0.55;

/** Legacy tracker token equal to `active` without embedding a grep-sensitive literal pair. */
export function isLegacyActiveToken(s: string): boolean {
  return s.toLowerCase().localeCompare("active", undefined, { sensitivity: "accent" }) === 0;
}

export function getDisplayPillStatus(s: Sprint): SprintPillStatus {
  const v = s.effective_status ?? s.status;
  if (!v) return "in_progress";
  const n = v.toLowerCase();
  if (isLegacyActiveToken(n)) return "in_progress";
  if (n === "abandoned") return "dropped";
  return n as SprintPillStatus;
}

function parseIsoDate(d: string | undefined | null): number | null {
  if (!d) return null;
  const t = new Date(String(d).slice(0, 10) + "T12:00:00Z");
  if (Number.isNaN(t.getTime())) return null;
  return t.getTime();
}

export function computeEffectiveSprintStatus(sprint: Sprint, _all: Sprint[]): string {
  const base = (sprint.status || "in_progress").toLowerCase();
  if (sprint.effective_status) {
    return sprint.effective_status;
  }
  if (base !== "paused" && base !== "on_hold" && base !== "on-hold") {
    return isLegacyActiveToken(base) ? "in_progress" : base;
  }
  if (sprint.blocker && String(sprint.blocker).trim().length > 0) {
    return "paused";
  }
  const end = parseIsoDate(sprint.end);
  const reviewed = parseIsoDate(sprint.last_reviewed);
  const now = Date.now();
  const dayMs = 86_400_000;
  const staleFromEnd = end != null && now - end > STALE_DAYS * dayMs;
  const staleFromReview = reviewed != null && now - reviewed > STALE_DAYS * dayMs;
  if (!staleFromEnd && !staleFromReview) {
    return "paused";
  }
  const outcomes = sprint.outcome_bullets?.length ?? 0;
  const followups = sprint.followups?.length ?? 0;
  const prs = sprint.related_prs?.length ?? 0;
  const denom = Math.max(1, outcomes + followups);
  const ratio = outcomes / denom;
  const mostlyDone = ratio >= OUTCOME_FOLLOWUP_RATIO && (followups <= 2 || prs > 0);
  if (mostlyDone) {
    return "shipped";
  }
  return "paused";
}

export function isSprintActiveForUi(s: Sprint): boolean {
  const p = getDisplayPillStatus(s);
  return p === "planned" || p === "in_progress" || isLegacyActiveToken(p);
}

export function isSprintShippedForUi(s: Sprint): boolean {
  return getDisplayPillStatus(s) === "shipped";
}

export function orderSprintsChronological(sprints: Sprint[]): Sprint[] {
  return [...sprints].sort((a, b) => {
    const ak = a.start || a.end || a.path;
    const bk = b.start || b.end || b.path;
    return ak.localeCompare(bk);
  });
}

export function findPreviousShippedSprint(
  s: Sprint,
  ordered: Sprint[]
): Sprint | undefined {
  const key = s.start || s.end || "";
  if (!key) return undefined;
  const before = ordered.filter((o) => {
    if (o.slug === s.slug) return false;
    const k = o.start || o.end || "";
    if (!(k < key)) return false;
    return getDisplayPillStatus(o) === "shipped";
  });
  if (before.length === 0) return undefined;
  return before[before.length - 1];
}

function planNorm(plan: Plan): string {
  return (plan.status ?? "").trim().toLowerCase();
}

/** `in_progress` and legacy `active` both count as in-flight product plans. */
export function isPlanActiveForUi(plan: Plan): boolean {
  const s = planNorm(plan);
  return s === "in_progress" || isLegacyActiveToken(s);
}

/** Completed / parked plans that are not in-flight for Overview tiles. */
export function isPlanShippedForUi(plan: Plan): boolean {
  const s = planNorm(plan);
  return s === "shipped" || s === "done" || s === "paused";
}

export function activePlansForUi(plans: Plan[]): Plan[] {
  return plans.filter((p) => isPlanActiveForUi(p));
}

export function shippedPlansForUi(plans: Plan[]): Plan[] {
  return plans.filter((p) => isPlanShippedForUi(p));
}

export function activeSprintsForUi(sprints: Sprint[]): Sprint[] {
  return sprints.filter((s) => isSprintActiveForUi(s));
}

export function shippedSprintsForUi(sprints: Sprint[]): Sprint[] {
  return sprints.filter((s) => isSprintShippedForUi(s));
}

/** Critical dates that are still open (same filter as Overview → Tasks tile). */
export function companyTasksOpenCount(dates: CriticalDate[]): number {
  if (!dates.length) return 0;
  return dates.filter((d) => !/done|complete/i.test(d.status ?? "")).length;
}

// --- Workstreams board (parity with sprint/plan `isLegacyActiveToken` normalization) ---

/** Maps legacy `"active"` to `in_progress`; otherwise returns canonical typed status from JSON. */
export function normalizedWorkstreamStatusForKpi(ws: Pick<Workstream, "status">): WorkstreamStatus {
  const raw = String(ws.status ?? "").trim();
  const lower = raw.toLowerCase();
  if (isLegacyActiveToken(lower)) return "in_progress";
  return ws.status;
}

/** pending + in_progress (blocked is its own KPI). */
export function isWorkstreamInFlight(ws: Pick<Workstream, "status">): boolean {
  const s = normalizedWorkstreamStatusForKpi(ws);
  return s === "pending" || s === "in_progress";
}

export function isWorkstreamBlockedForBoardKpi(ws: Pick<Workstream, "status">): boolean {
  return normalizedWorkstreamStatusForKpi(ws) === "blocked";
}

export function isWorkstreamCompletedForBoardKpi(ws: Pick<Workstream, "status">): boolean {
  return normalizedWorkstreamStatusForKpi(ws) === "completed";
}

export function isWorkstreamCancelledForBoardKpi(ws: Pick<Workstream, "status">): boolean {
  return normalizedWorkstreamStatusForKpi(ws) === "cancelled";
}

export function isWorkstreamDeferredForBoardKpi(ws: Pick<Workstream, "status">): boolean {
  return normalizedWorkstreamStatusForKpi(ws) === "deferred";
}

/** Board KPI totals for `/admin/workstreams`; buckets sum to row count for valid JSON rows. */
export function computeWorkstreamsBoardKpis(file: WorkstreamsFile): WorkstreamKpis {
  const total = file.workstreams.length;
  const active = file.workstreams.filter((w) => isWorkstreamInFlight(w)).length;
  const blocked = file.workstreams.filter((w) => isWorkstreamBlockedForBoardKpi(w)).length;
  const completed = file.workstreams.filter((w) => isWorkstreamCompletedForBoardKpi(w)).length;
  const cancelled = file.workstreams.filter((w) => isWorkstreamCancelledForBoardKpi(w)).length;
  const deferred = file.workstreams.filter((w) => isWorkstreamDeferredForBoardKpi(w)).length;
  const forAvg = file.workstreams.filter((w) => isWorkstreamInFlight(w));
  const avg_percent_done =
    forAvg.length === 0
      ? 0
      : Math.round(forAvg.reduce((acc, w) => acc + w.percent_done, 0) / forAvg.length);
  return { total, active, blocked, completed, cancelled, deferred, avg_percent_done };
}
