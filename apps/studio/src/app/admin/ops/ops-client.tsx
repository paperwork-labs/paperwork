"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ExternalLink,
  Play,
  Pause,
  Zap,
  Link2,
  DollarSign,
} from "lucide-react";
import { motion } from "framer-motion";

type Workflow = {
  id: string;
  name: string;
  active: boolean;
  createdAt?: string;
  updatedAt?: string;
};

type Execution = {
  id: string;
  finished: boolean;
  mode: string;
  startedAt?: string;
  stoppedAt?: string;
  workflowId?: string;
  status?: string;
};

type ServiceToken = {
  service: string;
  configured: boolean;
  verified: boolean;
  detail: string;
};

type OpsData = {
  workflows: Workflow[];
  executions: Execution[];
  serviceTokens: ServiceToken[];
  fetchedAt: string;
};

const costs = [
  { service: "Render (FileFree API)", monthly: "$7.00", type: "compute" },
  { service: "Render (LaunchFree API)", monthly: "$7.00", type: "compute" },
  { service: "Hetzner (n8n + Postiz)", monthly: "$5.49", type: "ops" },
  { service: "Google Workspace", monthly: "$6.00", type: "productivity" },
  { service: "Vercel (5 apps)", monthly: "$0.00", type: "hosting", note: "Hobby tier" },
  { service: "Neon PostgreSQL", monthly: "$0.00", type: "database", note: "Free tier" },
  { service: "Upstash Redis", monthly: "$0.00", type: "cache", note: "Free tier" },
  { service: "GCP Cloud Vision", monthly: "~$0.00", type: "ai", note: "1K free pages/mo" },
];

const totalMonthlyCost = costs.reduce(
  (sum, c) => sum + parseFloat(c.monthly.match(/[\d.]+/)?.[0] ?? "0"),
  0,
);

function formatTimePT(iso: string | undefined): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZone: "America/Los_Angeles",
    }).format(new Date(iso));
  } catch {
    return "—";
  }
}

