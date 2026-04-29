"use client";

import { useEffect, useState } from "react";

import { fetchSelfImprovementJson } from "../lib/fetch-self-improvement";

type JobRow = {
  id: string;
  name: string;
  next_run: string | null;
  trigger: string;
  classification: string;
  last_run_at: string | null;
  last_result: string | null;
  last_error_preview: string | null;
};

type AutoPayload = {
  scheduler_running: boolean;
  jobs: JobRow[];
  note?: string | null;
};

export function AutomationStateTab() {
  const [data, setData] = useState<AutoPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetchSelfImprovementJson<AutoPayload>("automation-state");
      if (cancelled) return;
      if (res.success && res.data) setData(res.data);
      else setErr(res.error ?? "Failed to load automation state");
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (err) {
    return (
      <p className="text-sm text-rose-200" role="alert">
        {err}
      </p>
    );
  }
  if (!data) return <p className="text-sm text-zinc-500">Loading…</p>;

  if (!data.scheduler_running || data.jobs.length === 0) {
    return (
      <div className="space-y-2 text-sm text-zinc-400" data-testid="automation-empty">
        <p>{data.note ?? "Scheduler has no registered jobs in this process."}</p>
        <p className="text-xs text-zinc-600">
          When <code className="text-zinc-500">BRAIN_SCHEDULER_ENABLED=true</code>, Brain registers APScheduler jobs
          from <code className="text-zinc-500">app/schedulers/__init__.py</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="automation-tab">
      <table className="w-full min-w-[640px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-xs uppercase tracking-wide text-zinc-500">
            <th className="py-2 pr-3">Job</th>
            <th className="py-2 pr-3">Schedule</th>
            <th className="py-2 pr-3">Last run</th>
            <th className="py-2 pr-3">Result</th>
            <th className="py-2 pr-3">Next run</th>
          </tr>
        </thead>
        <tbody>
          {data.jobs.map((j) => (
            <tr key={j.id} className="border-b border-zinc-800/80">
              <td className="py-2 pr-3 align-top">
                <div className="font-mono text-xs text-zinc-300">{j.id}</div>
                <div className="text-xs text-zinc-500">{j.name}</div>
              </td>
              <td className="max-w-xs py-2 pr-3 align-top text-xs text-zinc-400">{j.trigger}</td>
              <td className="py-2 pr-3 align-top text-xs text-zinc-400">{j.last_run_at ?? "—"}</td>
              <td className="py-2 pr-3 align-top text-xs">
                {j.last_result ? (
                  <span
                    className={
                      j.last_result === "success" ? "text-emerald-400" : "text-amber-200"
                    }
                  >
                    {j.last_result}
                  </span>
                ) : (
                  "—"
                )}
                {j.last_error_preview ? (
                  <p className="mt-1 line-clamp-2 text-[10px] text-rose-300/90">{j.last_error_preview}</p>
                ) : null}
              </td>
              <td className="py-2 pr-3 align-top text-xs text-zinc-400">{j.next_run ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
