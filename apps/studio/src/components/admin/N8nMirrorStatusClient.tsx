"use client";

import { useCallback, useEffect, useState } from "react";
import type { N8nMirrorSchedulerStatus } from "@/lib/command-center";
import {
  N8N_MIRROR_CUTOVER_JOB_IDS,
  N8N_MIRROR_SPEC_META,
} from "@/lib/n8n-mirror-spec-meta";

const POLL_MS = 30_000;

type ApiOk = { ok: true; status: N8nMirrorSchedulerStatus; checkedAt: string };
type ApiErr = { ok: false; status: null; error?: string; checkedAt: string };

function formatLastRun(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
      timeZone: "UTC",
      timeZoneName: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function runStatusBadge(lastStatus: string | null) {
  if (lastStatus === "success")
    return (
      <span className="inline-flex items-center rounded-md border border-emerald-800/50 bg-emerald-950/40 px-2 py-0.5 text-xs font-medium text-emerald-300">
        success
      </span>
    );
  if (lastStatus === "error")
    return (
      <span className="inline-flex items-center rounded-md border border-rose-800/50 bg-rose-950/40 px-2 py-0.5 text-xs font-medium text-rose-300">
        error
      </span>
    );
  if (lastStatus === "skipped")
    return (
      <span className="inline-flex items-center rounded-md border border-amber-800/50 bg-amber-950/40 px-2 py-0.5 text-xs font-medium text-amber-200">
        skipped
      </span>
    );
  return (
    <span className="inline-flex items-center rounded-md border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-xs text-zinc-500">
      no runs
    </span>
  );
}

function boolChip(
  value: boolean,
  labels: { on: string; off: string },
  onClass: string,
  offClass: string,
) {
  return (
    <span
      className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${
        value ? onClass : offClass
      }`}
    >
      {value ? labels.on : labels.off}
    </span>
  );
}

/**
 * Heuristic: for the two `BRAIN_OWNS_*` job ids, when the global mirror default is on
 * but this shadow job is not registered, Brain typically cut over (shadow suppressed).
 * Per-job `SCHEDULER_N8N_MIRROR_*=false` can also produce the same pattern — use DB/logs to confirm.
 */
function brainOwnsHeuristic(
  jobId: string,
  globalEnabled: boolean,
  shadowEnabled: boolean,
): { label: string; tone: "cutover" | "shadow" | "na" } {
  if (!N8N_MIRROR_CUTOVER_JOB_IDS.has(jobId)) {
    return { label: "n/a", tone: "na" };
  }
  if (!globalEnabled) {
    return { label: "mirror off", tone: "na" };
  }
  if (shadowEnabled) {
    return { label: "n8n shadow", tone: "shadow" };
  }
  return { label: "Brain path", tone: "cutover" };
}

export default function N8nMirrorStatusClient({
  initialStatus,
  initialCheckedAt,
}: {
  initialStatus: N8nMirrorSchedulerStatus | null;
  initialCheckedAt: string;
}) {
  const [status, setStatus] = useState<N8nMirrorSchedulerStatus | null>(initialStatus);
  const [checkedAt, setCheckedAt] = useState(initialCheckedAt);
  const [error, setError] = useState<string | null>(
    !initialStatus ? "Brain not wired (set BRAIN_API_URL + BRAIN_API_SECRET) or status unavailable." : null,
  );

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/n8n-mirror/status", { cache: "no-store" });
      const data = (await res.json()) as ApiOk | ApiErr;
      setCheckedAt(data.checkedAt);
      if (data.ok && data.status) {
        setStatus(data.status);
        setError(null);
        return;
      }
      setError("error" in data && data.error ? data.error : `HTTP ${res.status}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    }
  }, []);

  useEffect(() => {
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [refresh]);

  const perJob = status?.per_job ?? [];
  const globalEnabled = status?.global_enabled ?? false;
  const mirrorRetired = Boolean(status?.retired);
  const total = perJob.length;
  const shadowOn = perJob.filter((j) => j.enabled).length;
  const cutoverHints = N8N_MIRROR_CUTOVER_JOB_IDS;
  let cutoverComplete = 0;
  let pendingCutover = 0;
  for (const j of perJob) {
    if (!cutoverHints.has(j.key)) continue;
    if (!globalEnabled) continue;
    if (j.enabled) pendingCutover += 1;
    else cutoverComplete += 1;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          n8n cron mirror
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Legacy view: n8n shadow APScheduler jobs were retired after Track K (Brain owns crons
          permanently). Auto-refresh every {POLL_MS / 1000}s. Source:{" "}
          <span className="text-zinc-500">GET</span>{" "}
          <code className="text-zinc-500">/api/v1/admin/scheduler/n8n-mirror/status</code>
        </p>
      </div>

      {mirrorRetired && status?.message ? (
        <div className="rounded-lg border border-emerald-800/40 bg-emerald-950/25 px-4 py-3 text-sm text-emerald-100">
          {status.message}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-amber-800/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
          {error}
        </div>
      ) : null}

      {status ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Jobs</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-zinc-100">{total}</p>
            <p className="text-sm text-zinc-500">mirrored workflow ids</p>
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Shadow on</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-emerald-300">{shadowOn}</p>
            <p className="text-sm text-zinc-500">APScheduler n8n shadow jobs registered</p>
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Cutover (T1.2 / T1.3)</p>
            <p className="mt-1 text-lg tabular-nums text-zinc-100">
              <span className="text-emerald-300">{cutoverComplete}</span>
              <span className="text-zinc-600"> / </span>
              <span className="text-amber-200">{pendingCutover}</span>
            </p>
            <p className="text-sm text-zinc-500">
              Brain path (no shadow row) / still shadowing — daily + infra only; heuristic when global
              mirror is on
            </p>
          </div>
        </div>
      ) : null}

      <p className="text-xs text-zinc-500">
        Last fetch: {formatLastRun(checkedAt)}
      </p>

      {status ? (
        <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40">
          <table className="w-full min-w-[960px] text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-800/80 text-xs uppercase tracking-wide text-zinc-500">
                <th className="px-3 py-3 font-medium">Job ID</th>
                <th className="px-3 py-3 font-medium">n8n workflow</th>
                <th className="px-3 py-3 font-medium">Schedule</th>
                <th className="px-3 py-3 font-medium">Shadow</th>
                <th className="px-3 py-3 font-medium">Brain owns*</th>
                <th className="px-3 py-3 font-medium">Last run (UTC)</th>
                <th className="px-3 py-3 font-medium">24h ok</th>
                <th className="px-3 py-3 font-medium">24h err</th>
                <th className="px-3 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 text-zinc-200">
              {perJob.map((row) => {
                const meta = N8N_MIRROR_SPEC_META[row.key];
                const bo = brainOwnsHeuristic(row.key, globalEnabled, row.enabled);
                return (
                  <tr key={row.key} className="hover:bg-zinc-800/30">
                    <td className="px-3 py-2.5 font-mono text-xs text-zinc-300">{row.key}</td>
                    <td className="px-3 py-2.5 text-zinc-300">
                      {meta?.n8n_workflow_name ?? "—"}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs text-zinc-400">
                      {meta ? `${meta.schedule} (${meta.trigger_type})` : "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      {boolChip(
                        row.enabled,
                        { on: "on", off: "off" },
                        "border-emerald-800/50 bg-emerald-950/40 text-emerald-200",
                        "border-zinc-700 bg-zinc-900 text-zinc-500",
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      {bo.tone === "cutover" ? (
                        <span
                          className="inline-flex rounded-md border border-emerald-800/50 bg-emerald-950/40 px-2 py-0.5 text-xs font-medium text-emerald-200"
                          title="Shadow not registered while global mirror default is on — usual when BRAIN_OWNS_* cutover is active"
                        >
                          {bo.label}
                        </span>
                      ) : bo.tone === "shadow" ? (
                        <span className="inline-flex rounded-md border border-zinc-600 bg-zinc-800/60 px-2 py-0.5 text-xs text-zinc-400">
                          {bo.label}
                        </span>
                      ) : (
                        <span className="text-xs text-zinc-600">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-zinc-400">{formatLastRun(row.last_run)}</td>
                    <td className="px-3 py-2.5 tabular-nums text-zinc-300">
                      {row.success_count_24h}
                    </td>
                    <td className="px-3 py-2.5 tabular-nums text-zinc-300">{row.error_count_24h}</td>
                    <td className="px-3 py-2.5">{runStatusBadge(row.last_status)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      <p className="text-xs text-zinc-600">
        * <strong className="text-zinc-500">Brain owns</strong> applies to daily + infra cutover
        job ids. Green “Brain path” is a best-effort signal when the shadow row is off while
        <code className="mx-1">SCHEDULER_N8N_MIRROR_ENABLED</code> is true; confirm with Brain env
        and <code className="mx-1">agent_scheduler_runs</code> during migrations.
      </p>
    </div>
  );
}
