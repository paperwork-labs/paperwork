"use client";

import { useMemo, useState } from "react";
import {
  ExternalLink,
  RefreshCw,
  MessagesSquare,
  X,
  Github,
  Activity,
  Sparkles,
  Workflow,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  type SystemGraph,
  type SystemNode,
  type NodeHealth,
  type SystemLayer,
  LAYER_LABELS,
  LAYER_DESCRIPTIONS,
} from "@/lib/system-graph";

type Props = {
  graph: SystemGraph;
  initialHealth: NodeHealth[];
  checkedAt: string;
};

const KIND_BADGE: Record<SystemNode["kind"], string> = {
  api: "API",
  worker: "Worker",
  frontend: "Web",
  agent: "Agent",
  mcp: "MCP",
  infra: "Infra",
  workflow: "Workflow",
  platform: "Platform",
};

function statusDot(status: NodeHealth["status"]) {
  const color =
    status === "green"
      ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"
      : status === "amber"
        ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]"
        : status === "red"
          ? "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.8)]"
          : "bg-zinc-600";
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} />;
}

function formatRelative(iso: string): string {
  const diffMs = Date.now() - Date.parse(iso);
  if (Number.isNaN(diffMs)) return "—";
  const s = Math.floor(diffMs / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
}

export default function ArchitectureClient({
  graph,
  initialHealth,
  checkedAt: initialCheckedAt,
}: Props) {
  const [health, setHealth] = useState(initialHealth);
  const [checkedAt, setCheckedAt] = useState(initialCheckedAt);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [askingId, setAskingId] = useState<string | null>(null);
  const [askResponse, setAskResponse] = useState<string>("");

  const nodesByLayer = useMemo(() => {
    const map = new Map<SystemLayer, SystemNode[]>();
    for (const layer of graph.layers) map.set(layer, []);
    for (const node of graph.nodes) {
      const arr = map.get(node.layer) ?? [];
      arr.push(node);
      map.set(node.layer, arr);
    }
    return map;
  }, [graph]);

  const healthById = useMemo(
    () => new Map(health.map((h) => [h.id, h])),
    [health],
  );

  const summary = useMemo(() => {
    const probed = health.filter((h) => h.configured);
    const green = probed.filter((h) => h.status === "green").length;
    return {
      total: graph.nodes.length,
      probed: probed.length,
      healthy: green,
      healthyPct:
        probed.length > 0 ? Math.round((green * 100) / probed.length) : 0,
    };
  }, [graph, health]);

  const selected = selectedId
    ? graph.nodes.find((n) => n.id === selectedId) ?? null
    : null;
  const selectedHealth = selected
    ? healthById.get(selected.id) ?? null
    : null;

  async function refresh() {
    setRefreshing(true);
    try {
      const res = await fetch("/api/admin/architecture", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as {
        health: NodeHealth[];
        checkedAt: string;
      };
      setHealth(data.health);
      setCheckedAt(data.checkedAt);
      setRefreshError(null);
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }

  async function askBrain(node: SystemNode) {
    setAskingId(node.id);
    setAskResponse("");
    try {
      const res = await fetch("/api/admin/architecture/ask-brain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          node_id: node.id,
          label: node.label,
          module_path: node.module_path,
          description: node.description,
        }),
      });
      if (!res.ok) {
        setAskResponse(`Brain returned ${res.status}. Check BRAIN_API_URL + BRAIN_API_SECRET.`);
        return;
      }
      const data = (await res.json()) as { response?: string; error?: string };
      setAskResponse(data.response ?? data.error ?? "No response");
    } catch (err) {
      setAskResponse(
        err instanceof Error ? err.message : "Ask-Brain request failed",
      );
    } finally {
      setAskingId(null);
    }
  }

  // Two-tier layout:
  //   Top row:  medallion data layers (bronze / silver / gold) — the conceptual
  //             frame. Three wide columns so service cards aren't squashed.
  //   Bottom:   operational layers (execution, frontend, platform, infra) as
  //             full-width swim-lanes — these aren't medallion stages, they're
  //             cross-cutting concerns and deserve their own row.
  const MEDALLION_LAYERS: SystemLayer[] = ["bronze", "silver", "gold"];
  const OPERATIONAL_LAYERS: SystemLayer[] = [
    "execution",
    "frontend",
    "platform",
    "infra",
  ];
  const medallionLayersShown = MEDALLION_LAYERS.filter(
    (l) => (nodesByLayer.get(l)?.length ?? 0) > 0,
  );
  const operationalLayersShown = OPERATIONAL_LAYERS.filter(
    (l) => (nodesByLayer.get(l)?.length ?? 0) > 0,
  );

  const renderCard = (node: SystemNode) => {
    const h = healthById.get(node.id);
    const hasHealth = h?.configured;
    return (
      <motion.button
        key={node.id}
        onClick={() => setSelectedId(node.id)}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        className="group flex h-full w-full flex-col rounded-lg border border-zinc-800 bg-zinc-900/80 p-3 text-left transition hover:border-zinc-700 hover:bg-zinc-800/80"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              {hasHealth && statusDot(h.status)}
              <span className="truncate text-sm font-medium text-zinc-100">
                {node.label}
              </span>
            </div>
            <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-zinc-500">
              <span>{KIND_BADGE[node.kind]}</span>
              <span className="opacity-50">·</span>
              <span className="truncate">{node.product}</span>
              {node.llm_backed && (
                <>
                  <span className="opacity-50">·</span>
                  <Sparkles className="h-3 w-3 text-amber-400" />
                </>
              )}
            </div>
          </div>
          {node.medallion_summary && (
            <div className="flex gap-1 text-[10px] font-mono text-zinc-500">
              {Object.entries(node.medallion_summary).map(([k, v]) => (
                <span key={k} className="rounded bg-zinc-800/60 px-1">
                  {k[0]}
                  {v}
                </span>
              ))}
            </div>
          )}
        </div>
        <p className="mt-2 line-clamp-2 text-[11px] text-zinc-400">
          {node.description}
        </p>
        {h && h.configured && (
          <div className="mt-auto flex items-center gap-1 pt-2 text-[10px] text-zinc-500">
            <Activity className="h-2.5 w-2.5" />
            <span className="truncate">{h.detail}</span>
            {h.latencyMs !== null && <span>· {h.latencyMs}ms</span>}
          </div>
        )}
      </motion.button>
    );
  };

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
            <Workflow className="h-3.5 w-3.5" /> Command center
          </div>
          <h1 className="text-2xl font-semibold text-zinc-100">
            Paperwork system architecture
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-400">
            Top row is the medallion data spine (bronze → silver → gold). Below
            sit the operational lanes that consume it — agents, frontends,
            platform, infra. Click any card for a zoomed-in detail view, deploys,
            source, and an “ask Brain” drawer.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="rounded-lg border border-zinc-800/80 bg-zinc-900/60 px-3 py-2 text-xs">
            <div className="text-zinc-500">Nodes</div>
            <div className="font-mono text-zinc-200">
              {summary.total} · {summary.healthy}/{summary.probed} healthy ·{" "}
              {summary.healthyPct}%
            </div>
          </div>
          <button
            onClick={refresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-800/80 bg-zinc-900/60 px-3 py-2 text-xs text-zinc-300 transition hover:border-zinc-700 hover:bg-zinc-800/70 disabled:opacity-50"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
            />
            {refreshing ? "Probing…" : "Refresh health"}
          </button>
          <div className="text-xs text-zinc-500">
            Checked {formatRelative(checkedAt)} · commit{" "}
            <span className="font-mono text-zinc-400">{graph.commit_sha}</span>
          </div>
          {refreshError && (
            <div className="rounded-full border border-rose-800/40 bg-rose-950/20 px-2 py-0.5 text-xs text-rose-300">
              Health probe failed: {refreshError}
            </div>
          )}
        </div>
      </header>

      {medallionLayersShown.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-baseline justify-between">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-widest text-zinc-300">
                Medallion data layers
              </h2>
              <p className="mt-1 text-[11px] text-zinc-500">
                Bronze → silver → gold. The shape of the data spine.
              </p>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {medallionLayersShown.map((layer) => {
              const nodes = nodesByLayer.get(layer) ?? [];
              return (
                <section
                  key={layer}
                  className="flex flex-col gap-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4"
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-zinc-100">
                        {LAYER_LABELS[layer]}
                      </div>
                      <span className="text-[10px] font-mono text-zinc-500">
                        {nodes.length} {nodes.length === 1 ? "service" : "services"}
                      </span>
                    </div>
                    <div className="mt-0.5 text-[11px] leading-tight text-zinc-500">
                      {LAYER_DESCRIPTIONS[layer]}
                    </div>
                  </div>
                  <div className="grid gap-2">{nodes.map(renderCard)}</div>
                </section>
              );
            })}
          </div>
        </section>
      )}

      {operationalLayersShown.length > 0 && (
        <section className="space-y-3">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-widest text-zinc-300">
              Operational lanes
            </h2>
            <p className="mt-1 text-[11px] text-zinc-500">
              Cross-cutting consumers — agents, customer UIs, platform, hosting.
            </p>
          </div>
          <div className="space-y-3">
            {operationalLayersShown.map((layer) => {
              const nodes = nodesByLayer.get(layer) ?? [];
              return (
                <section
                  key={layer}
                  className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4"
                >
                  <div className="mb-3 flex items-baseline justify-between">
                    <div>
                      <div className="text-sm font-semibold text-zinc-100">
                        {LAYER_LABELS[layer]}
                      </div>
                      <div className="mt-0.5 text-[11px] leading-tight text-zinc-500">
                        {LAYER_DESCRIPTIONS[layer]}
                      </div>
                    </div>
                    <span className="text-[10px] font-mono text-zinc-500">
                      {nodes.length} {nodes.length === 1 ? "service" : "services"}
                    </span>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {nodes.map(renderCard)}
                  </div>
                </section>
              );
            })}
          </div>
        </section>
      )}

      <AnimatePresence>
        {selected && (
          <>
            <motion.div
              key="overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedId(null)}
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            />
            <motion.aside
              key="drawer"
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 260 }}
              className="fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col border-l border-zinc-800 bg-zinc-950 shadow-2xl"
            >
              <header className="flex items-start justify-between gap-4 border-b border-zinc-800 p-5">
                <div className="min-w-0">
                  <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-widest text-zinc-500">
                    {KIND_BADGE[selected.kind]} · {LAYER_LABELS[selected.layer]}
                  </div>
                  <h2 className="text-lg font-semibold text-zinc-100">
                    {selected.label}
                  </h2>
                  <p className="mt-1 text-xs text-zinc-500">
                    {selected.product} · {selected.module_path}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedId(null)}
                  className="rounded-md p-1 text-zinc-500 transition hover:bg-zinc-800 hover:text-zinc-200"
                >
                  <X className="h-4 w-4" />
                </button>
              </header>

              <div className="flex-1 space-y-5 overflow-y-auto p-5">
                <section>
                  <div className="mb-1 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    Description
                  </div>
                  <p className="text-sm leading-relaxed text-zinc-300">
                    {selected.description}
                  </p>
                </section>

                {selectedHealth?.configured && (
                  <section>
                    <div className="mb-1 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                      Health
                    </div>
                    <div className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 text-sm">
                      {statusDot(selectedHealth.status)}
                      <span className="text-zinc-200">
                        {selectedHealth.detail}
                      </span>
                      {selectedHealth.latencyMs !== null && (
                        <span className="text-zinc-500">
                          · {selectedHealth.latencyMs}ms
                        </span>
                      )}
                    </div>
                  </section>
                )}

                {selected.medallion_summary && (
                  <section>
                    <div className="mb-1 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                      Medallion files
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs">
                      {Object.entries(selected.medallion_summary).map(
                        ([layer, count]) => (
                          <span
                            key={layer}
                            className="rounded-md border border-zinc-800 bg-zinc-900/60 px-2 py-1 font-mono text-zinc-300"
                          >
                            {layer}: {count}
                          </span>
                        ),
                      )}
                    </div>
                  </section>
                )}

                {selected.depends_on.length > 0 && (
                  <section>
                    <div className="mb-1 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                      Depends on
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {selected.depends_on.map((dep) => (
                        <button
                          key={dep}
                          onClick={() => setSelectedId(dep)}
                          className="rounded-md border border-zinc-800 bg-zinc-900/60 px-2 py-1 font-mono text-[11px] text-zinc-300 transition hover:border-zinc-700 hover:bg-zinc-800/70"
                        >
                          {dep}
                        </button>
                      ))}
                    </div>
                  </section>
                )}

                <section>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    Links
                  </div>
                  <div className="space-y-1.5">
                    <a
                      href={selected.github_url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-700 hover:bg-zinc-800/60"
                    >
                      <Github className="h-3.5 w-3.5" /> Source on GitHub
                      <ExternalLink className="ml-auto h-3 w-3 opacity-60" />
                    </a>
                    {selected.admin_url && (
                      <a
                        href={
                          selected.admin_url +
                          (selected.admin_url.includes("?") ? "&" : "?") +
                          `focus=${encodeURIComponent(selected.id)}`
                        }
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-700 hover:bg-zinc-800/60"
                      >
                        <Workflow className="h-3.5 w-3.5" /> Product admin
                        <ExternalLink className="ml-auto h-3 w-3 opacity-60" />
                      </a>
                    )}
                    {selected.health_url && (
                      <a
                        href={selected.health_url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-700 hover:bg-zinc-800/60"
                      >
                        <Activity className="h-3.5 w-3.5" /> Health endpoint
                        <ExternalLink className="ml-auto h-3 w-3 opacity-60" />
                      </a>
                    )}
                    {selected.owner_persona && (
                      <a
                        href={`https://github.com/paperwork-labs/paperwork/blob/main/.cursor/rules/${selected.owner_persona}.mdc`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-700 hover:bg-zinc-800/60"
                      >
                        <Sparkles className="h-3.5 w-3.5" /> Owner persona:{" "}
                        <span className="font-mono">{selected.owner_persona}</span>
                        <ExternalLink className="ml-auto h-3 w-3 opacity-60" />
                      </a>
                    )}
                  </div>
                </section>

                <section>
                  <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    <span>Ask Brain</span>
                    <button
                      onClick={() => askBrain(selected)}
                      disabled={askingId === selected.id}
                      className="flex items-center gap-1 rounded-md border border-zinc-800 bg-zinc-900/60 px-2 py-1 text-[11px] normal-case tracking-normal text-zinc-200 transition hover:border-zinc-700 hover:bg-zinc-800/70 disabled:opacity-50"
                    >
                      <MessagesSquare className="h-3 w-3" />
                      {askingId === selected.id ? "Asking…" : "Explain this"}
                    </button>
                  </div>
                  {askResponse ? (
                    <pre className="whitespace-pre-wrap rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 text-xs leading-relaxed text-zinc-300">
                      {askResponse}
                    </pre>
                  ) : (
                    <p className="text-xs text-zinc-600">
                      Brain will read the node’s source + memory and explain
                      what it does, what depends on it, and recent activity.
                    </p>
                  )}
                </section>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
