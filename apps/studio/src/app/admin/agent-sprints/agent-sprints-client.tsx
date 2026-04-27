"use client";

import { useCallback, useState } from "react";

import type { AgentSprintsTodayPayload } from "@/lib/command-center";

function sourceLink(src: Record<string, unknown>): string | null {
  const u = src.url;
  if (typeof u === "string" && u.startsWith("http")) return u;
  const ref = src.ref;
  if (typeof ref === "string" && ref.startsWith("http")) return ref;
  return null;
}

export default function AgentSprintsClient({
  initial,
  initialError,
}: {
  initial: AgentSprintsTodayPayload | null;
  initialError: string | null;
}) {
  const [data, setData] = useState<AgentSprintsTodayPayload | null>(initial);
  const [err, setErr] = useState<string | null>(initialError);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch("/api/admin/agent-sprints/today", { cache: "no-store" });
      const j = await res.json();
      if (!res.ok || !j?.ok) {
        setErr(j?.error ?? `HTTP ${res.status}`);
        return;
      }
      setData(j.data as AgentSprintsTodayPayload);
    } catch {
      setErr("Network error");
    } finally {
      setBusy(false);
    }
  }, []);

  const regenerate = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch("/api/admin/agent-sprints/regenerate", { method: "POST" });
      const j = await res.json();
      if (!res.ok || j?.success === false) {
        setErr(j?.error ?? j?.detail ?? `HTTP ${res.status}`);
        return;
      }
      await refresh();
    } catch {
      setErr("Regenerate failed");
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  const metrics = data?.metrics;

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">Cheap-agent sprints</h1>
        <p className="max-w-3xl text-sm leading-relaxed text-zinc-400">
          Brain buckets rule-generated tasks into ~1-day sprints (parallelism-aware). Review here before
          dispatching agents — automation does not launch workers in this version.
        </p>
      </header>

      {err ? (
        <div className="rounded-lg border border-amber-900/60 bg-amber-950/40 px-4 py-3 text-sm text-amber-200">
          {err}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={refresh}
          disabled={busy}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-medium text-zinc-100 transition hover:bg-zinc-800 disabled:opacity-50"
        >
          Refresh
        </button>
        <button
          type="button"
          onClick={regenerate}
          disabled={busy}
          className="rounded-lg border border-indigo-800 bg-indigo-950/50 px-4 py-2 text-sm font-medium text-indigo-100 transition hover:bg-indigo-900/50 disabled:opacity-50"
        >
          Regenerate now
        </button>
      </div>

      {metrics ? (
        <section className="grid gap-4 sm:grid-cols-3">
          <MetricCard label="Tasks generated today" value={String(metrics.tasks_generated_today)} />
          <MetricCard label="Sprints today" value={String(metrics.sprints_generated_today)} />
          <MetricCard label="Avg sprint size" value={metrics.average_sprint_size.toFixed(1)} />
        </section>
      ) : null}

      {data?.generated_through ? (
        <p className="text-xs text-zinc-500">Server clock through {data.generated_through}</p>
      ) : null}

      <section className="space-y-6">
        {data?.sprints?.length ? (
          data.sprints.map((sp) => (
            <article
              key={sp.sprint_id}
              className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-5 shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-800/60 pb-4">
                <div>
                  <h2 className="font-mono text-sm text-zinc-300">{sp.sprint_id}</h2>
                  <p className="mt-1 text-xs text-zinc-500">
                    {sp.generated_at} · {sp.timezone}
                  </p>
                </div>
                <div className="text-right text-sm text-zinc-400">
                  <div>
                    <span className="text-zinc-500">Total minutes:</span> {sp.total_minutes}
                  </div>
                  <div>
                    <span className="text-zinc-500">Parallelism score:</span> {sp.parallelizability_score}
                  </div>
                  <div>
                    <span className="text-zinc-500">Status:</span> {sp.status}
                  </div>
                </div>
                <button
                  type="button"
                  disabled
                  title="TODO: wire POST /internal/agent-sprints/dispatch (future PR)"
                  className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-500"
                >
                  Dispatch all (stub)
                </button>
              </div>
              <ul className="mt-4 space-y-4">
                {sp.tasks.map((t) => (
                  <li
                    key={t.task_id}
                    className="rounded-lg border border-zinc-800/60 bg-zinc-950/30 p-4"
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <h3 className="font-medium text-zinc-100">{t.title}</h3>
                      <span className="font-mono text-xs text-zinc-500">{t.task_id}</span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-400">
                      <span className="rounded bg-zinc-800/80 px-2 py-0.5">{t.estimated_minutes} min</span>
                      <span className="rounded bg-zinc-800/80 px-2 py-0.5">{t.agent_type}</span>
                      <span className="rounded bg-zinc-800/80 px-2 py-0.5">{t.model_hint}</span>
                      {sourceLink(t.source) ? (
                        <a
                          href={sourceLink(t.source)!}
                          target="_blank"
                          rel="noreferrer"
                          className="text-indigo-400 underline-offset-2 hover:underline"
                        >
                          Source
                        </a>
                      ) : (
                        <span className="text-zinc-600">
                          {String(t.source?.kind ?? "?")}: {String(t.source?.ref ?? "")}
                        </span>
                      )}
                    </div>
                    {t.depends_on.length ? (
                      <p className="mt-2 text-xs text-zinc-500">
                        Depends on: {t.depends_on.join(" → ")}
                      </p>
                    ) : null}
                    <details className="mt-3 text-sm text-zinc-300">
                      <summary className="cursor-pointer select-none text-zinc-400 hover:text-zinc-200">
                        Scope
                      </summary>
                      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-zinc-950/50 p-3 text-xs leading-relaxed text-zinc-400">
                        {t.scope}
                      </pre>
                    </details>
                  </li>
                ))}
              </ul>
            </article>
          ))
        ) : (
          <p className="text-sm text-zinc-500">No sprints in the last 24 hours. Try Regenerate now.</p>
        )}
      </section>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-zinc-100">{value}</p>
    </div>
  );
}
