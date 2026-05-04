/**
 * Scheduler row presentation (Studio `/admin/overview` — Track T1.7).
 *
 * **Next-run heuristic** (when Brain does not yet expose `last_completed_at` for the job):
 * - **Red (danger):** `next_run` is null, unparsable, in the past beyond the overdue grace window, or last-run
 *   age exceeds the per-job SLA when `last_completed_at` is present.
 * - **Amber (warn):** `next_run` is more than **24 hours in the future** — unexpectedly deferred; confirm
 *   `BRAIN_SCHEDULER_ENABLED`, paused brain, or trigger definitions (not a substitute for last-run truth).
 * - **Green (ok):** otherwise — next firing within 24h and not overdue, or last-run within SLA and next run
 *   is not “far future”.
 *
 * Last-run data from Brain (T1.7 follow-up) will tighten the red path; next-run remains a fallback signal only.
 */

/** Founder-tunable later (config / env); values are max age since LAST run before marking stale. */
const LAST_RUN_STALE_MS_BY_JOB_ID: Record<string, number> = {
  brain_autopilot_dispatcher: 5 * 60 * 1000,
  autopilot_dispatcher: 5 * 60 * 1000,
  brain_probe_failure_dispatcher: 15 * 60 * 1000,
  probe_failure_dispatcher: 15 * 60 * 1000,
  secrets_drift_audit: 24 * 60 * 60 * 1000,
  secrets_rotation_monitor: 24 * 60 * 60 * 1000,
  secrets_health_probe: 24 * 60 * 60 * 1000,
  secret_expiry_monitor: 24 * 60 * 60 * 1000,
  brain_credential_expiry: 24 * 60 * 60 * 1000,
  credential_expiry_monitor: 24 * 60 * 60 * 1000,
};

const DEFAULT_LAST_RUN_STALE_MS = 60 * 60 * 1000;

/** Grace after a missed `next_run` before treating schedule as overdue (scheduler clock / skew). */
const NEXT_RUN_OVERDUE_MS = 90 * 1000;

/** Next firing farther than this from now → amber “far future” (see module docstring). */
const NEXT_RUN_FAR_FUTURE_MS = 24 * 60 * 60 * 1000;

export type SchedulerStaleBadge = "ok" | "warn" | "danger";

export type SchedulerFreshnessGate = "last_run" | "next_run";

/** Next-run shape only — used when no trustworthy last-run timestamp exists. */
export function nextRunScheduleConcern(nextRun: string | null | undefined): SchedulerStaleBadge {
  const nxt = nextRun?.trim();
  if (!nxt) return "danger";
  const nt = Date.parse(nxt);
  if (Number.isNaN(nt)) return "danger";
  const overdueBy = Date.now() - nt;
  if (overdueBy >= NEXT_RUN_OVERDUE_MS) return "danger";
  const untilNext = nt - Date.now();
  if (untilNext > NEXT_RUN_FAR_FUTURE_MS) return "warn";
  return "ok";
}

export function schedulerStaleBadgeForJob(job: {
  id: string;
  last_completed_at?: string | null;
  next_run?: string | null;
}): { badge: SchedulerStaleBadge; label: string } {
  const last = job.last_completed_at?.trim();
  if (last) {
    const t = Date.parse(last);
    if (Number.isNaN(t)) {
      return { badge: "danger", label: "Invalid last-run timestamp" };
    }
    const age = Date.now() - t;
    if (age > staleThresholdMsForJobId(job.id)) {
      return { badge: "danger", label: "Stale (last run)" };
    }
    const concern = nextRunScheduleConcern(job.next_run);
    if (concern === "warn") {
      return { badge: "warn", label: "Next run >24h out" };
    }
    if (concern === "danger") {
      return { badge: "danger", label: "Schedule risk (next run)" };
    }
    return { badge: "ok", label: "Within last-run SLA" };
  }

  const concern = nextRunScheduleConcern(job.next_run);
  if (concern === "danger") {
    return {
      badge: "danger",
      label: job.next_run?.trim() ? "Next run overdue" : "No next run",
    };
  }
  if (concern === "warn") {
    return { badge: "warn", label: "Next run >24h out" };
  }
  return { badge: "ok", label: "Next run scheduled" };
}

export function staleThresholdMsForJobId(jobId: string): number {
  return LAST_RUN_STALE_MS_BY_JOB_ID[jobId] ?? DEFAULT_LAST_RUN_STALE_MS;
}

export function relativeLabelFromIso(iso: string | null | undefined): string {
  if (iso == null || iso === "") return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  let deltaSec = Math.round((Date.now() - t) / 1000);
  if (deltaSec === 0) return "now";
  const humanShort = (absSec: number): string => {
    if (absSec < 60) return `${absSec}s`;
    const mins = Math.round(absSec / 60);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.round(absSec / 3600);
    if (hrs < 48) return `${hrs}h`;
    const days = Math.round(absSec / 86400);
    return `${days}d`;
  };
  if (deltaSec > 0) return `${humanShort(deltaSec)} ago`;
  return `in ${humanShort(Math.abs(deltaSec))}`;
}

/**
 * Prefer last-run staleness when `last_completed_at` is present; otherwise fall back to schedule overdue.
 */
export function evaluateSchedulerRowHealth(args: {
  jobId: string;
  lastCompletedAt?: string | null;
  nextRun?: string | null;
}): { healthy: boolean; gate: SchedulerFreshnessGate } {
  const { badge } = schedulerStaleBadgeForJob({
    id: args.jobId,
    last_completed_at: args.lastCompletedAt,
    next_run: args.nextRun,
  });
  const gate: SchedulerFreshnessGate = args.lastCompletedAt?.trim() ? "last_run" : "next_run";
  return { healthy: badge === "ok", gate };
}
