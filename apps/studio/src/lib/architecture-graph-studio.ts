import type { SystemNode } from "@/lib/system-graph";
import { NODE_VERCEL_PROJECT } from "@/lib/architecture-vercel-projects";

const KNOWN_PRODUCT_SLUGS = new Set([
  "axiomfolio",
  "filefree",
  "launchfree",
  "distill",
  "trinkets",
]);

export type ArchitectureLayerBand =
  | "frontend"
  | "api"
  | "workers"
  | "database"
  | "ops";

export type DeployPlatformBadge =
  | "vercel"
  | "render"
  | "neon"
  | "upstash"
  | "github"
  | "hetzner";

/**
 * In-app Studio route for architecture graph click-through.
 * Returns null when there is no sensible internal destination (Shift+click opens the drawer instead).
 */
export function studioPathForSystemNode(node: SystemNode): string | null {
  switch (node.id) {
    case "brain.api":
      return "/admin/brain/conversations";
    case "brain.mcp":
    case "brain.personas":
      return "/admin/brain/personas";
    case "studio.frontend":
      return "/admin";
    case "infra.n8n":
      return "/admin/workflows";
    case "infra.postgres":
    case "infra.redis":
    case "infra.vercel":
    case "infra.render":
      return "/admin/infrastructure";
    case "infra.github_actions":
      return "/admin/pr-pipeline";
    default:
      break;
  }
  if (KNOWN_PRODUCT_SLUGS.has(node.product)) {
    return `/admin/products/${node.product}`;
  }
  return null;
}

/** Visual swimlane grouping for DAG cards (Frontend / API / Workers / Database / Ops). */
export function layerBandForSystemNode(node: SystemNode): ArchitectureLayerBand {
  if (node.layer === "frontend" || node.id === "studio.frontend") return "frontend";
  if (node.kind === "api") return "api";
  if (node.id === "infra.postgres" || node.id === "infra.redis") return "database";
  if (node.layer === "infra" || node.layer === "platform") return "ops";
  return "workers";
}

/** Hosting / console badge for architecture nodes (best-effort from catalog + Vercel map). */
export function deployPlatformForSystemNode(
  node: SystemNode,
): DeployPlatformBadge | undefined {
  if (NODE_VERCEL_PROJECT[node.id]) return "vercel";
  if (node.id === "brain.api") return "render";
  if (node.id === "infra.postgres") return "neon";
  if (node.id === "infra.redis") return "upstash";
  if (node.id === "infra.vercel") return "vercel";
  if (node.id === "infra.render") return "render";
  if (node.id === "infra.github_actions") return "github";
  if (node.id === "infra.n8n") return "hetzner";
  if (node.kind === "api" && node.module_path.startsWith("apis/")) return "render";
  return undefined;
}
