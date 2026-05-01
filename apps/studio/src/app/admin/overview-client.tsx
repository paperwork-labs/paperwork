"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  RefreshCw,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  GitBranch,
  ArrowRight,
  Workflow,
  Clock,
} from "lucide-react";
import { motion } from "framer-motion";

import { BrainFreshnessTile } from "@/components/admin/BrainFreshnessTile";
import { HqMissingCredCard } from "@/components/admin/hq/HqMissingCredCard";

import { StatCard } from "@/components/admin/stat-card";

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

type OverviewData = {
  workflows: N8nWorkflow[];
  executions: N8nExecution[];
  prs: PullRequest[];
  infrastructure: InfraService[];
  ciRuns: CIRun[];
  slackActivity?: {
    id: number;
    persona: string;
    channel_id: string;
    summary: string;
    created_at: string;
    model: string;
    persona_pinned: boolean;
  }[];
  fetchedAt: string;
  githubPrMissingCred?: "GITHUB_TOKEN";
  githubCiMissingCred?: "GITHUB_TOKEN";
  githubPrFetchError?: string;
  githubCiFetchError?: string;
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

  const { prs, infrastructure, ciRuns, fetchedAt } = data;
  const githubPrMissingCred = data.githubPrMissingCred;
  const githubCiMissingCred = data.githubCiMissingCred;
  const githubPrFetchError = data.githubPrFetchError;
  const githubCiFetchError = data.githubCiFetchError;

  const githubAnyMissingCred = Boolean(githubPrMissingCred || githubCiMissingCred);
  const githubFetchErrorLines = Array.from(
    new Set([githubPrFetchError, githubCiFetchError].filter(Boolean) as string[]),
  );
  const githubPrDegraded = Boolean(githubPrMissingCred || githubPrFetchError);

  const healthyInfra = infrastructure.filter((s) => s.healthy).length;
  const degradedInfra = infrastructure.filter((s) => s.configured && !s.healthy).length;
  const unconfiguredInfra = useMemo(
    () => infrastructure.filter((s) => !s.configured).length,
    [infrastructure],
  );
  const ciFailureCount = useMemo(
    () => ciRuns.filter((r) => r.conclusion === "failure").length,
    [ciRuns],
  );
  const ciSuccessCount = useMemo(
    () => ciRuns.filter((r) => r.conclusion === "success").length,
    [ciRuns],
  );
  const prsNeedingChanges = useMemo(
    () => prs.filter((p) => p.brain_review?.verdict === "REQUEST_CHANGES").length,
    [prs],
  );

  /** Venture health from GitHub CI, infra probes, and Brain PR review — not n8n workflow volume. */
  const ventureHealth: "green" | "yellow" | "red" = useMemo(() => {
    if (degradedInfra > 0 || ciFailureCount >= 2) return "red";
    if (
      Boolean(githubPrMissingCred) ||
      Boolean(githubCiMissingCred) ||
      unconfiguredInfra > 0 ||
      ciFailureCount === 1 ||
      prsNeedingChanges > 0
    )
      return "yellow";
    return "green";
  }, [
    degradedInfra,
    ciFailureCount,
    githubPrMissingCred,
    githubCiMissingCred,
    unconfiguredInfra,
    prsNeedingChanges,
  ]);

  const trafficLightConfig =
    {
      green: {
        label: "Shipping pipeline healthy",
        subtitle: "Infra probes green · CI and Brain reviews on track",
        bg: "border-[var(--status-success)]/40 bg-[var(--status-success-bg)]",
        text: "text-[var(--status-success)]",
        dotColor: "bg-[var(--status-success)]",
        Icon: CheckCircle2,
      },
      yellow: {
        label: "Attention needed",
        subtitle: "Review CI, infra configuration, or PRs requesting changes",
        bg: "border-[var(--status-warning)]/40 bg-[var(--status-warning-bg)]",
        text: "text-[var(--status-warning)]",
        dotColor: "bg-[var(--status-warning)]",
        Icon: AlertTriangle,
      },
      red: {
        label: "Critical issues",
        subtitle: "Unhealthy infra or multiple failing CI runs on main",
        bg: "border-[var(--status-danger)]/40 bg-[var(--status-danger-bg)]",
        text: "text-[var(--status-danger)]",
        dotColor: "bg-[var(--status-danger)]",
        Icon: XCircle,
      },
    }[ventureHealth];

  const activity: ActivityItem[] = useMemo(() => {
    const items: ActivityItem[] = [
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
      ...ciRuns.slice(0, 8).map((run) => ({
        id: `ci-${run.id}`,
        timestamp: run.updatedAt,
        label:
          run.status === "in_progress" || run.status === "queued"
            ? `CI ${run.status.replace(/_/g, " ")}`
            : run.conclusion === "success"
              ? "CI passed"
              : run.conclusion === "failure"
                ? "CI failed"
                : `CI ${run.conclusion ?? run.status}`,
        detail: run.name,
        href: run.url,
        status: (run.conclusion === "failure"
          ? "error"
          : run.conclusion === "success"
            ? "success"
            : "neutral") as "error" | "success" | "neutral",
      })),
    ]
      .filter((item) => Boolean(item.timestamp))
      .sort((a, b) => parseTs(b.timestamp) - parseTs(a.timestamp))
      .slice(0, 12);

    return items;
  }, [prs, ciRuns]);

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-3xl font-semibold tracking-tight text-transparent">
            Company HQ
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Brain-led operating picture — shipping, health, and what needs a decision.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {refreshError && (
            <span className="rounded-full border border-[var(--status-danger)]/40 bg-[var(--status-danger-bg)] px-2 py-0.5 text-xs text-[var(--status-danger)]">
              Refresh failed: {refreshError}
            </span>
          )}
          <button
            type="button"
            onClick={refresh}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 outline-none transition hover:bg-zinc-800 hover:text-zinc-100 focus-visible:ring-2 focus-visible:ring-zinc-500 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {githubAnyMissingCred || githubFetchErrorLines.length > 0 ? (
        <div
          data-testid="overview-github-honesty-banner"
          className="space-y-6"
          role="status"
        >
          {githubAnyMissingCred ? (
            <HqMissingCredCard
              service="GitHub (PRs & Actions)"
              envVar="GITHUB_TOKEN"
              reconnectAction={{
                label: "Reconnect",
                href: "https://vercel.com/docs/projects/environment-variables",
              }}
              docsLink="https://github.com/paperwork-labs/paperwork/blob/main/docs/infra/PR_PIPELINE_AUTOMATION.md"
              description="Open PR and CI widgets cannot load from the GitHub API because GITHUB_TOKEN is not set in this environment. Set the env var in Vercel / Render then redeploy."
            />
          ) : null}
          {githubFetchErrorLines.map((line) => (
            <p
              key={line}
              className="rounded-lg border border-[var(--status-warning)]/30 bg-[var(--status-warning-bg)] px-3 py-2 text-sm text-[var(--status-warning)]"
            >
              GitHub data could not be loaded: {line}
            </p>
          ))}
        </div>
      ) : null}

      {/* Traffic light — GitHub CI, infra, Brain PR signals (not n8n volume) */}
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        className={`flex items-center gap-4 rounded-xl border px-5 py-4 ring-1 ring-zinc-800/90 transition hover:ring-zinc-700 ${trafficLightConfig.bg}`}
      >
        <span className="relative inline-block h-3 w-3 shrink-0">
          {ventureHealth === "green" ? (
            <span
              className={`absolute inset-0 motion-safe:animate-ping rounded-full ${trafficLightConfig.dotColor} opacity-40`}
            />
          ) : null}
          <span className={`relative inline-block h-3 w-3 rounded-full ${trafficLightConfig.dotColor}`} />
        </span>
        <trafficLightConfig.Icon className={`h-5 w-5 shrink-0 ${trafficLightConfig.text}`} />
        <div className="min-w-0 flex-1">
          <span className={`block font-medium ${trafficLightConfig.text}`}>
            {trafficLightConfig.label}
          </span>
          <span className="mt-0.5 block text-xs text-zinc-500">{trafficLightConfig.subtitle}</span>
        </div>
        <span className="shrink-0 text-xs text-zinc-500">{formatTimePT(fetchedAt)} PT</span>
      </motion.div>

      <BrainFreshnessTile />

      {/* Stat cards — PRs, CI, infra, products */}
      <motion.section
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
        variants={stagger}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={fadeUp} className="min-h-[1px] min-w-0">
          <StatCard
            label="Open PRs"
            value={githubPrDegraded ? "—" : prs.length}
            href={
              githubPrDegraded
                ? "/admin/infrastructure"
                : "/admin/workstreams?status=in_progress"
            }
            hint={
              githubPrMissingCred
                ? "Connect GITHUB_TOKEN to load pull requests."
                : githubPrFetchError
                  ? githubPrFetchError
                  : `${prs.filter((pr) => pr.brain_review?.verdict === "APPROVE").length} approved · ${prs.filter((pr) => pr.brain_review?.verdict === "COMMENT").length} commented · ${prs.filter((pr) => pr.brain_review?.verdict === "REQUEST_CHANGES").length} changes · ${prs.filter((pr) => !pr.brain_review).length} unreviewed`
            }
            className={
              githubPrDegraded
                ? "border-amber-500/35 bg-amber-950/15 ring-amber-500/25"
                : prsNeedingChanges > 0
                  ? "border-rose-500/35 bg-rose-950/15 ring-rose-500/25"
                  : undefined
            }
          />
        </motion.div>

        <motion.div variants={fadeUp} className="min-h-[1px] min-w-0">
          <StatCard
            label="CI on main"
            value={githubCiMissingCred ? "—" : ciRuns.length === 0 ? "—" : `${ciSuccessCount}/${ciRuns.length}`}
            href="https://github.com/paperwork-labs/paperwork/actions?query=branch%3Amain"
            hint={
              githubCiMissingCred
                ? "Connect GITHUB_TOKEN to load workflow runs."
                : ciRuns.length === 0
                  ? "No recent runs loaded."
                  : ciFailureCount > 0
                    ? `${ciFailureCount} failing · recent runs below`
                    : "Recent runs below"
            }
            className={
              githubCiMissingCred
                ? "border-amber-500/35 bg-amber-950/15 ring-amber-500/25"
                : ciFailureCount > 0
                  ? "border-rose-500/35 bg-rose-950/15 ring-rose-500/25"
                  : ciRuns.length > 0 && ciSuccessCount === ciRuns.length
                    ? "border-emerald-500/35 bg-emerald-950/15 ring-emerald-500/25"
                    : undefined
            }
          />
        </motion.div>

        <motion.div variants={fadeUp} className="min-h-[1px] min-w-0">
          <StatCard
            label="Infra health"
            value={infrastructure.length > 0 ? `${healthyInfra}/${infrastructure.length}` : "—"}
            href="/admin/infrastructure"
            hint="Provider checks · Brain, APIs, frontends"
            className={
              healthyInfra === infrastructure.length && infrastructure.length > 0
                ? "border-emerald-500/35 bg-emerald-950/15 ring-emerald-500/25"
                : degradedInfra > 0
                  ? "border-rose-500/35 bg-rose-950/15 ring-rose-500/25"
                  : undefined
            }
          />
        </motion.div>

        <motion.div variants={fadeUp} className="min-h-[1px] min-w-0">
          <StatCard
            label="Products"
            value="Catalog"
            href="/admin/products"
            hint="Ship matrix, plans, and product health"
          />
        </motion.div>
      </motion.section>

      {/* Architecture + CI */}
      <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Link
          href="/admin/architecture"
          className="group flex flex-col justify-between rounded-xl border border-zinc-800 bg-zinc-950 p-5 ring-1 ring-zinc-800 transition duration-200 ease-out hover:scale-[1.01] hover:border-zinc-700 hover:ring-zinc-700 active:scale-[0.995]"
        >
          <div>
            <div className="mb-3 flex items-center gap-2">
              <Workflow className="h-4 w-4 text-zinc-500" />
              <p className="text-sm font-medium text-zinc-200">Architecture</p>
              <ArrowRight className="ml-auto h-3.5 w-3.5 text-zinc-600 transition group-hover:translate-x-0.5 group-hover:text-zinc-300" />
            </div>
            <p className="text-sm leading-relaxed text-zinc-400">
              System map and dependencies — services, probes, and how Brain ties to what ships.
              Open the graph for the full interactive view.
            </p>
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-3 text-xs text-zinc-500">
            <span className="rounded-md bg-zinc-800/60 px-2 py-1 font-mono text-zinc-300">
              {infrastructure.length} probes
            </span>
            <span className="rounded-md bg-zinc-800/60 px-2 py-1 font-mono text-zinc-300">
              {healthyInfra}/{infrastructure.length} healthy
            </span>
            <span className="ml-auto text-zinc-600 group-hover:text-zinc-400">Open →</span>
          </div>
        </Link>

        <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 ring-1 ring-zinc-800">
          <div className="mb-3 flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-zinc-500" />
            <p className="text-sm font-medium text-zinc-200">Recent CI on main</p>
            <a
              href="https://github.com/paperwork-labs/paperwork/actions"
              target="_blank"
              rel="noreferrer"
              className="ml-auto text-xs text-zinc-500 transition hover:text-zinc-300"
            >
              All runs <ExternalLink className="ml-1 inline h-3 w-3" />
            </a>
          </div>
          <div className="max-h-72 space-y-1.5 overflow-y-auto">
            {githubCiMissingCred ? (
              <p className="py-2 text-sm text-zinc-500">
                Recent runs are not loaded — set <code className="font-mono text-xs">GITHUB_TOKEN</code> (see
                the banner above).
              </p>
            ) : githubCiFetchError ? (
              <p className="py-2 text-sm text-[var(--status-warning)]">{githubCiFetchError}</p>
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
      </div>

      <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 ring-1 ring-zinc-800">
          <p className="mb-3 text-sm font-medium text-zinc-200">Shipping activity</p>
          <p className="mb-3 text-xs text-zinc-500">Pull requests and GitHub Actions — newest first.</p>
          <div className="max-h-96 space-y-1.5 overflow-y-auto">
            {activity.length === 0 ? (
              <p className="py-2 text-sm text-zinc-500">No recent PR or CI activity.</p>
            ) : (
              activity.map((item) => (
                <div key={item.id} className="rounded-md bg-zinc-800/40 px-3 py-2 text-sm">
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
                    <p className="mt-0.5 truncate pl-[14px] text-xs text-zinc-500">{item.detail}</p>
                  )}
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 ring-1 ring-zinc-800">
          <p className="mb-3 text-sm font-medium text-zinc-200">Quick links</p>
          <div className="space-y-1">
            {[
              { label: "Brain conversations", href: "/admin/brain/conversations" },
              { label: "Workstreams", href: "/admin/workstreams" },
              { label: "Products", href: "/admin/products" },
              { label: "Architecture", href: "/admin/architecture" },
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
          </div>
        </section>
      </div>
      </div>
    </div>
  );
}
