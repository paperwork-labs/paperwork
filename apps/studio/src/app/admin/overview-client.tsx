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
  Info,
} from "lucide-react";
import { motion } from "framer-motion";

import { BrainFreshnessTile } from "@/components/admin/BrainFreshnessTile";
import { HqMissingCredCard } from "@/components/admin/hq/HqMissingCredCard";

import { HqStatCard } from "@/components/admin/hq/HqStatCard";

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
  brain_review?: {
    verdict: string;
    head_sha: string;
    model: string;
    summary: string;
    created_at: string;
  };
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

type SlackActivityEntry = {
  id: number;
  persona: string;
  channel_id: string;
  summary: string;
  created_at: string;
  model: string;
  persona_pinned: boolean;
};

type OverviewData = {
  workflows: N8nWorkflow[];
  executions: N8nExecution[];
  prs: PullRequest[];
  infrastructure: InfraService[];
  ciRuns: CIRun[];
  slackActivity?: SlackActivityEntry[];
  fetchedAt: string;
  githubPrMissingCred?: "GITHUB_TOKEN";
  githubCiMissingCred?: "GITHUB_TOKEN";
  n8nConfigured?: boolean;
  slackDailyBriefingHref?: string | null;
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
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await fetch("/api/admin/overview");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setRefreshError(null);
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(refresh, 60_000);
    return () => clearInterval(interval);
  }, [refresh]);

  const { workflows, executions, prs, infrastructure, ciRuns, fetchedAt } = data;
  const slackActivity = data.slackActivity ?? [];
  const githubPrMissingCred = data.githubPrMissingCred;
  const githubCiMissingCred = data.githubCiMissingCred;
  const n8nConfigured = data.n8nConfigured ?? false;
  const slackDailyBriefingHref = data.slackDailyBriefingHref ?? null;

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

  // Traffic light — "standby" = n8n not wired but nothing else degraded (F-020)
  const ventureHealth: "green" | "yellow" | "red" | "standby" = useMemo(() => {
    if (degradedInfra > 0 || failedLastDay > 3) return "red";
    if (infrastructure.some((s) => !s.configured) || failedLastDay > 0) return "yellow";
    if (!n8nConfigured && workflows.length === 0) return "standby";
    if (workflows.length === 0) return "yellow";
    return "green";
  }, [degradedInfra, failedLastDay, infrastructure, n8nConfigured, workflows.length]);

  const trafficLightConfig =
    {
      green: {
        label: "All Systems Operational",
        bg: "border-[var(--status-success)]/40 bg-[var(--status-success-bg)]",
        text: "text-[var(--status-success)]",
        dotColor: "bg-[var(--status-success)]",
        Icon: CheckCircle2,
      },
      yellow: {
        label: "Partially Degraded",
        bg: "border-[var(--status-warning)]/40 bg-[var(--status-warning-bg)]",
        text: "text-[var(--status-warning)]",
        dotColor: "bg-[var(--status-warning)]",
        Icon: AlertTriangle,
      },
      red: {
        label: "Service Issues Detected",
        bg: "border-[var(--status-danger)]/40 bg-[var(--status-danger-bg)]",
        text: "text-[var(--status-danger)]",
        dotColor: "bg-[var(--status-danger)]",
        Icon: XCircle,
      },
      standby: {
        label: "Automation integrations on standby",
        bg: "border-[var(--status-info)]/35 bg-[var(--status-info-bg)]",
        text: "text-[var(--status-info)]",
        dotColor: "bg-[var(--status-info)]",
        Icon: Info,
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
      ...prs.slice(0, 10).map((pr) => {
        const verdictTag = pr.brain_review
          ? pr.brain_review.verdict === "APPROVE"
            ? "Approved"
            : pr.brain_review.verdict === "REQUEST_CHANGES"
              ? "Changes requested"
              : "Comment"
          : "";
        return {
          id: `pr-${pr.number}`,
          timestamp: pr.created_at,
          label:
            verdictTag !== ""
              ? `PR #${pr.number} · ${verdictTag}`
              : `PR #${pr.number}`,
          detail: pr.title,
          href: pr.html_url,
          status: (pr.brain_review?.verdict === "REQUEST_CHANGES"
            ? "error"
            : pr.brain_review?.verdict === "APPROVE"
              ? "success"
              : "neutral") as "error" | "success" | "neutral",
        };
      }),
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
        <div className="flex items-center gap-3">
          {refreshError && (
            <span className="rounded-full border border-[var(--status-danger)]/40 bg-[var(--status-danger-bg)] px-2 py-0.5 text-xs text-[var(--status-danger)]">
              Refresh failed: {refreshError}
            </span>
          )}
          <button
            onClick={refresh}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 transition hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {!n8nConfigured ? (
        <div
          data-testid="overview-n8n-misconfig-banner"
          className="rounded-xl border border-[var(--status-info)]/35 bg-[var(--status-info-bg)] px-4 py-3 text-sm text-[color-mix(in_srgb,var(--status-info)_88%,white)]"
          role="status"
        >
          <span className="font-medium text-[var(--status-info)]">Automation data optional: </span>
          n8n is not configured in this environment (set{" "}
          <code className="rounded bg-black/30 px-1 font-mono text-xs">N8N_API_URL</code> and API
          credentials). Dashboard tiles below will stay empty until wired.
        </div>
      ) : null}

      {/* Traffic Light */}
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        className={`flex items-center gap-3 rounded-xl border px-5 py-4 ${trafficLightConfig.bg}`}
      >
        <span className="relative inline-block h-3 w-3">
          {ventureHealth === "green" ? (
            <span
              className={`absolute inset-0 motion-safe:animate-ping rounded-full ${trafficLightConfig.dotColor} opacity-40`}
            />
          ) : null}
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

      <BrainFreshnessTile />

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
                      ? "text-[var(--status-success)]"
                      : "text-[var(--status-danger)]"
                  }`}
                >
                  ({lastBriefingExec.status})
                </span>
              )}
            </p>
          </div>
          <a
            href={slackDailyBriefingHref || "https://app.slack.com/client"}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-zinc-500 transition hover:text-zinc-300"
            title={
              slackDailyBriefingHref
                ? "Open Slack"
                : "Set NEXT_PUBLIC_SLACK_DAILY_BRIEFING_URL for a deep link to #daily-briefing"
            }
          >
            {slackDailyBriefingHref ? "#daily-briefing" : "Slack · #daily-briefing"}
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
        <motion.div variants={fadeUp}>
          <HqStatCard
            variant="default"
            status={workflows.length > 0 && activeWorkflows === workflows.length ? "success" : "neutral"}
            icon={<Zap className="h-4 w-4 text-zinc-500" />}
            label="Active workflows"
            value={workflows.length > 0 ? `${activeWorkflows}/${workflows.length}` : "—"}
            helpText="n8n workflows enabled"
          />
        </motion.div>

        <motion.div variants={fadeUp}>
          <HqStatCard
            variant="default"
            status={failedLastDay > 0 ? "danger" : "neutral"}
            icon={<Activity className="h-4 w-4 text-zinc-500" />}
            label="24h executions"
            value={executionsLastDay.length}
            helpText={`${successfulLastDay} success / ${failedLastDay} failed`}
          />
        </motion.div>

        <motion.div variants={fadeUp}>
          <HqStatCard
            variant="default"
            status={githubPrMissingCred ? "warning" : "neutral"}
            icon={<GitPullRequest className="h-4 w-4 text-zinc-500" />}
            label="Open PRs"
            value={githubPrMissingCred ? "—" : prs.length}
            helpText={
              githubPrMissingCred
                ? "Connect GITHUB_TOKEN to load pull requests."
                : `${prs.filter((pr) => pr.brain_review?.verdict === "APPROVE").length} approved · ${prs.filter((pr) => pr.brain_review?.verdict === "COMMENT").length} commented · ${prs.filter((pr) => pr.brain_review?.verdict === "REQUEST_CHANGES").length} changes · ${prs.filter((pr) => !pr.brain_review).length} unreviewed`
            }
          />
        </motion.div>

        <motion.div variants={fadeUp}>
          <HqStatCard
            variant="default"
            status={
              healthyInfra === infrastructure.length && infrastructure.length > 0
                ? "success"
                : degradedInfra > 0
                  ? "danger"
                  : "neutral"
            }
            icon={<Shield className="h-4 w-4 text-zinc-500" />}
            label="Infra health"
            value={infrastructure.length > 0 ? `${healthyInfra}/${infrastructure.length}` : "—"}
            helpText="provider checks passing"
          />
        </motion.div>
      </motion.section>

      {/* Architecture link + CI Runs */}
      <div className="grid gap-4 md:grid-cols-2">
        <Link
          href="/admin/architecture"
          className="group flex flex-col justify-between rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 transition hover:border-zinc-700 hover:bg-zinc-900/80"
        >
          <div>
            <div className="mb-3 flex items-center gap-2">
              <Workflow className="h-4 w-4 text-zinc-500" />
              <p className="text-sm font-medium text-zinc-200">System architecture</p>
              <ArrowRight className="ml-auto h-3.5 w-3.5 text-zinc-600 transition group-hover:translate-x-0.5 group-hover:text-zinc-300" />
            </div>
            <p className="text-sm leading-relaxed text-zinc-400">
              Layered service catalog with health probes — bronze, silver, gold,
              execution, frontend, platform, infra. Click any service for the dependency
              drawer; full interactive graph at the architecture page link.
            </p>
          </div>
          <div className="mt-5 flex items-center gap-3 text-xs text-zinc-500">
            <span className="rounded-md bg-zinc-800/60 px-2 py-1 font-mono text-zinc-300">
              {infrastructure.length} infra probes
            </span>
            <span className="rounded-md bg-zinc-800/60 px-2 py-1 font-mono text-zinc-300">
              {healthyInfra}/{infrastructure.length} healthy
            </span>
            <span className="ml-auto text-zinc-600 group-hover:text-zinc-400">
              Open →
            </span>
          </div>
        </Link>

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
            {githubCiMissingCred ? (
              <HqMissingCredCard
                service="GitHub Actions"
                envVar="GITHUB_TOKEN"
                reconnectAction={{
                  label: "Reconnect",
                  href: "https://vercel.com/docs/projects/environment-variables",
                }}
                docsLink="https://github.com/paperwork-labs/paperwork/blob/main/docs/infra/PR_PIPELINE_AUTOMATION.md"
                description="We can't load recent workflow runs because GITHUB_TOKEN is not set in this environment. Set the env var in Vercel / Render then redeploy."
              />
            ) : ciRuns.length === 0 ? (
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
                    <Clock className="h-3.5 w-3.5 animate-spin text-[var(--status-warning)]" />
                  ) : run.conclusion === "success" ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-[var(--status-success)]" />
                  ) : run.conclusion === "failure" ? (
                    <XCircle className="h-3.5 w-3.5 text-[var(--status-danger)]" />
                  ) : (
                    <AlertTriangle className="h-3.5 w-3.5 text-zinc-400" />
                  )}
                  <span className="truncate font-medium text-zinc-200">{run.name}</span>
                  <span
                    className={`ml-auto shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                      run.conclusion === "success"
                        ? "bg-[var(--status-success-bg)] text-[var(--status-success)]"
                        : run.conclusion === "failure"
                          ? "bg-[var(--status-danger-bg)] text-[var(--status-danger)]"
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

      {/* Slack Activity + Activity Feed + Quick Links */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-medium text-zinc-200">Brain · Slack activity</p>
          <span className="text-[10px] uppercase tracking-wide text-zinc-500">
            {slackActivity.length} recent
          </span>
        </div>
        <div className="space-y-1.5 max-h-72 overflow-y-auto">
          {slackActivity.length === 0 ? (
            <p className="py-2 text-sm text-zinc-500">
              No Slack conversations in memory yet. Brain posts here when personas
              reply in threads or proactive cadences fire.
            </p>
          ) : (
            slackActivity.map((entry) => (
              <div key={entry.id} className="rounded-md bg-zinc-800/40 px-3 py-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--status-info)]" />
                  <span className="font-medium text-zinc-100">
                    {entry.persona}
                  </span>
                  {entry.persona_pinned ? (
                    <span className="rounded-full bg-[var(--status-info-bg)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--status-info)]">
                      pinned
                    </span>
                  ) : null}
                  <span className="truncate text-xs text-zinc-500">
                    #{entry.channel_id}
                  </span>
                  <span className="ml-auto shrink-0 text-xs text-zinc-600">
                    {relativeTime(entry.created_at)}
                  </span>
                </div>
                <p className="mt-0.5 truncate pl-[14px] text-xs text-zinc-400">
                  {entry.summary}
                </p>
                {entry.model ? (
                  <p className="pl-[14px] text-[10px] text-zinc-600">{entry.model}</p>
                ) : null}
              </div>
            ))
          )}
        </div>
      </section>

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
                          ? "bg-[var(--status-success)]"
                          : item.status === "error"
                            ? "bg-[var(--status-danger)]"
                            : "bg-[var(--status-muted)]"
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
              { label: "Workflows", href: "/admin/architecture?tab=flows", internal: true },
              { label: "Sprint tracker", href: "/admin/sprints", internal: true },
              { label: "Infrastructure", href: "/admin/infrastructure", internal: true },
              { label: "Secrets vault", href: "/admin/infrastructure?tab=secrets", internal: true },
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
