"use client";

import type { ReactNode } from "react";
import { useId, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight } from "lucide-react";

import type { HeroRollup, ProductHealthBrainState } from "@/lib/product-health-brain";

function pillClass(rollup: HeroRollup): string {
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

function pillLabel(rollup: HeroRollup): string {
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

function HealthSparkline({ points }: { points: { t: string; pass: boolean }[] }) {
  if (points.length === 0) {
    return (
      <p className="text-xs text-zinc-500">No probe trend points in the last 24h.</p>
    );
  }
  const w = 120;
  const h = 32;
  const pad = 2;
  const n = points.length;
  const step = n > 1 ? (w - pad * 2) / (n - 1) : 0;
  const ys = points.map((p, i) => {
    const x = n === 1 ? w / 2 : pad + i * step;
    const y = p.pass ? pad + 4 : h - pad - 4;
    return `${x},${y}`;
  });
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      className="text-zinc-500"
      aria-hidden
    >
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={ys.join(" ")}
      />
      {points.map((p, i) => {
        const x = n === 1 ? w / 2 : pad + i * step;
        const y = p.pass ? pad + 4 : h - pad - 4;
        return (
          <circle
            key={`${p.t}-${i}`}
            cx={x}
            cy={y}
            r={2}
            className={p.pass ? "fill-emerald-400" : "fill-red-400"}
          />
        );
      })}
    </svg>
  );
}

function Card({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-zinc-800/90 bg-zinc-950/50 p-4 shadow-sm shadow-black/20">
      <h2 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">{title}</h2>
      <div className="mt-3 space-y-2 text-sm text-zinc-300">{children}</div>
    </section>
  );
}

export type ProductHealthShellProps = {
  productName: string;
  state: ProductHealthBrainState;
  heroRollup: HeroRollup;
  narrative: string;
  lastCheckedLabel: string | null;
};

export function ProductHealthShell({
  productName,
  state,
  heroRollup,
  narrative,
  lastCheckedLabel,
}: ProductHealthShellProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <div className="space-y-6">
      {state.brainDataPlaneError ? (
        <div
          role="alert"
          className="rounded-xl border border-red-500/40 bg-red-950/30 px-4 py-3 text-sm text-red-100"
          data-testid="brain-api-error-banner"
        >
          <p className="font-medium">Brain API unreachable — check BRAIN_API_URL / BRAIN_API_SECRET</p>
          <p className="mt-1 text-xs text-red-200/90">{state.brainDataPlaneError}</p>
        </div>
      ) : null}

      {!state.brainDataPlaneError && state.deployTelemetryErrors.length ? (
        <div
          role="status"
          className="rounded-xl border border-amber-500/35 bg-amber-950/20 px-4 py-3 text-xs text-amber-100"
        >
          <p className="font-medium text-amber-200">Deploy quota telemetry partial</p>
          <ul className="mt-1 list-inside list-disc text-amber-100/90">
            {state.deployTelemetryErrors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <header className="space-y-3">
        <nav aria-label="Breadcrumb" className="text-xs text-zinc-400">
          <ol className="flex flex-wrap items-center gap-1.5">
            <li>
              <Link href="/admin" className="text-zinc-300 hover:text-zinc-100">
                Admin
              </Link>
            </li>
            <span className="text-zinc-600">/</span>
            <li>
              <Link href="/admin/products" className="text-zinc-300 hover:text-zinc-100">
                Products
              </Link>
            </li>
            <span className="text-zinc-600">/</span>
            <li>
              <Link href={`/admin/products/${state.slug}`} className="text-zinc-300 hover:text-zinc-100">
                {productName}
              </Link>
            </li>
            <span className="text-zinc-600">/</span>
            <li className="font-medium text-zinc-200">Health</li>
          </ol>
        </nav>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">Production health</h1>
            <p className="max-w-3xl text-sm text-zinc-400">{narrative}</p>
            {lastCheckedLabel ? (
              <p className="text-xs text-zinc-500">Last checked (probes): {lastCheckedLabel}</p>
            ) : null}
          </div>
          <span
            data-testid="health-status-pill"
            className={`inline-flex shrink-0 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${pillClass(heroRollup)}`}
          >
            {pillLabel(heroRollup)}
          </span>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="UX Probes">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <HealthSparkline points={state.probeResultsSpark} />
          </div>
          {state.cujRows.length === 0 ? (
            <p className="text-xs text-zinc-500">No per-CUJ rows in the latest health payload.</p>
          ) : (
            <ul className="mt-2 space-y-1.5 text-xs">
              {state.cujRows.map((r) => (
                <li
                  key={r.id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800/80 bg-zinc-900/40 px-2 py-1.5"
                >
                  <span className="truncate text-zinc-200">{r.name}</span>
                  <span
                    className={
                      r.status === "pass"
                        ? "shrink-0 text-emerald-400"
                        : r.status === "fail"
                          ? "shrink-0 text-red-400"
                          : "shrink-0 text-zinc-500"
                    }
                  >
                    {r.status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Errors (24h)">
          {state.errorTotal24h === null ? (
            <p className="text-xs text-zinc-500">Error aggregate unavailable.</p>
          ) : (
            <p className="text-lg font-semibold tabular-nums text-zinc-100">{state.errorTotal24h}</p>
          )}
          <p className="text-[11px] uppercase tracking-wide text-zinc-500">Top fingerprints</p>
          {state.errorFingerprints.length === 0 ? (
            <p className="text-xs text-zinc-500">None in window.</p>
          ) : (
            <ul className="space-y-1.5 font-mono text-[11px]">
              {state.errorFingerprints.map((f) => (
                <li key={f.fingerprint} className="rounded border border-zinc-800/80 bg-zinc-900/40 px-2 py-1">
                  <div className="flex justify-between gap-2 text-zinc-300">
                    <span className="truncate">{f.fingerprint}</span>
                    <span className="shrink-0 tabular-nums text-zinc-400">{f.count}</span>
                  </div>
                  {f.firstSeen ? (
                    <p className="mt-0.5 text-[10px] text-zinc-500">first {f.firstSeen}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Deploys">
          <div className="space-y-3 text-xs">
            <div>
              <p className="text-[10px] font-semibold uppercase text-zinc-500">Vercel (quota)</p>
              {state.vercelDeploy ? (
                <dl className="mt-1 space-y-0.5 text-zinc-300">
                  <div className="flex justify-between gap-2">
                    <dt>Project</dt>
                    <dd className="text-right">{state.vercelDeploy.projectName}</dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt>24h deploys</dt>
                    <dd className="tabular-nums text-right">
                      {state.vercelDeploy.deployCount24h ?? "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt>Snapshot</dt>
                    <dd className="text-right text-zinc-400">
                      {state.vercelDeploy.snapshotAt ?? "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt>Commit SHA</dt>
                    <dd className="font-mono text-right text-zinc-400">
                      {state.vercelDeploy.commitSha ?? "— (not in quota payload)"}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="text-zinc-500">No Vercel row.</p>
              )}
            </div>
            <div className="border-t border-zinc-800/80 pt-2">
              <p className="text-[10px] font-semibold uppercase text-zinc-500">Render (pipeline)</p>
              {state.renderDeploy ? (
                <dl className="mt-1 space-y-0.5 text-zinc-300">
                  <div className="flex justify-between gap-2">
                    <dt>Service</dt>
                    <dd className="text-right">{state.renderDeploy.serviceName}</dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt>Approx build min</dt>
                    <dd className="tabular-nums text-right">
                      {state.renderDeploy.approxMinutes ?? "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt>Snapshot</dt>
                    <dd className="text-right text-zinc-400">
                      {state.renderDeploy.snapshotRecordedAt ?? "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt>Pipeline usage</dt>
                    <dd className="tabular-nums text-right">
                      {state.renderDeploy.pipelineUsageRatio != null
                        ? `${(state.renderDeploy.pipelineUsageRatio * 100).toFixed(1)}%`
                        : "—"}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="text-zinc-500">No Render snapshot.</p>
              )}
            </div>
          </div>
        </Card>

        <Card title="Visual diffs">
          <p className="text-sm text-zinc-400">Coming in PR-PB2</p>
          <p className="text-xs text-zinc-600">
            Percy / screenshot diff status will appear here. No placeholder scores are shown.
          </p>
        </Card>
      </div>

      <section className="rounded-xl border border-zinc-800/90 bg-zinc-950/50 p-4">
        <button
          type="button"
          id={`${panelId}-btn`}
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center gap-2 text-left text-sm font-medium text-zinc-200 hover:text-zinc-50"
        >
          {open ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
          )}
          Last 20 probe runs
        </button>
        {open ? (
          <ul id={panelId} className="mt-3 space-y-2 border-t border-zinc-800/80 pt-3 text-xs">
            {state.probeRuns.length === 0 ? (
              <li className="text-zinc-500">No probe runs in the last 24h.</li>
            ) : (
              state.probeRuns.map((r, i) => (
                <li
                  key={`${r.at}-${i}`}
                  className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-zinc-800/60 bg-zinc-900/30 px-2 py-1.5"
                >
                  <span className="font-mono text-zinc-500">{r.at}</span>
                  <span className="text-zinc-300">{r.assertion}</span>
                  <span
                    className={
                      r.status === "pass"
                        ? "text-emerald-400"
                        : r.status === "fail"
                          ? "text-red-400"
                          : "text-zinc-500"
                    }
                  >
                    {r.status}
                  </span>
                </li>
              ))
            )}
          </ul>
        ) : null}
      </section>
    </div>
  );
}
