"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import type { ForceGraphMethods } from "react-force-graph-2d";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import type { HubDocCategory } from "@/lib/doc-metadata";
import { HUB_CATEGORY_LABEL } from "@/lib/doc-metadata";
import {
  isKnowHotZoneNode,
  KNOW_CATEGORY_HEX,
  KNOW_GRAPH_CATEGORY_FILTERS,
  KNOW_HOT_ZONE_MIN_LINKS,
  type KnowledgeGraphVizNode,
  type KnowledgeGraphVizPayload,
} from "@/lib/knowledge-graph-viz";

type FGNode = KnowledgeGraphVizNode & { x?: number; y?: number };

const ForceGraph2D = dynamic(
  async () => (await import("react-force-graph-2d")).default,
  { ssr: false }
);

const GRAPH_HEIGHT = 480;

function nodeVal(n: KnowledgeGraphVizNode): number {
  return Math.max(1, n.links_in);
}

function nodeCanvasRadius(n: KnowledgeGraphVizNode): number {
  return Math.sqrt(nodeVal(n)) * 3 + 2;
}

export type DocsKnowledgeGraphClientProps = {
  payload: KnowledgeGraphVizPayload;
};

export function DocsKnowledgeGraphClient({ payload }: DocsKnowledgeGraphClientProps) {
  const router = useRouter();
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const rafRefreshRef = useRef<number | null>(null);
  const [graphWidth, setGraphWidth] = useState(960);

  const scheduleRefresh = useCallback(() => {
    if (rafRefreshRef.current != null) return;
    rafRefreshRef.current = requestAnimationFrame(() => {
      rafRefreshRef.current = null;
      (fgRef.current as { refresh?: () => void } | undefined)?.refresh?.();
    });
  }, []);

  const raw = payload;
  const [hiddenCategories, setHiddenCategories] = useState<Set<HubDocCategory>>(() => new Set());
  const [search, setSearch] = useState("");

  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      requestAnimationFrame(() => {
        const w = el.getBoundingClientRect().width;
        setGraphWidth(Math.max(280, Math.floor(w)));
        scheduleRefresh();
      });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [scheduleRefresh]);

  useEffect(() => {
    scheduleRefresh();
  }, [hiddenCategories, search, raw, graphWidth, scheduleRefresh]);

  const { activeNodes, activeLinks } = useMemo(() => {
    if (!raw.nodes.length) {
      return { activeNodes: [] as KnowledgeGraphVizNode[], activeLinks: [] as KnowledgeGraphVizPayload["links"] };
    }
    const nodes = raw.nodes.filter((n) => !hiddenCategories.has(n.category));
    const ids = new Set(nodes.map((n) => n.id));
    const links = raw.links.filter((l) => ids.has(l.source) && ids.has(l.target));
    return { activeNodes: nodes, activeLinks: links };
  }, [raw, hiddenCategories]);

  const searchNeedle = search.trim().toLowerCase();
  const matchIds = useMemo(() => {
    if (!searchNeedle) return null as Set<string> | null;
    const s = new Set<string>();
    for (const n of activeNodes) {
      if (n.title.toLowerCase().includes(searchNeedle) || n.slug.toLowerCase().includes(searchNeedle)) {
        s.add(n.id);
      }
    }
    return s;
  }, [activeNodes, searchNeedle]);

  const graphData = useMemo(
    () => ({
      nodes: activeNodes as FGNode[],
      links: activeLinks.map((l) => ({ ...l })),
    }),
    [activeNodes, activeLinks]
  );

  const toggleCategory = useCallback((id: HubDocCategory) => {
    setHiddenCategories((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  if (!raw.nodes.length) {
    return (
      <HqEmptyState
        title="No graph data yet"
        description="Add nodes and links to src/data/knowledge-graph.json."
        action={{ label: "Back to docs", href: "/admin/docs" }}
      />
    );
  }

  if (!activeNodes.length) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-zinc-500">All categories are hidden — turn at least one category on.</p>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Category filters">
          {KNOW_GRAPH_CATEGORY_FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              aria-pressed={!hiddenCategories.has(f.id)}
              onClick={() => toggleCategory(f.id)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                !hiddenCategories.has(f.id)
                  ? "bg-sky-500/20 text-sky-200 ring-1 ring-sky-500/40"
                  : "bg-zinc-800/80 text-zinc-500 line-through"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Highlight nodes by title or slug…"
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900/60 py-2 pl-9 pr-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-sky-500/50"
            aria-label="Search nodes"
          />
        </div>
        <div
          className="flex flex-wrap items-center gap-2 rounded-lg border border-rose-500/25 bg-rose-500/5 px-3 py-2 text-[11px] text-rose-200/90"
          title="Nodes that are stale yet heavily linked — review soon."
        >
          <span className="font-semibold uppercase tracking-wide text-rose-300/90">Hot zones</span>
          <span className="text-zinc-400">
            Stale + {KNOW_HOT_ZONE_MIN_LINKS}+ inbound links (visible: {activeNodes.filter(isKnowHotZoneNode).length})
          </span>
        </div>
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Category visibility">
        {KNOW_GRAPH_CATEGORY_FILTERS.map((f) => {
          const on = !hiddenCategories.has(f.id);
          return (
            <button
              key={f.id}
              type="button"
              data-testid={`knowledge-graph-filter-${f.id}`}
              aria-pressed={on}
              onClick={() => toggleCategory(f.id)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                on
                  ? "bg-sky-500/20 text-sky-200 ring-1 ring-sky-500/40"
                  : "bg-zinc-800/80 text-zinc-500 line-through"
              }`}
            >
              {f.label}
            </button>
          );
        })}
      </div>

      <div
        ref={wrapRef}
        className="relative w-full overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-950"
      >
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          backgroundColor="rgba(9, 9, 11, 0.95)"
          width={graphWidth}
          height={GRAPH_HEIGHT}
          nodeId="id"
          nodeVal={(n) => nodeVal(n as KnowledgeGraphVizNode)}
          nodeRelSize={5}
          nodeLabel={(n) => {
            const node = n as KnowledgeGraphVizNode;
            const cat = HUB_CATEGORY_LABEL[node.category] ?? node.category;
            return `${node.title}\n${cat}\n${node.read_minutes} min read`;
          }}
          nodeColor={(n) => {
            const node = n as KnowledgeGraphVizNode;
            const base = KNOW_CATEGORY_HEX[node.category] ?? KNOW_CATEGORY_HEX.uncategorized;
            if (matchIds && matchIds.has(node.id)) return "#facc15";
            return base;
          }}
          linkColor={() => "rgba(113, 113, 122, 0.35)"}
          linkWidth={0.8}
          cooldownTicks={120}
          onEngineStop={scheduleRefresh}
          onNodeClick={(n) => {
            const node = n as KnowledgeGraphVizNode;
            router.push(`/admin/docs/${encodeURIComponent(node.slug)}`);
          }}
          nodePointerAreaPaint={(n, color, ctx, globalScale) => {
            const node = n as FGNode;
            if (node.x === undefined || node.y === undefined) return;
            const r = nodeCanvasRadius(node) / globalScale;
            const ringPad =
              (matchIds?.has(node.id) ? 8 : 0) +
              (isKnowHotZoneNode(node as KnowledgeGraphVizNode) ? 12 : 4);
            const hitR = r + ringPad / globalScale;
            ctx.beginPath();
            ctx.arc(node.x, node.y, hitR, 0, 2 * Math.PI, false);
            ctx.fillStyle = color;
            ctx.fill();
          }}
          nodeCanvasObjectMode={() => "after"}
          nodeCanvasObject={(n, ctx, globalScale) => {
            const node = n as FGNode;
            if (node.x === undefined || node.y === undefined) return;
            const r = nodeCanvasRadius(node) / globalScale;
            if (matchIds?.has(node.id)) {
              ctx.beginPath();
              ctx.arc(node.x, node.y, r + 6 / globalScale, 0, 2 * Math.PI);
              ctx.strokeStyle = "rgba(250, 204, 21, 0.85)";
              ctx.lineWidth = 2.5 / globalScale;
              ctx.stroke();
            }
            if (isKnowHotZoneNode(node)) {
              ctx.beginPath();
              ctx.arc(node.x, node.y, r + 10 / globalScale, 0, 2 * Math.PI);
              ctx.strokeStyle = "rgba(244, 63, 94, 0.75)";
              ctx.lineWidth = 2 / globalScale;
              ctx.setLineDash([4 / globalScale, 3 / globalScale]);
              ctx.stroke();
              ctx.setLineDash([]);
            }
          }}
        />
      </div>
    </div>
  );
}
