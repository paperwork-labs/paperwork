"use client";

import "@xyflow/react/dist/style.css";

import dagre from "dagre";
import type {
  ArchitectureLayerBand,
  DeployPlatformBadge,
} from "@/lib/architecture-graph-studio";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo } from "react";

const NODE_W = 252;
const NODE_H = 124;

export type DagTone =
  | "core"
  | "frontend"
  | "ops"
  | "data"
  | "execution"
  | "http"
  | "webhook"
  | "schedule"
  | "code"
  | "ai"
  | "default";

export type { ArchitectureLayerBand, DeployPlatformBadge };

export type CardNodeData = {
  label: string;
  tone: DagTone;
  subtitle?: string;
  pill?: string;
  status?: "green" | "amber" | "red" | "gray";
  /** Optional live DAG ring from Brain / Vercel signals (does not change layout). */
  liveFrame?: "emerald" | "amber" | "zinc" | "rose";
  /** Second line under subtitle for deploy + schedule hints. */
  liveSubtext?: string;
  /** Swimlane tint (architecture graph). */
  layerBand?: ArchitectureLayerBand;
  /** Hosting / console badge. */
  deployPlatform?: DeployPlatformBadge;
  /** Last production deploy (e.g. Vercel), when known. */
  deployRelative?: string | null;
  /** Cursor hint when parent handles in-app navigation. */
  navigable?: boolean;
  /** Layout for handle positions (matches graph direction). */
  handleLayout?: "horizontal" | "vertical";
  compact?: boolean;
};

const LIVE_FRAME_RING: Record<NonNullable<CardNodeData["liveFrame"]>, string> = {
  emerald: "ring-emerald-500/45 border-emerald-500/35 bg-emerald-500/[0.07]",
  amber: "ring-amber-500/45 border-amber-500/35 bg-amber-500/[0.07]",
  zinc: "ring-zinc-500/40 border-zinc-600/45 bg-zinc-800/35",
  rose: "ring-rose-500/45 border-rose-500/35 bg-rose-500/[0.07]",
};

const TONE_RING: Record<DagTone, string> = {
  core: "ring-emerald-500/35 border-emerald-500/30 bg-emerald-500/[0.06]",
  frontend: "ring-indigo-500/35 border-indigo-500/30 bg-indigo-500/[0.06]",
  ops: "ring-amber-500/35 border-amber-500/30 bg-amber-500/[0.06]",
  data: "ring-violet-500/35 border-violet-500/30 bg-violet-500/[0.06]",
  execution: "ring-orange-500/35 border-orange-500/30 bg-orange-500/[0.06]",
  http: "ring-sky-500/35 border-sky-500/30 bg-sky-500/[0.06]",
  webhook: "ring-emerald-500/35 border-emerald-500/30 bg-emerald-500/[0.06]",
  schedule: "ring-amber-500/35 border-amber-500/30 bg-amber-500/[0.06]",
  code: "ring-zinc-500/40 border-zinc-600/50 bg-zinc-800/40",
  ai: "ring-violet-500/35 border-violet-500/30 bg-violet-500/[0.08]",
  default: "ring-zinc-600/40 border-zinc-700/60 bg-zinc-900/50",
};

const STATUS_DOT: Record<NonNullable<CardNodeData["status"]>, string> = {
  green: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]",
  amber: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)]",
  red: "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.7)]",
  gray: "bg-zinc-600",
};

const LAYER_BAND_SURFACE: Record<ArchitectureLayerBand, string> = {
  frontend:
    "bg-gradient-to-br from-indigo-950/[0.42] via-indigo-950/[0.14] to-transparent",
  api: "bg-gradient-to-br from-sky-950/[0.38] via-sky-950/[0.12] to-transparent",
  workers:
    "bg-gradient-to-br from-orange-950/[0.4] via-orange-950/[0.14] to-transparent",
  database:
    "bg-gradient-to-br from-violet-950/[0.42] via-violet-950/[0.14] to-transparent",
  ops: "bg-gradient-to-br from-zinc-800/[0.45] via-zinc-900/[0.2] to-transparent",
};

const PLATFORM_BADGE: Record<
  DeployPlatformBadge,
  { label: string; className: string }
