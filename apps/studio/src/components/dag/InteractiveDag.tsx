"use client";

import "@xyflow/react/dist/style.css";

import dagre from "dagre";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
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

const NODE_W = 228;
const NODE_H = 92;

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

export type CardNodeData = {
  label: string;
  tone: DagTone;
  subtitle?: string;
  pill?: string;
  status?: "green" | "amber" | "red" | "gray";
  /** Layout for handle positions (matches graph direction). */
  handleLayout?: "horizontal" | "vertical";
  compact?: boolean;
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

function NodeCard({ data, selected }: NodeProps<Node<CardNodeData, "card">>) {
  const vertical = data.handleLayout === "vertical";
  const targetPos = vertical ? Position.Top : Position.Left;
  const sourcePos = vertical ? Position.Bottom : Position.Right;
  const tone = data.tone in TONE_RING ? data.tone : "default";
  const ring = TONE_RING[tone];
  const compact = data.compact ?? false;

  return (
    <div
      className={[
        "relative rounded-lg border px-3 py-2 shadow-sm ring-1 transition-colors",
        ring,
        selected ? "ring-2 ring-zinc-300/50" : "hover:border-zinc-600/80",
        compact ? "min-w-[160px] max-w-[200px]" : "min-w-[200px] max-w-[240px]",
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
            {data.status && (
              <span
                className={`inline-block h-2 w-2 shrink-0 rounded-full ${STATUS_DOT[data.status]}`}
              />
            )}
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
        </div>
        {data.pill && (
          <span className="shrink-0 rounded-full border border-zinc-700/80 bg-zinc-950/60 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-zinc-400">
            {data.pill}
          </span>
        )}
      </div>
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

function DagFitView({ padding, revision }: { padding: number; revision: number }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const t = requestAnimationFrame(() => {
      fitView({ padding, duration: 200 });
    });
    return () => cancelAnimationFrame(t);
  }, [fitView, padding, revision]);
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
};

export function InteractiveDag({
  nodes: inputNodes,
  edges: inputEdges,
  direction = "LR",
  className = "",
  onNodeClick,
  showMiniMap = true,
  fitViewPadding = 0.12,
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

  const [nodes, setNodes, onNodesChange] = useNodesState(laidOut);
  const [edges, setEdges, onEdgesChange] = useEdgesState(inputEdges);

  useEffect(() => {
    setNodes(layoutWithDagre(preparedNodes, inputEdges, direction));
  }, [preparedNodes, inputEdges, direction, setNodes]);

  useEffect(() => {
    setEdges(inputEdges);
  }, [inputEdges, setEdges]);

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
        minZoom={0.15}
        maxZoom={1.85}
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
        <DagFitView padding={fitViewPadding} revision={laidOut.length + inputEdges.length} />
      </ReactFlow>
    </div>
  );
}
