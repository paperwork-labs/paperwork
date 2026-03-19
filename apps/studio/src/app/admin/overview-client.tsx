"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  RefreshCw,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Activity,
  GitPullRequest,
  GitBranch,
  Zap,
  Shield,
  Radio,
  ArrowRight,
  Globe,
  Server,
  Database,
  Cpu,
  Workflow,
  Clock,
} from "lucide-react";
import { motion } from "framer-motion";

type N8nWorkflow = {
  id: string;
  name: string;
  active: boolean;
};
type N8nExecution = {
  id: string;
  finished: boolean;
  mode: string;
  startedAt?: string;
  stoppedAt?: string;
  workflowId?: string;
  status?: string;
};
type PullRequest = {
  number: number;
  title: string;
  html_url: string;
  created_at: string;
  draft: boolean;
  user?: { login?: string };
};
type InfraService = {
  service: string;
  category: string;
  configured: boolean;
  healthy: boolean;
  detail: string;
  latencyMs: number | null;
  dashboardUrl: string | null;
};
type CIRun = {
  id: number;
  name: string;
  status: string;
  conclusion: string | null;
  url: string;
  createdAt: string;
  updatedAt: string;
};

type OverviewData = {
  workflows: N8nWorkflow[];
  executions: N8nExecution[];
  prs: PullRequest[];
  infrastructure: InfraService[];
  ciRuns: CIRun[];
  fetchedAt: string;
};

type ActivityItem = {
  id: string;
  timestamp: string;
  label: string;
  detail: string;
  href?: string;
  status?: "success" | "error" | "neutral";
};

function parseTs(value?: string) {
  if (!value) return 0;
  const ts = Date.parse(value);
  return Number.isNaN(ts) ? 0 : ts;
}

