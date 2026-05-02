"use client";

import type { HeroRollup, ProductHealthBrainState } from "@/lib/product-health-brain";

function rollupPillClass(rollup: HeroRollup): string {
  switch (rollup) {
    case "healthy":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
    case "degraded":
      return "border-amber-500/40 bg-amber-500/10 text-amber-200";
    case "down":
      return "border-red-500/45 bg-red-500/10 text-red-200";
    default:
      return "border-zinc-600 bg-zinc-800/80 text-zinc-300";
  }
}

function rollupLabel(rollup: HeroRollup): string {
  switch (rollup) {
    case "healthy":
      return "Healthy";
    case "degraded":
      return "Degraded";
    case "down":
      return "Down";
    default:
      return "Unknown";
  }
}

function lastDeployedLabel(state: ProductHealthBrainState): string | null {
  const v = state.vercelDeploy?.snapshotAt;
  const r = state.renderDeploy?.snapshotRecordedAt;
  if (v && r) return `${v} (Vercel) · ${r} (Render)`;
  if (v) return v;
  if (r) return r;
  return null;
}

export function ProductHubHealthPanel({
  state,
  heroRollup,
  narrative,
}: {
  state: ProductHealthBrainState;
  heroRollup: HeroRollup;
  narrative: string;
}) {
  const deployed = lastDeployedLabel(state);

  return (
    <div className="space-y-6" data-testid="product-hub-health-panel">
      {state.brainDataPlaneError ? (
        <div
          role="alert"
          className="rounded-xl border border-red-500/40 bg-red-950/30 px-4 py-3 text-sm text-red-100"
        >
          <p className="font-medium">Brain API error — health probes may be stale</p>
          <p className="mt-1 text-xs text-red-200/90">{state.brainDataPlaneError}</p>
        </div>
      ) : null}

      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-4">
        <div className="min-w-0 space-y-2">
          <h2 className="text-sm font-semibold text-zinc-200">Production health</h2>
          <p className="max-w-2xl text-sm text-zinc-400">{narrative}</p>
          {deployed ? (
            <p className="text-xs text-zinc-500">
              <span className="font-medium text-zinc-400">Last deploy snapshot: </span>
              {deployed}
            </p>
          ) : (
            <p className="text-xs text-zinc-500">No deploy telemetry timestamp yet.</p>
          )}
        </div>
        <span
          className={`inline-flex shrink-0 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${rollupPillClass(heroRollup)}`}
        >
          {rollupLabel(heroRollup)}
        </span>
      </div>

      <section className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-4">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
          CUJ probes
        </h3>
        {state.cujRows.length === 0 ? (
          <p className="mt-3 text-sm text-zinc-500">No CUJ rows in the latest health payload.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {state.cujRows.map((r) => (
              <li
                key={r.id}
                className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800/70 bg-zinc-900/45 px-3 py-2 text-sm"
              >
                <span className="truncate text-zinc-200">{r.name}</span>
                <span
                  className={
                    r.status === "pass"
                      ? "shrink-0 text-[var(--status-success)]"
                      : r.status === "fail"
                        ? "shrink-0 text-[var(--status-danger)]"
                        : "shrink-0 text-zinc-500"
                  }
                >
                  {r.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-4">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
          Deploy status (infra)
        </h3>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <div className="text-sm text-zinc-300">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">Vercel</p>
            {state.vercelDeploy ? (
              <dl className="mt-2 space-y-1 text-xs">
                <div className="flex justify-between gap-2">
                  <dt className="text-zinc-500">Project</dt>
                  <dd>{state.vercelDeploy.projectName}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-zinc-500">24h deploys</dt>
                  <dd className="tabular-nums">{state.vercelDeploy.deployCount24h ?? "—"}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-zinc-500">Status</dt>
                  <dd>{state.vercelDeploy.statusLabel}</dd>
                </div>
              </dl>
            ) : (
              <p className="mt-2 text-xs text-zinc-500">No Vercel quota row for this product.</p>
            )}
          </div>
          <div className="text-sm text-zinc-300">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">Render</p>
            {state.renderDeploy ? (
              <dl className="mt-2 space-y-1 text-xs">
                <div className="flex justify-between gap-2">
                  <dt className="text-zinc-500">Service</dt>
                  <dd>{state.renderDeploy.serviceName}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-zinc-500">Pipeline</dt>
                  <dd>{state.renderDeploy.statusLabel}</dd>
                </div>
              </dl>
            ) : (
              <p className="mt-2 text-xs text-zinc-500">No Render snapshot.</p>
            )}
          </div>
        </div>
        {state.deployTelemetryErrors.length ? (
          <ul className="mt-3 list-inside list-disc text-xs text-amber-200/90">
            {state.deployTelemetryErrors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-4">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
          Uptime & deploy clock
        </h3>
        {(() => {
          const spark = state.probeResultsSpark;
          const passed = spark.filter((x) => x.pass).length;
          const pct = spark.length ? Math.round((100 * passed) / spark.length) : null;
          return (
            <div className="mt-3 space-y-2 text-sm text-zinc-300">
              {spark.length === 0 ? (
                <p className="text-zinc-500">No command-center probe spark data for this product yet.</p>
              ) : (
                <p>
                  <span className="font-medium text-zinc-200">{passed}</span>
                  <span className="text-zinc-500"> / {spark.length} recent probe ticks passing</span>
                  {pct !== null ? (
                    <span className="text-zinc-500"> ({pct}% — indicative, not contractual uptime)</span>
                  ) : null}
                </p>
              )}
              <p className="text-xs text-zinc-500">
                Last production deploy time: <span className="text-zinc-400">placeholder</span> — wire
                Vercel deployment finishedAt in a follow-up.
              </p>
            </div>
          );
        })()}
      </section>
    </div>
  );
}
