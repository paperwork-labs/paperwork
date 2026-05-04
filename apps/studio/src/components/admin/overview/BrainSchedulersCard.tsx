"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2, Clock, RefreshCw } from "lucide-react";

import { HqErrorState } from "@/components/admin/hq/HqErrorState";
import { StatusBadge } from "@/components/admin/hq/StatusBadge";
import { useBrainSchedulers } from "@/hooks/useBrainSchedulers";
import {
  relativeLabelFromIso,
  schedulerStaleBadgeForJob,
  type SchedulerStaleBadge,
} from "@/lib/brain-schedulers-freshness";
import type { BrainSchedulerJob } from "@/types/brain-schedulers";
import { Button } from "@paperwork-labs/ui";
import type { StatusLevel } from "@/styles/design-tokens";

/** Master plan tracker for T1.7 backend follow-up (SchedulerRun export + Studio wiring). */
const T1_7_FOLLOWUP_HREF =
  "https://github.com/paperwork-labs/paperwork/blob/main/docs/plans/PAPERWORK_LABS_2026Q2_MASTER_PLAN.md";

function classificationPresentation(c: string): { label: string; status: StatusLevel } {
  const x = c.toLowerCase().trim();
  if (x === "cutover") return { label: "cutover", status: "info" };
  if (x === "operational") return { label: "operational", status: "neutral" };
  if (x === "net-new") return { label: "net-new", status: "warning" };
  return { label: c || "unknown", status: "neutral" };
}

function staleBadgeStatus(b: SchedulerStaleBadge): StatusLevel {
  if (b === "ok") return "success";
  if (b === "warn") return "warning";
  return "danger";
}

function BrainSchedulersSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true">
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={String(i)} className="animate-pulse space-y-2">
          <div className="flex items-center gap-3">
            <div className="h-4 w-[min(240px,50%)] rounded bg-zinc-800/90" />
            <div className="h-6 w-20 rounded-full bg-zinc-800/90" />
          </div>
          <div className="h-3 w-full rounded bg-zinc-800/60" />
        </div>
      ))}
    </div>
  );
}

function RowFreshnessIndicators({ job }: { job: BrainSchedulerJob }) {
  const { badge, label } = schedulerStaleBadgeForJob({
    id: job.id,
    last_completed_at: job.last_completed_at,
    next_run: job.next_run,
  });

  return (
    <span className="flex items-center gap-2">
      {badge === "ok" ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-[var(--status-success)]" aria-hidden />
      ) : badge === "warn" ? (
        <AlertTriangle className="h-4 w-4 shrink-0 text-[var(--status-warning)]" aria-hidden />
      ) : (
        <Clock className="h-4 w-4 shrink-0 text-[var(--status-danger)]" aria-hidden />
      )}
      <span className="text-xs text-zinc-400">{label}</span>
    </span>
  );
}

