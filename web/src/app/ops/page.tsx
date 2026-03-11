"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  RefreshCw,
  Server,
  Database,
  Globe,
  Cpu,
  Workflow,
  ArrowRight,
  Shield,
  GitBranch,
  BarChart3,
  Bot,
  Calendar,
  ExternalLink,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import type { ServiceCheck, N8nWorkflow, CIRun, OpsData } from "@/types/ops";

type StatusType = ServiceCheck["status"];
type IconComponent = typeof Server;

const SERVICE_ICONS: Record<string, IconComponent> = {
  "Render API": Server,
  "Vercel Frontend": Globe,
  "n8n (Agents)": Workflow,
  "Postiz (Social)": Cpu,
  "PostHog (Analytics)": BarChart3,
  "Neon DB": Database,
  "Upstash Redis": Database,
};

const STATUS_COLORS: Record<StatusType, string> = {
  healthy: "bg-green-500",
  degraded: "bg-amber-500",
  down: "bg-red-500",
  unknown: "bg-zinc-500",
};

const STATUS_BORDER: Record<StatusType, string> = {
  healthy: "border-green-500/20",
  degraded: "border-amber-500/20",
  down: "border-red-500/20",
  unknown: "border-zinc-500/20",
};

const KNOWN_AGENTS = [
  {
    name: "FileFree — Social Content Generator",
    persona: "growth.mdc",
    schedule: "Daily 10am ET",
    output: "Notion + Postiz",
  },
  {
    name: "FileFree — Growth Content Writer",
    persona: "growth.mdc",
    schedule: "Mon/Wed/Fri 9am ET",
    output: "Notion",
  },
  {
    name: "FileFree — Weekly Strategy Check-in",
    persona: "strategy.mdc",
    schedule: "Monday 9am ET",
    output: "Notion",
  },
  {
    name: "FileFree — QA Security Scan",
    persona: "qa.mdc",
    schedule: "Daily 2am ET",
    output: "GitHub Issues",
  },
  {
    name: "FileFree — Partnership Outreach Drafter",
    persona: "strategy.mdc",
    schedule: "Tuesday 10am ET",
    output: "Notion",
  },
  {
    name: "FileFree — CPA Tax Review",
    persona: "cpa.mdc",
    schedule: "Weekly Thursday 3pm ET",
    output: "Notion",
  },
];

function StatusDot({ status }: { status: StatusType }) {
  return (
    <span className="relative flex h-3 w-3">
      {status === "healthy" && (
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
      )}
      <span
        className={`relative inline-flex h-3 w-3 rounded-full ${STATUS_COLORS[status]}`}
      />
    </span>
  );
}