> = {
  vercel: {
    label: "Vercel",
    className:
      "border-black/20 bg-zinc-100 text-zinc-900 ring-1 ring-white/30 dark:bg-zinc-950 dark:text-zinc-50 dark:ring-zinc-700",
  },
  render: {
    label: "Render",
    className: "border-emerald-900/50 bg-emerald-950/75 text-emerald-100 ring-1 ring-emerald-700/40",
  },
  neon: {
    label: "Neon",
    className: "border-emerald-900/40 bg-emerald-950/55 text-emerald-50 ring-1 ring-emerald-600/35",
  },
  upstash: {
    label: "Upstash",
    className: "border-violet-900/45 bg-violet-950/65 text-violet-100 ring-1 ring-violet-600/35",
  },
  github: {
    label: "GitHub",
    className: "border-zinc-600/50 bg-zinc-900/90 text-zinc-100 ring-1 ring-zinc-500/30",
  },
  hetzner: {
    label: "Hetzner",
    className: "border-red-900/40 bg-red-950/55 text-red-100 ring-1 ring-red-700/35",
  },
};

function NodeCard({ data, selected }: NodeProps<Node<CardNodeData, "card">>) {
  const vertical = data.handleLayout === "vertical";
  const targetPos = vertical ? Position.Top : Position.Left;
  const sourcePos = vertical ? Position.Bottom : Position.Right;
  const tone = data.tone in TONE_RING ? data.tone : "default";
  const baseRing = TONE_RING[tone];
  const ring = data.liveFrame ? LIVE_FRAME_RING[data.liveFrame] : baseRing;
  const compact = data.compact ?? false;
  const layerBand = data.layerBand;
  const bandSurface =
    layerBand && layerBand in LAYER_BAND_SURFACE
      ? LAYER_BAND_SURFACE[layerBand]
      : "";
  const statusKey = data.status ?? "gray";
  const platformMeta = data.deployPlatform
    ? PLATFORM_BADGE[data.deployPlatform]
    : null;

  return (
    <div
      className={[
        "relative overflow-hidden rounded-lg border px-3 py-2 shadow-sm ring-1 transition-colors",
        ring,
        bandSurface,
        selected ? "ring-2 ring-zinc-300/50" : "hover:border-zinc-600/80",
        data.navigable ? "cursor-pointer" : "",
        compact ? "min-w-[160px] max-w-[200px]" : "min-w-[218px] max-w-[268px]",
      ].join(" ")}
    >
      <Handle
        type="target"
        position={targetPos}
        className="!h-2 !w-2 !border-0 !bg-zinc-500"
      />
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span
              className={`inline-block h-2 w-2 shrink-0 rounded-full ${STATUS_DOT[statusKey]}`}
              title={
                statusKey === "gray"
                  ? "Health not probed or no endpoint"
                  : `Status: ${statusKey}`
              }
            />
            <span
              className={`truncate font-medium text-zinc-100 ${compact ? "text-[11px] leading-tight" : "text-xs"}`}
            >
              {data.label}
            </span>
          </div>
          {data.subtitle && (
            <p
              className={`mt-0.5 truncate font-mono text-zinc-500 ${compact ? "text-[9px]" : "text-[10px]"}`}
            >
              {data.subtitle}
            </p>
          )}
          {data.liveSubtext && (
            <p
              className={`mt-0.5 line-clamp-2 text-zinc-500 ${compact ? "text-[8px] leading-tight" : "text-[9px] leading-snug"}`}
            >
              {data.liveSubtext}
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {platformMeta && (
            <span
              className={`rounded px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wide ${platformMeta.className}`}
            >
              {platformMeta.label}
            </span>
          )}
          {data.pill && (
            <span className="rounded-full border border-zinc-700/80 bg-zinc-950/60 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-zinc-400">
              {data.pill}
            </span>
          )}
        </div>
      </div>
      {data.deployRelative != null && data.deployRelative !== "" && (
        <p
          className={`mt-1 truncate font-mono text-zinc-400 ${compact ? "text-[8px]" : "text-[9px]"}`}
        >
          Deploy{" "}
          {data.deployRelative === "unknown" ? (
            <span className="text-zinc-500">unknown</span>
          ) : (
            data.deployRelative
          )}
        </p>
      )}
      <Handle
        type="source"
        position={sourcePos}
        className="!h-2 !w-2 !border-0 !bg-zinc-500"
      />
    </div>
  );
}

const nodeTypes = { card: NodeCard };

function layoutWithDagre(
  nodes: Node<CardNodeData, "card">[],
  edges: Edge[],
  direction: "TB" | "LR",
): Node<CardNodeData, "card">[] {
  if (nodes.length === 0) return nodes;

  const g = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: direction,
    nodesep: direction === "LR" ? 56 : 48,
    ranksep: direction === "LR" ? 80 : 64,
    marginx: 28,
    marginy: 28,
  });

  for (const n of nodes) {
    g.setNode(n.id, { width: NODE_W, height: NODE_H });
  }
  for (const e of edges) {
    if (g.hasNode(e.source) && g.hasNode(e.target)) {
      g.setEdge(e.source, e.target);
    }
  }

  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    if (!pos) {
      return { ...n, position: n.position ?? { x: 0, y: 0 } };
    }
    return {
      ...n,
      position: {
        x: pos.x - NODE_W / 2,
        y: pos.y - NODE_H / 2,
      },
    };
  });
}