export function BrainSchedulersCard() {
  const { loading, data, error, retry } = useBrainSchedulers();

  if (loading) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 ring-1 ring-zinc-800 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              Scheduler jobs
            </p>
            <p className="mt-1 font-mono text-xs text-zinc-500">
              Brain <span className="text-zinc-400">GET /internal/schedulers</span>
            </p>
          </div>
        </div>
        <BrainSchedulersSkeleton />
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 ring-1 ring-zinc-800 sm:p-6">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Scheduler jobs</p>
        <div className="mt-3">
          <HqErrorState
            title="Could not load Brain schedulers"
            description="The proxy could not reach Brain or returned an unexpected response."
            error={error}
            onRetry={() => retry()}
          />
        </div>
      </section>
    );
  }

  if (!data) {
    return null;
  }

  if (data.status === "empty") {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 ring-1 ring-zinc-800 sm:p-6">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Scheduler jobs</p>
        <div className="mt-3 rounded-lg border border-[var(--status-warning)]/35 bg-[var(--status-warning-bg)] px-3 py-2 text-sm text-[var(--status-warning)]">
          {data.message}
        </div>
        <p className="mt-4 text-xs leading-relaxed text-zinc-400">
          Confirm <code className="rounded bg-zinc-900/80 px-1 py-0.5 font-mono text-[11px] text-zinc-300">BRAIN_SCHEDULER_ENABLED</code>{" "}
          on Brain and that{" "}
          <code className="rounded bg-zinc-900/80 px-1 py-0.5 font-mono text-[11px] text-zinc-300">
            /internal/schedulers
          </code>{" "}
          returns job rows —{" "}
          <Link
            href={T1_7_FOLLOWUP_HREF}
            className="text-sky-400 underline-offset-4 hover:text-sky-300 hover:underline"
            target="_blank"
            rel="noreferrer noopener"
          >
            Master plan — T1.7 follow-up
          </Link>
          .
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-4 min-h-11 border-zinc-600 bg-transparent px-6 text-zinc-200 hover:bg-zinc-900 hover:text-white"
          onClick={() => retry()}
        >
          <RefreshCw className="mr-2 h-4 w-4" aria-hidden />
          Retry fetch
        </Button>
      </section>
    );
  }

  const { jobs, lastRunExported } = data;

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 ring-1 ring-zinc-800 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Scheduler jobs</p>
          <p className="mt-1 font-mono text-xs text-zinc-500">
            Brain <span className="text-zinc-400">GET /internal/schedulers</span> · {jobs.length} job
            {jobs.length === 1 ? "" : "s"}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {lastRunExported ? (
            <StatusBadge status="success" size="sm">
              Last-run export
            </StatusBadge>
          ) : (
            <StatusBadge status="warning" size="sm">
              Next-run-only
            </StatusBadge>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="min-h-11 border-zinc-600 bg-transparent text-zinc-200 hover:bg-zinc-900 hover:text-white"
            onClick={() => retry()}
          >
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden />
            Refresh
          </Button>
        </div>
      </div>

      {!lastRunExported ? (
        <p className="mt-3 text-xs leading-relaxed text-zinc-500">
          <strong className="text-zinc-400">Staleness heuristic:</strong> without last-run timestamps, rows are{" "}
          <strong className="text-[var(--status-danger)]">red</strong> when <code className="font-mono text-zinc-400">next_run</code> is
          missing, invalid, or overdue (past the grace window);{" "}
          <strong className="text-[var(--status-warning)]">amber</strong> when the next firing is{" "}
          <strong>more than 24 hours away</strong> (unexpectedly deferred);{" "}
          <strong className="text-[var(--status-success)]">green</strong> otherwise. When Brain exports{" "}
          <code className="font-mono text-zinc-400">last_completed_at</code>, last-run SLA wins for red/green. See{" "}
          <Link
            href={T1_7_FOLLOWUP_HREF}
            target="_blank"
            rel="noreferrer noopener"
            className="text-sky-400 underline-offset-4 hover:text-sky-300 hover:underline"
          >
            T1.7 follow-up
          </Link>
          .
        </p>
      ) : null}

      <div className="-mx-1 mt-4 overflow-x-auto">
        <table className="w-full min-w-[min(380px,calc(100vw-40px))] table-fixed border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-zinc-800/90 text-[10px] uppercase tracking-wide text-zinc-500">
              <th className="w-[34%] py-2 pr-2 align-bottom font-semibold">Job</th>
              <th className="hidden w-[18%] py-2 pr-2 align-bottom font-semibold sm:table-cell">Class</th>
              <th className="hidden w-[22%] py-2 pr-2 align-bottom font-semibold md:table-cell">Last run</th>
              <th className="hidden w-[40px] py-2 pr-2 align-bottom font-semibold lg:table-cell">Runs</th>
              <th className="hidden w-[20%] py-2 align-bottom font-semibold sm:table-cell">Next</th>
              <th className="py-2 pl-2 align-bottom font-semibold">Freshness</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => {
              const lastIso =
                typeof job.last_completed_at === "string" && job.last_completed_at.trim() !== ""
                  ? job.last_completed_at.trim()
                  : null;

              const { badge } = schedulerStaleBadgeForJob({
                id: job.id,
                last_completed_at: job.last_completed_at,
                next_run: job.next_run,
              });
              const classPresentation = classificationPresentation(job.classification);

              return (
                <tr key={job.id} className="border-b border-zinc-800/60 align-top">
                  <td className="py-2 pr-2">
                    <div className="font-mono text-[11px] leading-snug break-all text-zinc-200">{job.id}</div>
                    <div className="mt-2 sm:hidden">
                      <StatusBadge status={classPresentation.status} size="sm" className="normal-case">
                        {classPresentation.label}
                      </StatusBadge>
                    </div>
                    <dl className="mt-2 space-y-1 text-[11px] text-zinc-500 md:hidden">
                      <div>
                        <dt className="inline font-medium text-zinc-600">Last:</dt>
                        <dd className="inline text-zinc-400">
                          {" "}
                          {lastIso !== null ? relativeLabelFromIso(lastIso) : "—"}
                        </dd>
                      </div>
                      <div>
                        <dt className="inline font-medium text-zinc-600">Next:</dt>
                        <dd className="inline text-zinc-400">
                          {" "}
                          {job.next_run != null ? relativeLabelFromIso(job.next_run) : "—"}
                        </dd>
                      </div>
                    </dl>
                  </td>
                  <td className="hidden py-2 pr-2 sm:table-cell">
                    <StatusBadge status={classPresentation.status} size="sm" className="normal-case">
                      {classPresentation.label}
                    </StatusBadge>
                  </td>
                  <td className="hidden md:table-cell">
                    <div className="text-zinc-300">{lastIso !== null ? relativeLabelFromIso(lastIso) : "—"}</div>
                    {lastIso === null ? (
                      <p className="mt-0.5 font-mono text-[10px] text-zinc-600">Not exported yet</p>
                    ) : null}
                  </td>
                  <td className="hidden py-2 pr-2 text-zinc-300 lg:table-cell">
                    {typeof job.run_count === "number" ? job.run_count : "—"}
                  </td>
                  <td className="hidden py-2 font-mono text-[11px] text-zinc-400 sm:table-cell">
                    {job.next_run !== null ? relativeLabelFromIso(job.next_run) : "—"}
                  </td>
                  <td className="py-2 pl-2 align-top">
                    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-2">
                      <RowFreshnessIndicators job={job} />
                      <StatusBadge status={staleBadgeStatus(badge)} size="sm" className="normal-case">
                        {badge === "ok" ? "OK" : badge === "warn" ? "Review" : "Stale"}
                      </StatusBadge>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
