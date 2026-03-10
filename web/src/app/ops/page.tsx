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
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

interface ServiceCheck {
  name: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  latencyMs: number | null;
  details?: Record<string, unknown>;
  checkedAt: string;
}

interface N8nWorkflow {
  id: string;
  name: string;
  active: boolean;
  updatedAt: string;
}

interface OpsData {
  services: ServiceCheck[];
  workflows: N8nWorkflow[];
  checkedAt: string;
}

const SERVICE_ICONS: Record<string, typeof Server> = {
  "Render API": Server,
  "Vercel Frontend": Globe,
  n8n: Workflow,
  Postiz: Cpu,
  "Hetzner VPS": Database,
};

const STATUS_COLORS = {
  healthy: "bg-green-500",
  degraded: "bg-amber-500",
  down: "bg-red-500",
  unknown: "bg-zinc-500",
};

const STATUS_GLOW = {
  healthy: "shadow-green-500/20",
  degraded: "shadow-amber-500/20",
  down: "shadow-red-500/20",
  unknown: "shadow-zinc-500/20",
};

const STATUS_BORDER = {
  healthy: "border-green-500/20",
  degraded: "border-amber-500/20",
  down: "border-red-500/20",
  unknown: "border-zinc-500/20",
};

function StatusDot({ status }: { status: ServiceCheck["status"] }) {
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

function ServiceCard({ service }: { service: ServiceCheck }) {
  const Icon = SERVICE_ICONS[service.name] || Server;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-xl border bg-card/50 p-4 shadow-lg ${STATUS_BORDER[service.status]} ${STATUS_GLOW[service.status]}`}
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

      {service.latencyMs !== null && (
        <p className="mt-3 text-xs text-muted-foreground">
          Response:{" "}
          <span className="font-mono text-foreground">
            {service.latencyMs}ms
          </span>
        </p>
      )}

      {service.details && Object.keys(service.details).length > 0 && (
        <div className="mt-2 space-y-0.5">
          {Object.entries(service.details)
            .filter(([, v]) => v !== undefined)
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

function WorkflowRow({ workflow }: { workflow: N8nWorkflow }) {
  return (
    <div className="flex items-center justify-between border-b border-border/30 px-4 py-3 last:border-0">
      <div className="flex items-center gap-3">
        <StatusDot status={workflow.active ? "healthy" : "unknown"} />
        <div>
          <p className="text-sm font-medium text-foreground">{workflow.name}</p>
          {workflow.updatedAt && (
            <p className="text-xs text-muted-foreground">
              Updated{" "}
              {new Date(workflow.updatedAt).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          )}
        </div>
      </div>
      <span
        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
          workflow.active
            ? "bg-green-500/10 text-green-400"
            : "bg-zinc-500/10 text-zinc-400"
        }`}
      >
        {workflow.active ? "Active" : "Inactive"}
      </span>
    </div>
  );
}

function ConnectionMap() {
  return (
    <div className="rounded-xl border border-border/50 bg-card/30 p-6">
      <h3 className="mb-4 text-sm font-semibold text-foreground">
        System Architecture
      </h3>
      <div className="space-y-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <Globe className="h-3.5 w-3.5 text-violet-400" />
          <span>User</span>
          <ArrowRight className="h-3 w-3" />
          <span className="text-violet-400">Vercel</span>
          <ArrowRight className="h-3 w-3" />
          <span className="text-blue-400">Render API</span>
          <ArrowRight className="h-3 w-3" />
          <span className="text-green-400">Neon DB</span>
          <span className="text-muted-foreground/50">+</span>
          <span className="text-orange-400">Redis</span>
        </div>
        <div className="flex items-center gap-2">
          <Workflow className="h-3.5 w-3.5 text-amber-400" />
          <span>n8n</span>
          <ArrowRight className="h-3 w-3" />
          <span className="text-emerald-400">OpenAI</span>
          <span className="text-muted-foreground/50">+</span>
          <span className="text-foreground/60">Notion</span>
          <span className="text-muted-foreground/50">+</span>
          <span className="text-foreground/60">GitHub</span>
        </div>
        <div className="flex items-center gap-2">
          <Cpu className="h-3.5 w-3.5 text-pink-400" />
          <span>Postiz</span>
          <ArrowRight className="h-3 w-3" />
          <span className="text-foreground/60">
            TikTok, Instagram, X, YouTube
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
  const allHealthy = healthyCount === totalCount && totalCount > 0;

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-2">
          <Link
            href="/"
            className="text-sm text-muted-foreground transition hover:text-foreground"
          >
            &larr; Back to FileFree
          </Link>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
                Operations
              </span>{" "}
              Dashboard
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {data
                ? `${healthyCount}/${totalCount} services healthy`
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
                  Services
                </h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {data.services.map((service) => (
                    <ServiceCard key={service.name} service={service} />
                  ))}
                </div>
              </section>

              {data.workflows.length > 0 && (
                <section>
                  <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                    AI Agent Workflows (n8n)
                  </h2>
                  <div className="overflow-hidden rounded-xl border border-border/50 bg-card/30">
                    {data.workflows.map((workflow) => (
                      <WorkflowRow key={workflow.id} workflow={workflow} />
                    ))}
                  </div>
                </section>
              )}

              <section>
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  Connection Map
                </h2>
                <ConnectionMap />
              </section>

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
