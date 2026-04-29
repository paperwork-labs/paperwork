"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  RefreshCw,
  ExternalLink,
  Server,
  Globe,
  Database,
  HardDrive,
  Cpu,
  Radio,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Layers,
  ScrollText,
} from "lucide-react";
import { motion } from "framer-motion";
import type { PlatformHealthSummary } from "@/lib/infra-types";
import QuotaGitHubActionsPanel from "./quota-github-actions-panel";
import QuotaRenderPanel from "./quota-render-panel";
import QuotaVercelPanel from "./quota-vercel-panel";
import LogsTab from "./_tabs/logs-tab";

type InfraService = {
  service: string;
  category: "core" | "frontend" | "ops" | "data" | "cache" | "hosting";
  configured: boolean;
  healthy: boolean;
  detail: string;
  latencyMs: number | null;
  dashboardUrl: string | null;
  consoleUrl?: string | null;
  probeKind?: "standard" | "render" | "vercel";
  platformType?: string;
  stateLabel?: "live" | "building" | "failed" | "suspended";
  deployState?: string;
  commitSha?: string | null;
  lastDeployedAt?: string | null;
  anchorId?: string;
};

const categoryMeta: Record<string, { label: string; icon: typeof Server }> = {
  core: { label: "Core APIs", icon: Server },
  frontend: { label: "Frontends", icon: Globe },
  ops: { label: "Operations", icon: Cpu },
  hosting: { label: "Hosting & Deploys", icon: Globe },
  data: { label: "Data", icon: Database },
  cache: { label: "Cache", icon: HardDrive },
};