function relativeTime(value?: string) {
  if (!value) return "—";
  const ts = parseTs(value);
  if (!ts) return "—";
  const diffMs = Date.now() - ts;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatTimePT(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZone: "America/Los_Angeles",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function statusColor(s: string | undefined) {
  const status = (s ?? "").toLowerCase();
  if (status === "success") return "success" as const;
  if (status === "error" || status === "failed" || status === "crashed") return "error" as const;
  return "neutral" as const;
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

export default function OverviewClient({ initial }: { initial: OverviewData }) {
  const [data, setData] = useState(initial);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await fetch("/api/admin/overview");
      const json = await res.json();
      setData(json);
    } catch {
      // keep stale
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(refresh, 60000);
    return () => clearInterval(interval);
  }, [refresh]);

  const { workflows, executions, prs, infrastructure, ciRuns, fetchedAt } = data;

  const activeWorkflows = workflows.filter((w) => w.active).length;
  const workflowNameById = useMemo(
    () => new Map(workflows.map((w) => [w.id, w.name])),
    [workflows],
  );

  const now = Date.now();
  const dayAgo = now - 24 * 60 * 60 * 1000;
  const executionsLastDay = useMemo(
    () =>
      executions.filter((e) => {
        const ts = parseTs(e.startedAt) || parseTs(e.stoppedAt);
        return ts >= dayAgo;
      }),
    [executions, dayAgo],
  );
  const successfulLastDay = executionsLastDay.filter(
    (e) => (e.status ?? "").toLowerCase() === "success",
  ).length;
  const failedLastDay = executionsLastDay.filter((e) => {
    const s = (e.status ?? "").toLowerCase();
    return s === "error" || s === "failed" || s === "crashed";
  }).length;

  const healthyInfra = infrastructure.filter((s) => s.healthy).length;
  const degradedInfra = infrastructure.filter((s) => s.configured && !s.healthy).length;

  // Traffic light
  const ventureHealth: "green" | "yellow" | "red" = useMemo(() => {
    if (degradedInfra > 0 || failedLastDay > 3) return "red";
    if (
      infrastructure.some((s) => !s.configured) ||
      failedLastDay > 0 ||
      workflows.length === 0
    )
      return "yellow";
    return "green";
  }, [degradedInfra, failedLastDay, infrastructure, workflows]);

  const trafficLightConfig = {
    green: {
      label: "All Systems Operational",
      bg: "border-emerald-800/40 bg-emerald-950/20",
      text: "text-emerald-300",
      dotColor: "bg-emerald-400",
      Icon: CheckCircle2,
    },
    yellow: {
      label: "Partially Degraded",
      bg: "border-amber-800/40 bg-amber-950/20",
      text: "text-amber-300",
      dotColor: "bg-amber-400",
      Icon: AlertTriangle,
    },
    red: {
      label: "Service Issues Detected",
      bg: "border-rose-800/40 bg-rose-950/20",
      text: "text-rose-300",
      dotColor: "bg-rose-400",
      Icon: XCircle,
    },
  }[ventureHealth];

  // Daily briefing detection — find the most recent EA workflow execution
  const lastBriefingExec = useMemo(() => {
    return executions.find((e) => {
      const name = workflowNameById.get(e.workflowId ?? "") ?? "";
      return name.toLowerCase().includes("daily") || name.toLowerCase().includes("briefing");
    });
  }, [executions, workflowNameById]);

  // Build activity feed
  const activity: ActivityItem[] = useMemo(() => {
    const items: ActivityItem[] = [
      ...executions.slice(0, 20).map((e) => {
        const status = statusColor(e.status);
        const label = e.status
          ? `Workflow ${e.status}`
          : e.finished
            ? "Workflow finished"
            : "Workflow running";
        return {
          id: `exec-${e.id}`,
          timestamp: e.startedAt ?? e.stoppedAt ?? "",
          label,
          detail: `${workflowNameById.get(e.workflowId ?? "") ?? "Unknown"} (#${e.id})`,
          status,
        };
      }),
      ...prs.slice(0, 10).map((pr) => ({
        id: `pr-${pr.number}`,
        timestamp: pr.created_at,
        label: `PR #${pr.number} opened`,
        detail: pr.title,
        href: pr.html_url,
        status: "neutral" as const,
      })),
    ]
      .filter((item) => Boolean(item.timestamp))
      .sort((a, b) => parseTs(b.timestamp) - parseTs(a.timestamp))
      .slice(0, 12);

    return items;
  }, [executions, prs, workflowNameById]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-3xl font-semibold tracking-tight text-transparent">
            Command Center
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Venture-wide health at a glance.
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

      {/* Traffic Light */}
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        className={`flex items-center gap-3 rounded-xl border px-5 py-4 ${trafficLightConfig.bg}`}
      >
        <span className="relative inline-block h-3 w-3">
          {ventureHealth === "green" && (
            <span className={`absolute inset-0 animate-ping rounded-full ${trafficLightConfig.dotColor} opacity-40`} />
          )}
          <span className={`relative inline-block h-3 w-3 rounded-full ${trafficLightConfig.dotColor}`} />
        </span>
        <trafficLightConfig.Icon className={`h-5 w-5 ${trafficLightConfig.text}`} />
        <span className={`font-medium ${trafficLightConfig.text}`}>
          {trafficLightConfig.label}
        </span>
        <span className="ml-auto text-xs text-zinc-500">
          {formatTimePT(fetchedAt)} PT
        </span>
      </motion.div>

      {/* Daily Briefing Widget */}
      {lastBriefingExec && (
        <div className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-900/60 px-5 py-3">
          <div className="flex items-center gap-2.5">
            <Radio className="h-4 w-4 text-zinc-500" />
            <p className="text-sm text-zinc-300">
              Daily briefing last ran{" "}
              <span className="font-medium text-zinc-100">
                {relativeTime(lastBriefingExec.startedAt || lastBriefingExec.stoppedAt)}
              </span>
              {lastBriefingExec.status && (
                <span
                  className={`ml-1.5 ${
                    lastBriefingExec.status === "success"
                      ? "text-emerald-400"
                      : "text-rose-400"
                  }`}
                >
                  ({lastBriefingExec.status})
                </span>
              )}
            </p>
          </div>
          <a
            href="https://app.slack.com/client"
            target="_blank"
            rel="noreferrer"
            className="text-xs text-zinc-500 transition hover:text-zinc-300"
          >
            #daily-briefing
          </a>
        </div>
      )}

      {/* Stat cards */}
      <motion.section
        className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"
        variants={stagger}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={fadeUp} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-zinc-500" />
            <p className="text-xs uppercase tracking-wide text-zinc-400">Active workflows</p>
          </div>
          <p className="mt-2 text-2xl font-semibold tabular-nums">
            {workflows.length > 0 ? (
              <>
                <span className={activeWorkflows === workflows.length ? "text-emerald-300" : "text-zinc-100"}>
                  {activeWorkflows}
                </span>
                <span className="text-zinc-500">/{workflows.length}</span>
              </>
            ) : (
              <span className="text-zinc-500">—</span>
            )}
          </p>
          <p className="text-sm text-zinc-500">n8n workflows enabled</p>
        </motion.div>

        <motion.div variants={fadeUp} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-zinc-500" />
            <p className="text-xs uppercase tracking-wide text-zinc-400">24h executions</p>
          </div>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-zinc-100">
            {executionsLastDay.length}
          </p>
          <p className="text-sm text-zinc-500">
            <span className="text-emerald-400">{successfulLastDay}</span> success{" "}
            <span className="text-zinc-600">/</span>{" "}
            <span className={failedLastDay > 0 ? "text-rose-400" : "text-zinc-500"}>
              {failedLastDay}
            </span>{" "}
            failed
          </p>
        </motion.div>

        <motion.div variants={fadeUp} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <div className="flex items-center gap-2">
            <GitPullRequest className="h-4 w-4 text-zinc-500" />
            <p className="text-xs uppercase tracking-wide text-zinc-400">Open PRs</p>
          </div>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-zinc-100">{prs.length}</p>
          <p className="text-sm text-zinc-500">paperwork-labs/paperwork</p>
        </motion.div>

        <motion.div variants={fadeUp} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-zinc-500" />
            <p className="text-xs uppercase tracking-wide text-zinc-400">Infra health</p>
          </div>
          <p className="mt-2 text-2xl font-semibold tabular-nums">
            <span className={healthyInfra === infrastructure.length ? "text-emerald-300" : "text-zinc-100"}>
              {healthyInfra}
            </span>
            <span className="text-zinc-500">/{infrastructure.length}</span>
          </p>
          <p className="text-sm text-zinc-500">provider checks passing</p>
        </motion.div>
      </motion.section>

      {/* Architecture + CI Runs */}
      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-4 text-sm font-medium text-zinc-200">System Architecture</p>
          <div className="space-y-4 text-xs">
            <div>
              <p className="mb-1.5 font-medium uppercase tracking-wider text-zinc-600">User Flow</p>
              <div className="flex flex-wrap items-center gap-1.5 text-zinc-400">
                <Globe className="h-3.5 w-3.5 text-zinc-300" />
                <span>User</span>
                <ArrowRight className="h-3 w-3 text-zinc-600" />
                <span className="rounded bg-zinc-700/50 px-1.5 py-0.5 text-zinc-300">Vercel (5 apps)</span>
                <ArrowRight className="h-3 w-3 text-zinc-600" />
                <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-blue-400">Render API</span>
                <ArrowRight className="h-3 w-3 text-zinc-600" />
                <span className="rounded bg-green-500/10 px-1.5 py-0.5 text-green-400">Neon DB</span>
                <span className="text-zinc-700">+</span>
                <span className="rounded bg-orange-500/10 px-1.5 py-0.5 text-orange-400">Upstash Redis</span>
              </div>
            </div>
            <div>
              <p className="mb-1.5 font-medium uppercase tracking-wider text-zinc-600">AI Agents</p>
              <div className="flex flex-wrap items-center gap-1.5 text-zinc-400">
                <Workflow className="h-3.5 w-3.5 text-amber-400" />
                <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-amber-400">n8n (16 workflows)</span>
                <ArrowRight className="h-3 w-3 text-zinc-600" />
                <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-emerald-400">OpenAI</span>
                <span className="text-zinc-700">+</span>
                <span className="text-zinc-400">Slack</span>
                <span className="text-zinc-700">+</span>
                <span className="text-zinc-400">GitHub</span>
              </div>
            </div>
            <div>
              <p className="mb-1.5 font-medium uppercase tracking-wider text-zinc-600">Social</p>
              <div className="flex flex-wrap items-center gap-1.5 text-zinc-400">
                <Cpu className="h-3.5 w-3.5 text-pink-400" />
                <span className="rounded bg-pink-500/10 px-1.5 py-0.5 text-pink-400">Postiz</span>
                <ArrowRight className="h-3 w-3 text-zinc-600" />
                <span className="text-zinc-400">TikTok, Instagram, X, YouTube</span>
              </div>
            </div>
            <div>
              <p className="mb-1.5 font-medium uppercase tracking-wider text-zinc-600">Infra</p>
              <div className="flex flex-wrap items-center gap-1.5 text-zinc-400">
                <Server className="h-3.5 w-3.5 text-zinc-300" />
                <span className="rounded bg-zinc-700/50 px-1.5 py-0.5 text-zinc-300">Hetzner VPS</span>
                <span className="text-zinc-700">hosts</span>
                <span className="text-zinc-400">n8n + Postiz + PostgreSQL + Redis</span>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <div className="mb-3 flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-zinc-500" />
            <p className="text-sm font-medium text-zinc-200">Recent CI Runs</p>
            <a
              href="https://github.com/paperwork-labs/paperwork/actions"
              target="_blank"
              rel="noreferrer"
              className="ml-auto text-xs text-zinc-500 transition hover:text-zinc-300"
            >
              All runs <ExternalLink className="ml-1 inline h-3 w-3" />
            </a>
          </div>
          <div className="space-y-1.5 max-h-72 overflow-y-auto">
            {ciRuns.length === 0 ? (
              <p className="py-2 text-sm text-zinc-500">No CI runs found.</p>
            ) : (
              ciRuns.map((run) => (
                <a
                  key={run.id}
                  href={run.url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 rounded-md bg-zinc-800/40 px-3 py-2 text-xs transition hover:bg-zinc-800/60"
                >
                  {run.status === "in_progress" || run.status === "queued" ? (
                    <Clock className="h-3.5 w-3.5 animate-spin text-amber-400" />
                  ) : run.conclusion === "success" ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  ) : run.conclusion === "failure" ? (
                    <XCircle className="h-3.5 w-3.5 text-rose-400" />
                  ) : (
                    <AlertTriangle className="h-3.5 w-3.5 text-zinc-400" />
                  )}
                  <span className="truncate font-medium text-zinc-200">{run.name}</span>
                  <span
                    className={`ml-auto shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                      run.conclusion === "success"
                        ? "bg-emerald-500/10 text-emerald-400"
                        : run.conclusion === "failure"
                          ? "bg-rose-500/10 text-rose-400"
                          : "bg-zinc-500/10 text-zinc-400"
                    }`}
                  >
                    {run.conclusion || run.status}
                  </span>
                  <span className="shrink-0 text-zinc-600">{relativeTime(run.updatedAt)}</span>
                </a>
              ))
            )}
          </div>
        </section>
      </div>

      {/* Activity Feed + Quick Links */}
      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-3 text-sm font-medium text-zinc-200">Activity Feed</p>
          <div className="space-y-1.5 max-h-96 overflow-y-auto">
            {activity.length === 0 ? (
              <p className="py-2 text-sm text-zinc-500">No recent activity.</p>
            ) : (
              activity.map((item) => (
                <div
                  key={item.id}
                  className="rounded-md bg-zinc-800/40 px-3 py-2 text-sm"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
                        item.status === "success"
                          ? "bg-emerald-400"
                          : item.status === "error"
                            ? "bg-rose-400"
                            : "bg-zinc-500"
                      }`}
                    />
                    <span className="font-medium text-zinc-200">{item.label}</span>
                    <span className="ml-auto shrink-0 text-xs text-zinc-600">
                      {relativeTime(item.timestamp)}
                    </span>
                  </div>
                  {item.href ? (
                    <a
                      href={item.href}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-0.5 block truncate pl-[14px] text-xs text-zinc-400 transition hover:text-zinc-200"
                    >
                      {item.detail}
                    </a>
                  ) : (
                    <p className="mt-0.5 truncate pl-[14px] text-xs text-zinc-500">
                      {item.detail}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-3 text-sm font-medium text-zinc-200">Quick Links</p>
          <div className="space-y-1">
            {[
              { label: "Operations", href: "/admin/ops", internal: true },
              { label: "Sprint tracker", href: "/admin/sprints", internal: true },
              { label: "Agent monitor", href: "/admin/agents", internal: true },
              { label: "Infrastructure", href: "/admin/infrastructure", internal: true },
              { label: "Secrets vault", href: "/admin/secrets", internal: true },
            ].map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="flex items-center justify-between rounded-md px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-800/60 hover:text-zinc-100"
              >
                {link.label}
                <ArrowRight className="h-3.5 w-3.5 text-zinc-600" />
              </Link>
            ))}

            <div className="my-2 border-t border-zinc-800/60" />

            {[
              { label: "n8n Editor", href: "https://n8n.paperworklabs.com" },
              { label: "Render Dashboard", href: "https://dashboard.render.com" },
              { label: "Vercel Dashboard", href: "https://vercel.com/paperwork-labs" },
              { label: "GitHub Repository", href: "https://github.com/paperwork-labs/paperwork" },
              { label: "Neon Console", href: "https://console.neon.tech" },
            ].map((link) => (
              <a
                key={link.href}
                href={link.href}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between rounded-md px-3 py-2 text-sm text-zinc-400 transition hover:bg-zinc-800/60 hover:text-zinc-200"
              >
                {link.label}
                <ExternalLink className="h-3.5 w-3.5 text-zinc-600" />
              </a>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
