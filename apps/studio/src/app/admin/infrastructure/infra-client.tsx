"use client";

import { useState, useEffect, useCallback } from "react";
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
} from "lucide-react";
import { motion } from "framer-motion";

type InfraService = {
  service: string;
  category: "core" | "frontend" | "ops" | "data" | "cache" | "hosting";
  configured: boolean;
  healthy: boolean;
  detail: string;
  latencyMs: number | null;
  dashboardUrl: string | null;
  consoleUrl?: string | null;
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

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

const AUTO_REFRESH_MS = 60_000;

export default function InfraClient({
  initialServices,
  initialCheckedAt,
}: {
  initialServices: InfraService[];
  initialCheckedAt: string;
}) {
  const [services, setServices] = useState(initialServices);
  const [checkedAt, setCheckedAt] = useState(initialCheckedAt);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await fetch("/api/admin/infrastructure");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setServices(data.services);
      setCheckedAt(data.checkedAt);
      setRefreshError(null);
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

  const healthyCount = services.filter((s) => s.healthy).length;
  const configuredCount = services.filter((s) => s.configured).length;
  const degradedCount = services.filter((s) => s.configured && !s.healthy).length;

  const allHealthy = degradedCount === 0 && configuredCount === services.length;
  const hasDegraded = degradedCount > 0;

  const grouped = new Map<string, InfraService[]>();
  for (const s of services) {
    const list = grouped.get(s.category) ?? [];
    list.push(s);
    grouped.set(s.category, list);
  }

  const categoryOrder = ["core", "frontend", "ops", "hosting", "data", "cache"];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Infrastructure Health
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Live checks across the full Paperwork Labs stack.
        </p>
      </div>

      {/* Overall status pill */}
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
          <StatusDot healthy={allHealthy} configured={configuredCount === services.length} />
          {allHealthy
            ? "All Systems Operational"
            : hasDegraded
              ? `${degradedCount} Service${degradedCount > 1 ? "s" : ""} Degraded`
              : "Partially Configured"}
        </div>
      </div>

      {/* Stats row */}
      <motion.section
        className="grid gap-4 md:grid-cols-3"
        variants={stagger}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={fadeUp} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Overall</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums">
            <span className={healthyCount === services.length ? "text-emerald-300" : "text-zinc-100"}>
              {healthyCount}
            </span>
            <span className="text-zinc-500">/{services.length}</span>
          </p>
          <p className="text-sm text-zinc-500">services healthy</p>
        </motion.div>
        <motion.div variants={fadeUp} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Configured</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums">
            {configuredCount}
            <span className="text-zinc-500">/{services.length}</span>
          </p>
          <p className="text-sm text-zinc-500">provider keys present</p>
        </motion.div>
        <motion.div variants={fadeUp} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Degraded</p>
          <p className={`mt-2 text-2xl font-semibold tabular-nums ${degradedCount > 0 ? "text-rose-300" : "text-emerald-300"}`}>
            {degradedCount}
          </p>
          <p className="text-sm text-zinc-500">configured with failures</p>
        </motion.div>
      </motion.section>

      {/* Refresh controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-900/60 px-4 py-3">
        <div className="flex items-center gap-3 text-sm text-zinc-400">
          <Radio className="h-3.5 w-3.5" />
          <span>
            Last checked:{" "}
            <span className="text-zinc-200">{formatTimePT(checkedAt)} PT</span>
          </span>
          <label className="flex cursor-pointer items-center gap-1.5 text-xs">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="h-3 w-3 rounded border-zinc-600 bg-zinc-800 accent-emerald-500"
            />
            Auto-refresh 60s
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

      {/* Service cards by category */}
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
    </div>
  );
}