function formatTimePT(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
      timeZone: "America/Los_Angeles",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function latencyColor(ms: number | null): string {
  if (ms === null) return "text-zinc-500";
  if (ms < 300) return "text-emerald-400";
  if (ms < 1000) return "text-amber-400";
  return "text-rose-400";
}

function StatusIcon({ healthy, configured }: { healthy: boolean; configured: boolean }) {
  if (!configured) return <AlertTriangle className="h-4 w-4 text-amber-400" />;
  if (healthy) return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
  return <XCircle className="h-4 w-4 text-rose-400" />;
}

function StatusDot({ healthy, configured }: { healthy: boolean; configured: boolean }) {
  if (!configured)
    return <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-400" />;
  if (healthy)
    return (
      <span className="relative inline-block h-2.5 w-2.5">
        <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400 opacity-50" />
        <span className="relative inline-block h-2.5 w-2.5 rounded-full bg-emerald-400" />
      </span>
    );
  return <span className="inline-block h-2.5 w-2.5 rounded-full bg-rose-400" />;
}

function platformStateBadgeClass(st?: string): string {
  if (st === "live" || st === "ready") return "border-emerald-800/50 bg-emerald-950/40 text-emerald-200";
  if (st === "building") return "border-amber-800/50 bg-amber-950/40 text-amber-200";
  if (st === "failed" || st === "suspended")
    return "border-rose-800/50 bg-rose-950/40 text-rose-200";
  return "border-zinc-700 bg-zinc-900/80 text-zinc-300";
}

/** Badge label: provider deploy state (e.g. `build_failed`) when present; else bucket. */
function platformProbeBadgeLabel(svc: InfraService): string {
  const raw = (svc.deployState ?? "").trim();
  if (raw && raw !== "?") return raw.replace(/_/g, " ");
  return svc.stateLabel ?? "?";
}

function platformProbeBadgeTone(svc: InfraService): string {
  const d = (svc.deployState ?? "").toLowerCase();
  if (d === "live" || d === "ready") return "live";
  if (
    d.includes("progress") ||
    d === "building" ||
    d === "queued" ||
    d === "initializing" ||
    d === "deploying" ||
    d === "analyzing"
  )
    return "building";
  if (d === "missing") return "failed";
  if (svc.stateLabel === "suspended") return "suspended";
  if (svc.stateLabel === "failed") return "failed";
  return svc.stateLabel ?? "";
}

function deriveSummary(services: InfraService[], fallback?: PlatformHealthSummary): PlatformHealthSummary {
  if (fallback) return fallback;
  const render = { live: 0, building: 0, failed: 0, suspended: 0, total: 0 };
  const vercel = { live: 0, building: 0, failed: 0, suspended: 0, total: 0 };
  for (const s of services) {
    if (s.probeKind === "render") {
      render.total++;
      const st = s.stateLabel ?? "failed";
      if (st === "live") render.live++;
      else if (st === "building") render.building++;
      else if (st === "failed") render.failed++;
      else render.suspended++;
    } else if (s.probeKind === "vercel") {
      vercel.total++;
      const st = s.stateLabel ?? "failed";
      if (st === "live") vercel.live++;
      else if (st === "building") vercel.building++;
      else if (st === "failed") vercel.failed++;
      else vercel.suspended++;
    }
  }
  return { render, vercel };
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

const AUTO_REFRESH_MS = 30_000;

export default function InfraClient({
  initialServices,
  initialPlatformSummary,
  initialPlatformPartial = [],
  initialCheckedAt,
}: {
  initialServices: InfraService[];
  initialPlatformSummary?: PlatformHealthSummary;
  initialPlatformPartial?: string[];
  initialCheckedAt: string;
}) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeTab = searchParams.get("tab") ?? "services";

  const setTab = (tab: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", tab);
    router.replace(`?${params.toString()}`, { scroll: false });
  };

  const [services, setServices] = useState(initialServices);
  const [platformSummary, setPlatformSummary] = useState<PlatformHealthSummary | undefined>(
    initialPlatformSummary,
  );
  const [platformPartial, setPlatformPartial] = useState<string[]>(initialPlatformPartial);
  const [checkedAt, setCheckedAt] = useState(initialCheckedAt);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [quotaRefresh, setQuotaRefresh] = useState(0);

  const { platformRows, otherRows } = useMemo(() => {
    const platformRowsInner = services.filter(
      (s) => s.probeKind === "render" || s.probeKind === "vercel",
    );
    const otherRowsInner = services.filter(
      (s) => s.probeKind !== "render" && s.probeKind !== "vercel",
    );
    return { platformRows: platformRowsInner, otherRows: otherRowsInner };
  }, [services]);

  const summary = useMemo(
    () => deriveSummary(services, platformSummary),
    [services, platformSummary],
  );

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await fetch("/api/admin/infrastructure");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as {
        services: InfraService[];
        platformSummary?: PlatformHealthSummary;
        platformPartial?: string[];
        checkedAt: string;
      };
      setServices(data.services);
      if (data.platformSummary) setPlatformSummary(data.platformSummary);
      if (data.platformPartial) setPlatformPartial(data.platformPartial);
      setCheckedAt(data.checkedAt);
      setRefreshError(null);
      setQuotaRefresh((q) => q + 1);
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(refresh, AUTO_REFRESH_MS);
    return () => clearInterval(interval);
  }, [autoRefresh, refresh]);

  const healthyCount = otherRows.filter((s) => s.healthy).length;
  const configuredCount = otherRows.filter((s) => s.configured).length;
  const degradedCount = otherRows.filter((s) => s.configured && !s.healthy).length;

  const r = summary.render;
  const v = summary.vercel;
  const hasRender = r.total > 0;
  const hasVercel = v.total > 0;
  const renderLine = hasRender
    ? `Render: ${r.live}/${r.total} live${
        r.building > 0 ? `, ${r.building} building` : ""
      }${r.failed > 0 ? `, ${r.failed} failed` : ""}${r.suspended > 0 ? `, ${r.suspended} suspended` : ""}`
    : "Render: (no API data — set RENDER_API_KEY)";

  const vercelLine = hasVercel
    ? `Vercel: ${v.live}/${v.total} live${v.building > 0 ? `, ${v.building} building` : ""}${
        v.failed > 0 ? `, ${v.failed} failed` : ""
      }`
    : "Vercel: (no API data — set VERCEL_API_TOKEN + team)";

  const allHealthy = degradedCount === 0 && otherRows.length > 0 && healthyCount === otherRows.length;
  const hasDegraded = degradedCount > 0;

  const grouped = new Map<string, InfraService[]>();
  for (const s of otherRows) {
    const list = grouped.get(s.category) ?? [];
    list.push(s);
    grouped.set(s.category, list);
  }

  const categoryOrder = ["core", "frontend", "ops", "hosting", "data", "cache"];

  const quickJump = platformRows.filter((p) => p.stateLabel && p.stateLabel !== "live" && p.anchorId);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Infrastructure Health
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Provider-native deploy state for every Render service + Vercel project, plus reachability
          and integration checks. Q2 Tech Debt (Track I4).
        </p>
      </div>

      {/* Tab bar */}
      <div
        className="flex gap-1 rounded-lg border border-zinc-800 bg-zinc-900/60 p-1"
        role="tablist"
        aria-label="Infrastructure view tabs"
      >
        <button
          role="tab"
          aria-selected={activeTab === "services"}
          onClick={() => setTab("services")}
          className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            activeTab === "services"
              ? "bg-zinc-700 text-zinc-100"
              : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          }`}
        >
          <Layers className="h-3.5 w-3.5" />
          Services
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "logs"}
          onClick={() => setTab("logs")}
          className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            activeTab === "logs"
              ? "bg-zinc-700 text-zinc-100"
              : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          }`}
        >
          <ScrollText className="h-3.5 w-3.5" />
          Logs
        </button>
      </div>

      {activeTab === "logs" && (
        <div role="tabpanel" aria-label="Application logs">
          <LogsTab />
        </div>
      )}

      {activeTab !== "logs" && (
      <>
      <section
        className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4"
        data-testid="infra-health-summary"
        aria-label="Platform health summary"
      >
        <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
          <Layers className="h-3.5 w-3.5" />
          Deploy platform (source of truth)
        </div>
        <p className="text-sm text-zinc-200" data-testid="infra-summary-render">
          {renderLine}
        </p>
        <p className="mt-1 text-sm text-zinc-200" data-testid="infra-summary-vercel">
          {vercelLine}
        </p>
        {quickJump.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
            <span className="w-full">Quick jump to issues:</span>
            {quickJump.map((p) => (
              <a
                key={p.anchorId}
                href={`#${p.anchorId}`}
                className="rounded border border-rose-900/50 bg-rose-950/30 px-2 py-0.5 text-rose-200 hover:bg-rose-900/30"
              >
                {p.service}
              </a>
            ))}
          </div>
        )}
        {platformPartial.length > 0 && (
          <p className="mt-2 text-xs text-amber-400/90">
            Partial API notes: {platformPartial.join(" · ")}
          </p>
        )}
      </section>

      <div className="flex items-center gap-3">
        <div
          className={`inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium ${
            allHealthy
              ? "border border-emerald-800/40 bg-emerald-950/30 text-emerald-300"
              : hasDegraded
                ? "border border-rose-800/40 bg-rose-950/30 text-rose-300"
                : "border border-amber-800/40 bg-amber-950/30 text-amber-300"
          }`}
        >
          <StatusDot
            healthy={allHealthy}
            configured={otherRows.length === 0 || configuredCount === otherRows.length}
          />
          {allHealthy
            ? "All synthetic checks green"
            : hasDegraded
              ? `${degradedCount} check${degradedCount > 1 ? "s" : ""} degraded (below)`
              : "Supplementary checks"}
        </div>
      </div>

      <motion.section
        className="grid gap-4 md:grid-cols-3"
        variants={stagger}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={fadeUp} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Platform rows</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-zinc-100">
            {platformRows.length}
          </p>
          <p className="text-sm text-zinc-500">Render + Postgres + Key Value + Vercel</p>
        </motion.div>
        <motion.div variants={fadeUp} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Supplementary / HTTP</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums">
            <span className={healthyCount === otherRows.length ? "text-emerald-300" : "text-zinc-100"}>
              {healthyCount}
            </span>
            <span className="text-zinc-500">/{otherRows.length}</span>
          </p>
          <p className="text-sm text-zinc-500">n8n, Slack, Neon, etc.</p>
        </motion.div>
        <motion.div variants={fadeUp} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Degraded (below)</p>
          <p className={`mt-2 text-2xl font-semibold tabular-nums ${degradedCount > 0 ? "text-rose-300" : "text-emerald-300"}`}>
            {degradedCount}
          </p>
          <p className="text-sm text-zinc-500">HTTP / token checks</p>
        </motion.div>
      </motion.section>

      <motion.section
        variants={fadeUp}
        initial="hidden"
        animate="show"
        className="space-y-3"
        data-testid="infra-quota-panels"
        aria-label="Vendor quota snapshots via Brain API"
      >
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Vendor quotas</p>
          <p className="mt-1 text-sm text-zinc-400">
            Brain-maintained snapshots (Vercel, GitHub Actions, Render). Bands: green below 60%,
            amber 60–85%, red above 85% of modeled caps — scan the top stripe on each card.
          </p>
        </div>
        <div className="grid gap-4 xl:grid-cols-3">
          <QuotaVercelPanel refreshSignal={quotaRefresh} />
          <QuotaGitHubActionsPanel refreshSignal={quotaRefresh} />
          <QuotaRenderPanel refreshSignal={quotaRefresh} />
        </div>
      </motion.section>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-900/60 px-4 py-3">
        <div className="flex items-center gap-3 text-sm text-zinc-400">
          <Radio className="h-3.5 w-3.5" />
          <span>
            Last checked: <span className="text-zinc-200">{formatTimePT(checkedAt)} PT</span>
          </span>
          <label className="flex cursor-pointer items-center gap-1.5 text-xs">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="h-3 w-3 rounded border-zinc-600 bg-zinc-800 accent-emerald-500"
            />
            Auto-refresh 30s
          </label>
          {refreshError && (
            <span className="ml-3 rounded-full border border-rose-800/40 bg-rose-950/20 px-2 py-0.5 text-xs text-rose-300">
              Refresh failed: {refreshError}
            </span>
          )}
        </div>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 transition hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {platformRows.length > 0 && (
        <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-3">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Platform services</p>
          <div className="grid gap-3 md:grid-cols-2">
            {platformRows.map((svc) => (
              <div
                key={svc.service + (svc.anchorId ?? "") + (svc.probeKind ?? "")}
                id={svc.anchorId}
                data-testid="infra-probe-row"
                className={`scroll-mt-24 rounded-xl border bg-zinc-900/60 p-4 ${
                  !svc.configured
                    ? "border-zinc-800"
                    : svc.healthy
                      ? "border-emerald-800/20"
                      : "border-rose-800/30"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-zinc-100">{svc.service}</p>
                    <p className="mt-0.5 text-xs text-zinc-500">
                      {svc.probeKind === "vercel" ? "Vercel" : "Render"} · {svc.platformType ?? "—"}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded border px-2 py-0.5 text-xs font-medium uppercase ${platformStateBadgeClass(
                      platformProbeBadgeTone(svc),
                    )}`}
                    data-testid="infra-probe-state"
                  >
                    {platformProbeBadgeLabel(svc)}
                  </span>
                </div>
                <p className="mt-2 text-sm text-zinc-400">{svc.detail}</p>
                {svc.commitSha && (
                  <p className="mt-1 font-mono text-xs text-zinc-500">SHA {svc.commitSha}</p>
                )}
                {svc.lastDeployedAt && (
                  <p className="text-xs text-zinc-500">Deployed {formatTimePT(svc.lastDeployedAt)} PT</p>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  {svc.dashboardUrl && (
                    <a
                      href={svc.dashboardUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-zinc-500 transition hover:text-zinc-300"
                    >
                      Open dashboard <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      <motion.div className="space-y-6" variants={stagger} initial="hidden" animate="show">
        {categoryOrder.map((cat) => {
          const catServices = grouped.get(cat);
          if (!catServices?.length) return null;
          const meta = categoryMeta[cat] ?? { label: cat, icon: Server };
          const CatIcon = meta.icon;
          return (
            <motion.section key={cat} variants={fadeUp}>
              <div className="mb-3 flex items-center gap-2">
                <CatIcon className="h-4 w-4 text-zinc-500" />
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">
                  {meta.label}
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">

                {catServices.map((svc) => (
                  <div
                    key={svc.service}
                    className={`rounded-xl border bg-zinc-900/60 p-4 transition ${
                      !svc.configured
                        ? "border-zinc-800"
                        : svc.healthy
                          ? "border-emerald-800/30"
                          : "border-rose-800/30"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <StatusDot healthy={svc.healthy} configured={svc.configured} />
                        <p className="font-medium text-zinc-100">{svc.service}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        {svc.latencyMs !== null && (
                          <span className={`font-mono text-xs tabular-nums ${latencyColor(svc.latencyMs)}`}>
                            {svc.latencyMs}ms
                          </span>
                        )}
                        <StatusIcon healthy={svc.healthy} configured={svc.configured} />
                      </div>
                    </div>
                    <p className="mt-2 text-sm text-zinc-400">{svc.detail}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-3">
                      {svc.dashboardUrl && (
                        <a
                          href={svc.dashboardUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-zinc-500 transition hover:text-zinc-300"
                        >
                          Dashboard <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                      {svc.consoleUrl && (
                        <a
                          href={svc.consoleUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-zinc-500 transition hover:text-zinc-300"
                        >
                          Console <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </motion.section>
          );
        })}
      </motion.div>
      </>
      )}
    </div>
  );
}
