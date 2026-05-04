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

export type SchedulerFreshnessGate = "last_run" | "next_run";

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
  const last = args.lastCompletedAt?.trim();
  if (last) {
    const t = Date.parse(last);
    if (Number.isNaN(t)) {
      return { healthy: false, gate: "last_run" };
    }
    const age = Date.now() - t;
    return {
      healthy: age <= staleThresholdMsForJobId(args.jobId),
      gate: "last_run",
    };
  }

  const nxt = args.nextRun?.trim();
  if (!nxt) {
    return { healthy: false, gate: "next_run" };
  }
  const nt = Date.parse(nxt);
  if (Number.isNaN(nt)) {
    return { healthy: false, gate: "next_run" };
  }
  const overdueBy = Date.now() - nt;
  return {
    healthy: overdueBy < NEXT_RUN_OVERDUE_MS,
    gate: "next_run",
  };
}
