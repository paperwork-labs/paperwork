import type { Sprint } from "./tracker";

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

export function getDisplayPillStatus(s: Sprint): SprintPillStatus {
  const v = s.effective_status ?? s.status;
  if (!v) return "in_progress";
  const n = v.toLowerCase();
  if (n === "active") return "in_progress";
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
    return base === "active" ? "in_progress" : base;
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
  return p === "planned" || p === "in_progress" || p === "active";
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