function relativeTime(iso: string | undefined): string {
  if (!iso) return "—";
  const ts = Date.parse(iso);
  if (isNaN(ts)) return "—";
  const diffMs = Date.now() - ts;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function executionStatusStyle(status: string | undefined) {
  const s = (status ?? "").toLowerCase();
  if (s === "success") return { color: "text-emerald-400", bg: "bg-emerald-400" };
  if (s === "error" || s === "failed" || s === "crashed") return { color: "text-rose-400", bg: "bg-rose-400" };
  if (s === "running" || s === "waiting") return { color: "text-amber-400", bg: "bg-amber-400" };
  return { color: "text-zinc-400", bg: "bg-zinc-400" };
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

export default function OpsClient({ initial }: { initial: OpsData }) {
  const [data, setData] = useState(initial);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await fetch("/api/admin/ops");
      const json = await res.json();
      setData(json);
    } catch {
      // keep stale
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(refresh, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  const { workflows, executions, serviceTokens, fetchedAt } = data;

  const activeCount = workflows.filter((w) => w.active).length;
  const workflowNameById = useMemo(
    () => new Map(workflows.map((w) => [w.id, w.name])),
    [workflows],
  );

  const recentExecs = executions.slice(0, 15);
  const last24h = useMemo(() => {
    const cutoff = Date.now() - 24 * 60 * 60 * 1000;
    return executions.filter((e) => {
      const ts = Date.parse(e.startedAt || e.stoppedAt || "");
      return !isNaN(ts) && ts >= cutoff;
    });
  }, [executions]);
  const failedLast24h = last24h.filter((e) => {
    const s = (e.status ?? "").toLowerCase();
    return s === "error" || s === "failed" || s === "crashed";
  }).length;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
            Operations
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Agent workflows, service tokens, and cost tracking.
          </p>
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

      {/* Workflow Roster */}
      <motion.section variants={stagger} initial="hidden" animate="show">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-zinc-500" />
            <p className="text-sm font-medium text-zinc-200">
              n8n Workflows{" "}
              <span className="text-zinc-500">
                ({activeCount}/{workflows.length} active)
              </span>
            </p>
          </div>
          <a
            href="https://n8n.paperworklabs.com"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-xs text-zinc-500 transition hover:text-zinc-300"
          >
            n8n Editor <ExternalLink className="h-3 w-3" />
          </a>
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          {workflows.length === 0 ? (
            <div className="col-span-2 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 text-sm text-zinc-500">
              No workflows found. Check n8n API connection.
            </div>
          ) : (
            workflows.map((w) => {
              const lastExec = executions.find((e) => e.workflowId === w.id);
              const lastStatus = lastExec ? executionStatusStyle(lastExec.status) : null;
              return (
                <motion.div
                  key={w.id}
                  variants={fadeUp}
                  className={`rounded-lg border bg-zinc-900/60 px-4 py-3 ${
                    w.active ? "border-zinc-700/60" : "border-zinc-800/40 opacity-60"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      {w.active ? (
                        <Play className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                      ) : (
                        <Pause className="h-3.5 w-3.5 shrink-0 text-zinc-500" />
                      )}
                      <span className="truncate text-sm font-medium text-zinc-100">
                        {w.name}
                      </span>
                    </div>
                    {lastStatus && (
                      <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${lastStatus.bg}`} />
                    )}
                  </div>
                  {lastExec && (
                    <p className="mt-1 pl-[22px] text-xs text-zinc-500">
                      Last: {relativeTime(lastExec.startedAt || lastExec.stoppedAt)}{" "}
                      <span className={lastStatus?.color}>
                        {lastExec.status || (lastExec.finished ? "finished" : "running")}
                      </span>
                    </p>
                  )}
                </motion.div>
              );
            })
          )}
        </div>
      </motion.section>

      {/* Execution feed + Service Tokens */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Recent Executions */}
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-medium text-zinc-200">Recent Executions</p>
            <p className="text-xs text-zinc-500">
              24h: {last24h.length} runs, {failedLast24h} failed
            </p>
          </div>
          <div className="space-y-1.5 max-h-80 overflow-y-auto">
            {recentExecs.length === 0 ? (
              <p className="py-2 text-sm text-zinc-500">No recent executions.</p>
            ) : (
              recentExecs.map((e) => {
                const style = executionStatusStyle(e.status);
                const name = workflowNameById.get(e.workflowId ?? "") || "Unknown";
                return (
                  <div
                    key={e.id}
                    className="flex items-center gap-2 rounded-md bg-zinc-800/40 px-3 py-2 text-xs"
                  >
                    <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${style.bg}`} />
                    <span className="truncate font-medium text-zinc-200">{name}</span>
                    <span className="ml-auto shrink-0 text-zinc-500">
                      {relativeTime(e.startedAt || e.stoppedAt)}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </section>

        {/* Service Tokens */}
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <div className="mb-3 flex items-center gap-2">
            <Link2 className="h-4 w-4 text-zinc-500" />
            <p className="text-sm font-medium text-zinc-200">Service Tokens</p>
          </div>
          <div className="space-y-2">
            {serviceTokens.map((t) => (
              <div
                key={t.service}
                className="flex items-center justify-between rounded-md bg-zinc-800/40 px-3 py-2.5 text-sm"
              >
                <div className="flex items-center gap-2.5">
                  {t.verified ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  ) : t.configured ? (
                    <XCircle className="h-4 w-4 text-rose-400" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-amber-400" />
                  )}
                  <span className="font-medium text-zinc-100">{t.service}</span>
                </div>
                <span className="text-xs text-zinc-500">{t.detail}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Cost Snapshot */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <div className="mb-3 flex items-center gap-2">
          <DollarSign className="h-4 w-4 text-zinc-500" />
          <p className="text-sm font-medium text-zinc-200">Monthly Cost Snapshot</p>
          <span className="ml-auto rounded-full bg-zinc-800 px-2.5 py-0.5 text-xs font-medium tabular-nums text-zinc-300">
            ${totalMonthlyCost.toFixed(2)}/mo
          </span>
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          {costs.map((c) => (
            <div
              key={c.service}
              className="flex items-center justify-between rounded-md bg-zinc-800/40 px-3 py-2 text-sm"
            >
              <div>
                <span className="text-zinc-200">{c.service}</span>
                {c.note && (
                  <span className="ml-2 text-xs text-zinc-600">{c.note}</span>
                )}
              </div>
              <span className="font-mono text-xs tabular-nums text-zinc-400">
                {c.monthly}
              </span>
            </div>
          ))}
        </div>
      </section>

      <p className="text-right text-xs text-zinc-600">
        Updated: {formatTimePT(fetchedAt)} PT
      </p>
    </div>
  );
}
