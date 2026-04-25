import rawGraph from "@/data/system-graph.json";

export type SystemLayer =
  | "bronze"
  | "silver"
  | "gold"
  | "execution"
  | "frontend"
  | "platform"
  | "infra";

export type SystemKind =
  | "api"
  | "worker"
  | "frontend"
  | "agent"
  | "mcp"
  | "infra"
  | "workflow"
  | "platform";

export type SystemSubgroup = {
  name: string;
  file_count: number;
  github_url: string;
};

export type SystemNode = {
  id: string;
  label: string;
  product: string;
  layer: SystemLayer;
  kind: SystemKind;
  module_path: string;
  github_url: string;
  description: string;
  depends_on: string[];
  health_url?: string;
  admin_url?: string;
  docs_url?: string;
  owner_persona?: string;
  llm_backed?: boolean;
  severity?: "critical" | "high" | "low";
  medallion_summary?: Partial<Record<SystemLayer, number>>;
  subgroups?: SystemSubgroup[];
};

export type SystemGraph = {
  generated_at: string;
  commit_sha: string;
  layers: SystemLayer[];
  nodes: SystemNode[];
};

export const systemGraph: SystemGraph = rawGraph as SystemGraph;

export const LAYER_LABELS: Record<SystemLayer, string> = {
  bronze: "Bronze",
  silver: "Silver",
  gold: "Gold",
  execution: "Execution",
  frontend: "Frontend",
  platform: "Platform",
  infra: "Infra",
};

export const LAYER_DESCRIPTIONS: Record<SystemLayer, string> = {
  bronze: "Raw external data + provider clients",
  silver: "Enriched, normalized, point-in-time",
  gold: "Decision-ready views + agent tools",
  execution: "Actions, orchestration, agents",
  frontend: "Customer UIs",
  platform: "Developer platform + command center",
  infra: "Managed services + hosting",
};

export type NodeHealth = {
  id: string;
  configured: boolean;
  healthy: boolean;
  status: "green" | "amber" | "red" | "gray";
  latencyMs: number | null;
  detail: string;
  checkedAt: string;
};

export async function probeNode(node: SystemNode): Promise<NodeHealth> {
  const checkedAt = new Date().toISOString();
  if (!node.health_url) {
    return {
      id: node.id,
      configured: false,
      healthy: false,
      status: "gray",
      latencyMs: null,
      detail: "No health endpoint",
      checkedAt,
    };
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 6000);
  try {
    const start = Date.now();
    const res = await fetch(node.health_url, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
    });
    const latencyMs = Date.now() - start;
    const healthy = res.ok;
    const status = healthy
      ? latencyMs > 3000
        ? "amber"
        : "green"
      : "red";
    return {
      id: node.id,
      configured: true,
      healthy,
      status,
      latencyMs,
      detail: healthy ? `HTTP ${res.status}` : `HTTP ${res.status}`,
      checkedAt,
    };
  } catch (err) {
    const detail =
      err instanceof DOMException && err.name === "AbortError"
        ? "Timeout (6s)"
        : "Unreachable";
    return {
      id: node.id,
      configured: true,
      healthy: false,
      status: "red",
      latencyMs: null,
      detail,
      checkedAt,
    };
  } finally {
    clearTimeout(timeout);
  }
}

export async function probeAll(graph: SystemGraph): Promise<NodeHealth[]> {
  return Promise.all(graph.nodes.map((n) => probeNode(n)));
}
