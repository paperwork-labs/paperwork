"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";

import { StatusBadge } from "@/components/admin/hq/StatusBadge";
import { StatusDot } from "@/components/admin/hq/StatusDot";
import { useBrainSchedulers } from "@/hooks/useBrainSchedulers";
import { evaluateSchedulerRowHealth, relativeLabelFromIso } from "@/lib/brain-schedulers-freshness";
import type { BrainSchedulerJob } from "@/types/brain-schedulers";
import { Button } from "@paperwork-labs/ui";

/** Master plan tracker for T1.7 backend follow-up (SchedulerRun export + Studio wiring). */
const T1_7_FOLLOWUP_HREF =
  "https://github.com/paperwork-labs/paperwork/blob/main/docs/plans/PAPERWORK_LABS_2026Q2_MASTER_PLAN.md";

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
  const lastIso =
    typeof job.last_completed_at === "string" && job.last_completed_at.trim() !== ""
      ? job.last_completed_at.trim()
      : null;
  const { healthy, gate } = evaluateSchedulerRowHealth({
    jobId: job.id,
    lastCompletedAt: job.last_completed_at,
    nextRun: job.next_run,
  });

  let statusLabel: string;
  if (lastIso !== null) {
    statusLabel = healthy ? "Within last-run SLA" : "Stale (last-run)";
  } else if (!job.next_run) {
    statusLabel = "Unknown (no schedule)";
  } else if (healthy) {
    statusLabel =
      gate === "next_run" ? "Next run scheduled" : "Within last-run SLA";
  } else {
    statusLabel = gate === "next_run" ? "Next run overdue" : "Stale (last-run)";
  }

  const dotBad = gate === "next_run";

  return (
    <span className="flex items-center gap-2">
      {healthy ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-[var(--status-success)]" aria-hidden />
      ) : dotBad ? (
        <span className="relative inline-flex h-5 w-5 items-center justify-center" aria-hidden>
          <span className="absolute inline-flex h-3 w-3 motion-safe:animate-ping rounded-full bg-[var(--status-danger)] opacity-40" />
          <StatusDot status="danger" size="sm" pulse={false} className="relative" />
        </span>
      ) : (
        <AlertTriangle className="h-4 w-4 shrink-0 text-[var(--status-warning)]" aria-hidden />
      )}
      <span className="text-xs text-zinc-400">{statusLabel}</span>
    </span>
  );
}

export function BrainSchedulersCard() {
  const { loading, data, error, retry } = useBrainSchedulers();

  if (loading) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-6 ring-1 ring-zinc-800">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              Brain Schedulers
            </p>
            <p className="mt-1 font-mono text-xs text-zinc-500">
              Proxied Brain <span className="text-zinc-400">GET /internal/schedulers</span>
            </p>
          </div>
        </div>
        <BrainSchedulersSkeleton />
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-950 ring-1 ring-zinc-800">
        <div className="rounded-xl border border-[var(--status-danger)]/35 bg-[var(--status-danger-bg)] p-6 ring-1 ring-[var(--status-danger)]/25">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--status-danger)]">
            Brain Schedulers — error
          </p>
          <p className="mt-3 text-sm text-rose-100">{error.message}</p>
          <Button type="button" variant="destructive" size="sm" className="mt-5 min-h-11 px-6" onClick={() => retry()}>
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden />
            Retry
          </Button>
        </div>
      </section>
    );
  }

  if (!data) {
    return null;
  }

  if (data.status === "empty") {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-6 ring-1 ring-zinc-800">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Brain Schedulers</p>
        <div className="mt-3 rounded-lg border border-[var(--status-warning)]/35 bg-[var(--status-warning-bg)] px-3 py-2 text-sm text-[var(--status-warning)]">
          {data.message}
        </div>
        <p className="mt-4 text-xs leading-relaxed text-zinc-400">
          Brain scheduler endpoint is not fully wired until{" "}
          <code className="rounded bg-zinc-900/80 px-1 py-0.5 font-mono text-[11px] text-zinc-300">
            /internal/schedulers
          </code>{" "}
          is reachable plus last-run history lands in Brain —{" "}
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
    <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-6 ring-1 ring-zinc-800">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Brain Schedulers</p>
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
              Next-run view
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
          {/* Thresholds keyed in `brain-schedulers-freshness.ts` for when last-run timestamps export (T1.7-followup). */}
          Registered jobs expose <strong className="text-zinc-300">next firing times</strong>, not authoritative last-run
          history or run totals yet.
          Planned staleness thresholds:{" "}
          <span className="font-mono text-zinc-400">brain_autopilot_dispatcher</span> (5&nbsp;minutes), probe failure
          dispatcher (15&nbsp;minutes), secrets + credential expiry monitors (24&nbsp;hours), unknown jobs (
          60&nbsp;minutes). Wire-up:{" "}
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
        <table className="w-full min-w-[min(340px,calc(100vw-48px))] table-fixed border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-zinc-800/90 text-[10px] uppercase tracking-wide text-zinc-500">
              <th className="w-[42%] py-2 pr-2 align-bottom font-semibold">Job ID</th>
              <th className="hidden w-[26%] py-2 pr-2 align-bottom font-semibold md:table-cell">Last run</th>
              <th className="w-[48px] py-2 pr-2 align-bottom font-semibold lg:w-[72px]">Runs</th>
              <th className="hidden w-[26%] py-2 align-bottom font-semibold sm:table-cell">Next run</th>
              <th className="py-2 pl-2 align-bottom font-semibold">Drift</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => {
              const lastIso =
                typeof job.last_completed_at === "string" && job.last_completed_at.trim() !== ""
                  ? job.last_completed_at.trim()
                  : null;

              const { healthy } = evaluateSchedulerRowHealth({
                jobId: job.id,
                lastCompletedAt: job.last_completed_at,
                nextRun: job.next_run,
              });

              return (
                <tr key={job.id} className="border-b border-zinc-800/60 align-top">
                  <td className="py-2 pr-2">
                    <div className="font-mono text-[11px] leading-snug break-all text-zinc-200">{job.id}</div>
                    <dl className="mt-2 space-y-1 text-[11px] text-zinc-500 md:hidden">
                      <div>
                        <dt className="inline font-medium text-zinc-600">Last run:</dt>
                        <dd className="inline text-zinc-400">
                          {" "}
                          {lastIso !== null ? relativeLabelFromIso(lastIso) : "— (not wired)"}
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
                  <td className="hidden md:table-cell">
                    <div className="text-zinc-300">{lastIso !== null ? relativeLabelFromIso(lastIso) : "—"}</div>
                    {lastIso === null ? (
                      <p className="mt-0.5 font-mono text-[10px] text-zinc-600">Awaiting T1.7-followup export</p>
                    ) : null}
                  </td>
                  <td className="py-2 pr-2 text-zinc-300">
                    {typeof job.run_count === "number" ? job.run_count : "—"}
                  </td>
                  <td className="hidden font-mono py-2 text-[11px] text-zinc-400 sm:table-cell">
                    {job.next_run !== null ? relativeLabelFromIso(job.next_run) : "—"}
                  </td>
                  <td className="py-2 pl-2 align-top">
                    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-2">
                      <RowFreshnessIndicators job={job} />
                      <div className="shrink-0">
                        {healthy ? (
                          <StatusBadge status="success" size="sm">
                            Healthy
                          </StatusBadge>
                        ) : (
                          <StatusBadge status="danger" size="sm">
                            Stale
                          </StatusBadge>
                        )}
                      </div>
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
