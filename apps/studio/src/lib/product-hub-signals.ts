/**
 * Wiring status for product hub tabs and metric rows (WS-82 PR-4a).
 * Maps to CSS vars: --status-success | --status-warning | --status-danger | muted.
 */

import type { EpicHierarchyResponse } from "@/lib/brain-client";
import type { ProductHealthBrainState, HeroRollup } from "@/lib/product-health-brain";
import { deriveHeroRollup } from "@/lib/product-health-brain";
import type { DocEntry } from "@/lib/docs";
import type { ProductRegistryEntry } from "@/lib/products-registry";
import { getLatestReleaseShippedIso } from "@/lib/products-registry";

export type HubSignalKind = "success" | "warning" | "danger" | "muted";

export function combineSignals(levels: HubSignalKind[]): HubSignalKind {
  if (levels.includes("danger")) return "danger";
  if (levels.includes("warning")) return "warning";
  if (levels.includes("success")) return "success";
  return "muted";
}

export function filterEpicsForProductSlug(
  hierarchy: EpicHierarchyResponse | null,
  slug: string,
): { goals: EpicHierarchyResponse } {
  if (!hierarchy?.length) return { goals: [] };
  const lower = slug.trim().toLowerCase();
  const goals: EpicHierarchyResponse = [];
  for (const g of hierarchy) {
    const epics = g.epics.filter((e) => {
      const bt = (e.brief_tag || "").trim().toLowerCase();
      const ps = (e.product_slug || "").trim().toLowerCase();
      return bt === lower || ps === lower;
    });
    if (epics.length) {
      goals.push({ ...g, epics });
    }
  }
  return { goals };
}

export function countFilteredEpics(goals: EpicHierarchyResponse): number {
  return goals.reduce((n, g) => n + g.epics.length, 0);
}

export function filterDocEntriesForProduct(
  entries: DocEntry[],
  product: ProductRegistryEntry,
): DocEntry[] {
  const slugLower = product.slug.toLowerCase();
  const tagMatches = entries.filter((e) =>
    e.tags.some((t) => t.trim().toLowerCase() === slugLower),
  );
  if (tagMatches.length > 0) return tagMatches;
  const nameLower = product.name.toLowerCase();
  return entries.filter((e) => {
    const p = e.path.toLowerCase();
    return p.includes(slugLower) || p.includes(nameLower);
  });
}

export type ProductPlansLoadResult = {
  hierarchy: EpicHierarchyResponse | null;
  /** Brain URL/secret missing */
  configured: boolean;
  /** Set when configured but fetch failed */
  fetchError: string | null;
};

export function plansTabSignal(
  res: ProductPlansLoadResult,
  filteredEpicCount: number,
): HubSignalKind {
  if (!res.configured) return "muted";
  if (res.fetchError) return "danger";
  if (filteredEpicCount > 0) return "success";
  return "muted";
}

export function healthTabSignal(state: ProductHealthBrainState, rollup: HeroRollup): HubSignalKind {
  if (!state.brainConfigured) return "muted";
  if (state.brainDataPlaneError) return "danger";
  if (rollup === "down") return "danger";
  if (rollup === "degraded" || rollup === "unknown") return "warning";
  return "success";
}

export function docsTabSignal(docCount: number): HubSignalKind {
  if (docCount > 0) return "success";
  return "muted";
}

export function gtmTabSignal(): HubSignalKind {
  return "muted";
}

function metricOpenIssuesSignal(openIssues: number | null): HubSignalKind {
  if (openIssues === null) return "muted";
  return "success";
}

function metricLastShippedSignal(product: ProductRegistryEntry): HubSignalKind {
  return getLatestReleaseShippedIso(product) ? "success" : "muted";
}

/** Registry-only financials — honest “not live wired” state. */
function metricRegistryPlaceholderSignal(): HubSignalKind {
  return "warning";
}

/** Brain-native fields — success when the row has more than name/tagline. */
function metricBrainProfileSignal(product: ProductRegistryEntry): HubSignalKind {
  if (
    product.tech_stack.length > 0 ||
    Boolean(product.repo_path) ||
    Boolean(product.vercel_project) ||
    Boolean(product.domain)
  ) {
    return "success";
  }
  return "warning";
}

export type OverviewMetricWire = {
  id: "mrr" | "active_users" | "open_issues" | "last_shipped" | "brain_profile";
  label: string;
  signal: HubSignalKind;
};

export function overviewMetricWiring(args: {
  product: ProductRegistryEntry;
  openIssues: number | null;
}): OverviewMetricWire[] {
  return [
    {
      id: "brain_profile",
      label: "Brain product profile",
      signal: metricBrainProfileSignal(args.product),
    },
    {
      id: "mrr",
      label: "MRR",
      signal: metricRegistryPlaceholderSignal(),
    },
    {
      id: "active_users",
      label: "Active users",
      signal: metricRegistryPlaceholderSignal(),
    },
    {
      id: "open_issues",
      label: "Open issues (GitHub)",
      signal: metricOpenIssuesSignal(args.openIssues),
    },
    {
      id: "last_shipped",
      label: "Last shipped",
      signal: metricLastShippedSignal(args.product),
    },
  ];
}

export function overviewTabSignal(args: {
  product: ProductRegistryEntry;
  openIssues: number | null;
}): HubSignalKind {
  const wires = overviewMetricWiring(args);
  return combineSignals(wires.map((w) => w.signal));
}

export type HubTabSignals = {
  overview: HubSignalKind;
  plans: HubSignalKind;
  docs: HubSignalKind;
  health: HubSignalKind;
  gtm: HubSignalKind;
};

export function computeHubTabSignals(args: {
  product: ProductRegistryEntry;
  openIssues: number | null;
  plans: ProductPlansLoadResult;
  filteredEpicCount: number;
  docCount: number;
  healthState: ProductHealthBrainState;
}): HubTabSignals {
  const { rollup } = deriveHeroRollup(args.healthState);
  return {
    overview: overviewTabSignal({
      product: args.product,
      openIssues: args.openIssues,
    }),
    plans: plansTabSignal(args.plans, args.filteredEpicCount),
    docs: docsTabSignal(args.docCount),
    health: healthTabSignal(args.healthState, rollup),
    gtm: gtmTabSignal(),
  };
}

export function hubSignalsToTuple(s: HubTabSignals): readonly HubSignalKind[] {
  return [s.overview, s.plans, s.docs, s.health, s.gtm] as const;
}