function DagFitView({
  padding,
  minZoom,
  revision,
}: {
  padding: number;
  minZoom?: number;
  revision: number;
}) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const t = requestAnimationFrame(() => {
      fitView({
        padding,
        duration: 220,
        ...(typeof minZoom === "number" ? { minZoom } : {}),
      });
    });
    return () => cancelAnimationFrame(t);
  }, [fitView, padding, minZoom, revision]);
  return null;
}

export type InteractiveDagProps = {
  nodes: Node<CardNodeData, "card">[];
  edges: Edge[];
  direction?: "TB" | "LR";
  className?: string;
  onNodeClick?: (event: React.MouseEvent, node: Node<CardNodeData, "card">) => void;
  showMiniMap?: boolean;
  fitViewPadding?: number;
  /** Minimum zoom after fit — keeps the graph readable (architecture DAG). */
  fitMinZoom?: number;
  /** Subtle motion on edges (disable for very busy workflow graphs). */
  animateEdges?: boolean;
};

const EDGE_MARKER = {
  type: MarkerType.ArrowClosed,
  width: 16,
  height: 16,
  color: "rgb(161 161 170)",
} as const;

export function InteractiveDag({
  nodes: inputNodes,
  edges: inputEdges,
  direction = "LR",
  className = "",
  onNodeClick,
  showMiniMap = true,
  fitViewPadding = 0.06,
  fitMinZoom,
  animateEdges = true,
}: InteractiveDagProps) {
  const handleLayout: "horizontal" | "vertical" =
    direction === "TB" ? "vertical" : "horizontal";

  const preparedNodes = useMemo(
    () =>
      inputNodes.map((n) => ({
        ...n,
        type: "card" as const,
        data: {
          ...n.data,
          handleLayout,
        },
      })),
    [inputNodes, handleLayout],
  );

  const laidOut = useMemo(
    () => layoutWithDagre(preparedNodes, inputEdges, direction),
    [preparedNodes, inputEdges, direction],
  );

  const flowEdges = useMemo(
    () =>
      inputEdges.map((e) => ({
        ...e,
        animated: animateEdges,
        markerEnd: e.markerEnd ?? EDGE_MARKER,
        style: {
          stroke: "rgb(139 139 150)",
          strokeWidth: 1.35,
          ...e.style,
        },
      })),
    [inputEdges, animateEdges],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(laidOut);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => {
    setNodes(layoutWithDagre(preparedNodes, inputEdges, direction));
  }, [preparedNodes, inputEdges, direction, setNodes]);

  useEffect(() => {
    setEdges(flowEdges);
  }, [flowEdges, setEdges]);

  const onNodeClickCb = useCallback(
    (event: React.MouseEvent, node: Node<CardNodeData, "card">) => {
      onNodeClick?.(event, node);
    },
    [onNodeClick],
  );

  return (
    <div
      className={`flex min-h-[280px] w-full flex-1 flex-col rounded-xl border border-zinc-800 bg-zinc-950 ${className}`}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClickCb}
        minZoom={0.28}
        maxZoom={2.15}
        defaultEdgeOptions={{
          animated: animateEdges,
          style: { stroke: "rgb(139 139 150)", strokeWidth: 1.35 },
          markerEnd: EDGE_MARKER,
        }}
        proOptions={{ hideAttribution: true }}
        className="!min-h-[260px] !flex-1 !bg-zinc-950"
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={18}
          size={1}
          color="rgb(63 63 70 / 0.35)"
        />
        <Controls
          className="!m-3 !overflow-hidden !rounded-lg !border !border-zinc-800 !bg-zinc-900/90 !shadow-lg [&_button]:!border-zinc-700 [&_button]:!bg-zinc-900 [&_button]:!text-zinc-200 [&_button:hover]:!bg-zinc-800"
        />
        {showMiniMap && (
          <MiniMap
            className="!m-3 !overflow-hidden !rounded-lg !border !border-zinc-800 !bg-zinc-900/85"
            maskColor="rgb(24 24 27 / 0.55)"
            nodeColor={() => "rgb(82 82 91)"}
          />
        )}
        <DagFitView
          padding={fitViewPadding}
          minZoom={fitMinZoom}
          revision={laidOut.length + inputEdges.length}
        />
      </ReactFlow>
    </div>
  );
}