function stripProtocol(url: string): string {
  return url.replace(/^https?:\/\//, "");
}

function ServiceCard({ service }: { service: ServiceCheck }) {
  const Icon = SERVICE_ICONS[service.name] || Server;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-xl border bg-card/50 p-4 ${STATUS_BORDER[service.status]}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-muted p-2">
            <Icon className="h-4 w-4 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">
              {service.name}
            </p>
            <p className="text-xs capitalize text-muted-foreground">
              {service.status}
            </p>
          </div>
        </div>
        <StatusDot status={service.status} />
      </div>

      {service.dashboardUrl && (
        <a
          href={service.dashboardUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 flex items-center gap-1.5 text-xs text-violet-400 transition hover:text-violet-300"
        >
          {stripProtocol(service.dashboardUrl)}
          <ExternalLink className="h-3 w-3" />
        </a>
      )}

      {service.accessHint && (
        <p className="mt-1 text-xs leading-snug text-muted-foreground/60">
          {service.accessHint}
        </p>
      )}

      {service.latencyMs !== null && (
        <p className="mt-2 text-xs text-muted-foreground">
          <span className="font-mono text-foreground">
            {service.latencyMs}ms
          </span>
        </p>
      )}

      {service.details && Object.keys(service.details).length > 0 && (
        <div className="mt-2 space-y-0.5">
          {Object.entries(service.details)
            .filter(([, v]) => v !== undefined && v !== null)
            .slice(0, 4)
            .map(([key, value]) => (
              <p key={key} className="text-xs text-muted-foreground">
                {key}:{" "}
                <span className="font-mono text-foreground/70">
                  {String(value)}
                </span>
              </p>
            ))}
        </div>
      )}
    </motion.div>
  );
}

function CIRunRow({ run }: { run: CIRun }) {
  const getIcon = () => {
    if (run.status === "in_progress" || run.status === "queued")
      return <Clock className="h-3.5 w-3.5 animate-spin text-amber-400" />;
    if (run.conclusion === "success")
      return <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />;
    if (run.conclusion === "failure")
      return <XCircle className="h-3.5 w-3.5 text-red-400" />;
    return <AlertTriangle className="h-3.5 w-3.5 text-zinc-400" />;
  };

  return (
    <div className="flex items-center justify-between border-b border-border/30 px-4 py-3 last:border-0">
      <div className="flex items-center gap-3">
        {getIcon()}
        <div>
          <p className="text-sm font-medium text-foreground">{run.name}</p>
          {run.updatedAt && (
            <p className="text-xs text-muted-foreground">
              {new Date(run.updatedAt).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            run.conclusion === "success"
              ? "bg-green-500/10 text-green-400"
              : run.conclusion === "failure"
                ? "bg-red-500/10 text-red-400"
                : "bg-zinc-500/10 text-zinc-400"
          }`}
        >
          {run.conclusion || run.status}
        </span>
        {run.url && (
          <a
            href={run.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted-foreground transition hover:text-foreground"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
    </div>
  );
}

function AgentRoster({ liveWorkflows }: { liveWorkflows: N8nWorkflow[] }) {
  const liveMap = new Map(
    liveWorkflows.map((w) => [w.name.toLowerCase(), w]),
  );

  return (
    <div className="overflow-hidden rounded-xl border border-border/50 bg-card/30">
      <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 border-b border-border/50 px-4 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        <span>Agent</span>
        <span className="hidden sm:block">Schedule</span>
        <span className="hidden sm:block">Output</span>
        <span>Status</span>
      </div>
      {KNOWN_AGENTS.map((agent) => {
        const live = liveMap.get(agent.name.toLowerCase());
        const isLive = live?.active ?? false;

        return (
          <div
            key={agent.name}
            className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-x-4 border-b border-border/30 px-4 py-3 last:border-0"
          >
            <div className="flex items-center gap-2">
              <Bot className="h-3.5 w-3.5 text-violet-400" />
              <div>
                <p className="text-sm font-medium text-foreground">
                  {agent.name.replace("FileFree — ", "")}
                </p>
                <p className="text-xs text-muted-foreground/60 sm:hidden">
                  {agent.schedule}
                </p>
              </div>
            </div>
            <div className="hidden items-center gap-1.5 sm:flex">
              <Calendar className="h-3 w-3 text-muted-foreground/50" />
              <span className="text-xs text-muted-foreground">
                {agent.schedule}
              </span>
            </div>
            <span className="hidden text-xs text-muted-foreground sm:block">
              {agent.output}
            </span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                isLive
                  ? "bg-green-500/10 text-green-400"
                  : "bg-zinc-500/10 text-zinc-400"
              }`}
            >
              {isLive ? "Active" : "Setup needed"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function ConnectionMap() {
  return (
    <div className="rounded-xl border border-border/50 bg-card/30 p-6">
      <h3 className="mb-4 text-sm font-semibold text-foreground">
        System Architecture
      </h3>
      <div className="space-y-4 text-xs">
        <div>
          <p className="mb-1.5 font-medium uppercase tracking-wider text-muted-foreground/60">
            User Flow
          </p>
          <div className="flex flex-wrap items-center gap-1.5 text-muted-foreground">
            <Globe className="h-3.5 w-3.5 text-violet-400" />
            <span>User</span>
            <ArrowRight className="h-3 w-3" />
            <span className="rounded bg-violet-500/10 px-1.5 py-0.5 text-violet-400">
              Vercel
            </span>
            <ArrowRight className="h-3 w-3" />
            <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-blue-400">
              Render API
            </span>
            <ArrowRight className="h-3 w-3" />
            <span className="rounded bg-green-500/10 px-1.5 py-0.5 text-green-400">
              Neon DB
            </span>
            <span className="text-muted-foreground/30">+</span>
            <span className="rounded bg-orange-500/10 px-1.5 py-0.5 text-orange-400">
              Upstash Redis
            </span>
          </div>
        </div>
        <div>
          <p className="mb-1.5 font-medium uppercase tracking-wider text-muted-foreground/60">
            AI Agents
          </p>
          <div className="flex flex-wrap items-center gap-1.5 text-muted-foreground">
            <Workflow className="h-3.5 w-3.5 text-amber-400" />
            <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-amber-400">
              n8n
            </span>
            <ArrowRight className="h-3 w-3" />
            <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-emerald-400">
              OpenAI
            </span>
            <span className="text-muted-foreground/30">+</span>
            <span className="text-foreground/60">Notion</span>
            <span className="text-muted-foreground/30">+</span>
            <span className="text-foreground/60">GitHub</span>
          </div>
        </div>
        <div>
          <p className="mb-1.5 font-medium uppercase tracking-wider text-muted-foreground/60">
            Social
          </p>
          <div className="flex flex-wrap items-center gap-1.5 text-muted-foreground">
            <Cpu className="h-3.5 w-3.5 text-pink-400" />
            <span className="rounded bg-pink-500/10 px-1.5 py-0.5 text-pink-400">
              Postiz
            </span>
            <ArrowRight className="h-3 w-3" />
            <span className="text-foreground/60">
              TikTok, Instagram, X, YouTube
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function CostSummary() {
  return (
    <div className="rounded-xl border border-border/50 bg-card/30 p-6">
      <h3 className="mb-3 text-sm font-semibold text-foreground">
        Monthly Burn
      </h3>
      <div className="space-y-2 text-xs">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Render Starter</span>
          <span className="font-mono text-foreground">$7.00</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Hetzner CX33</span>
          <span className="font-mono text-foreground">$5.49</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">
            Vercel / Neon / Upstash
          </span>
          <span className="font-mono text-green-400">Free tier</span>
        </div>
        <div className="flex justify-between border-t border-border/30 pt-2">
          <span className="font-medium text-foreground">Total</span>
          <span className="font-mono font-medium text-foreground">
            $12.49/mo
          </span>
        </div>
      </div>
    </div>
  );
}

export default function OpsPage() {
  const [data, setData] = useState<OpsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOps = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/ops", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as OpsData;
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOps();
    const interval = setInterval(fetchOps, 30_000);
    return () => clearInterval(interval);
  }, [fetchOps]);

  const healthyCount =
    data?.services.filter((s) => s.status === "healthy").length ?? 0;
  const totalCount = data?.services.length ?? 0;
  const downCount =
    data?.services.filter((s) => s.status === "down").length ?? 0;
  const allHealthy = healthyCount === totalCount && totalCount > 0;

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-2">
          <Link
            href="/"
            className="text-sm text-muted-foreground transition hover:text-foreground"
          >
            &larr; Back to FileFree
          </Link>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
                Operations
              </span>{" "}
              Dashboard
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {data
                ? `${healthyCount}/${totalCount} services healthy${downCount > 0 ? ` · ${downCount} down` : ""}`
                : "Checking services..."}
            </p>
          </div>

          <div className="flex items-center gap-3">
            {allHealthy && (
              <div className="flex items-center gap-1.5 rounded-full border border-green-500/20 bg-green-500/10 px-3 py-1 text-xs font-medium text-green-400">
                <Shield className="h-3 w-3" />
                All Systems Operational
              </div>
            )}
            {downCount > 0 && (
              <div className="flex items-center gap-1.5 rounded-full border border-red-500/20 bg-red-500/10 px-3 py-1 text-xs font-medium text-red-400">
                <AlertTriangle className="h-3 w-3" />
                {downCount} Service{downCount > 1 ? "s" : ""} Down
              </div>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={fetchOps}
              disabled={loading}
            >
              <RefreshCw
                className={`mr-1.5 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
              />
              Refresh
            </Button>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-400">
            Failed to load ops data: {error}
          </div>
        )}

        <AnimatePresence mode="wait">
          {data && (
            <motion.div
              key="content"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-8 space-y-8"
            >
              <section>
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  Infrastructure
                </h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {data.services.map((service, i) => (
                    <motion.div
                      key={service.name}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.05 }}
                    >
                      <ServiceCard service={service} />
                    </motion.div>
                  ))}
                </div>
              </section>

              <section>
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  AI Agents (n8n Workflows)
                </h2>
                <AgentRoster liveWorkflows={data.workflows} />
                {data.workflows.length === 0 && (
                  <p className="mt-2 text-xs text-muted-foreground/60">
                    n8n API key not configured — showing expected agents.
                    Set N8N_API_KEY env var to see live status.
                  </p>
                )}
              </section>

              {data.ciRuns.length > 0 && (
                <section>
                  <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                    <span className="flex items-center gap-2">
                      <GitBranch className="h-4 w-4" />
                      Recent CI Runs (main)
                    </span>
                  </h2>
                  <div className="overflow-hidden rounded-xl border border-border/50 bg-card/30">
                    {data.ciRuns.map((run, i) => (
                      <CIRunRow key={`${run.name}-${i}`} run={run} />
                    ))}
                  </div>
                </section>
              )}

              <div className="grid gap-4 sm:grid-cols-2">
                <ConnectionMap />
                <CostSummary />
              </div>

              {data.checkedAt && (
                <p className="text-center text-xs text-muted-foreground/50">
                  Last checked:{" "}
                  {new Date(data.checkedAt).toLocaleTimeString("en-US", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                  {" \u00B7 "}Auto-refreshes every 30s
                </p>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {loading && !data && (
          <div className="mt-16 flex flex-col items-center">
            <RefreshCw className="h-8 w-8 animate-spin text-violet-500" />
            <p className="mt-4 text-sm text-muted-foreground">
              Checking all services...
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
