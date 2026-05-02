import type { DispatchLogEntry, EpicHierarchyResponse, GoalItem, EpicItem } from "@/lib/brain-client";
import { BrainClient, BrainClientError } from "@/lib/brain-client";
import type { InfraStatus } from "@/lib/infra-types";
import {
  deriveHeroRollup,
  heroRollupToProductPulse,
  loadProductHealthBrainState,
  type ProductHealthPulse,
} from "@/lib/product-health-brain";
import type { ProductRegistryEntry } from "@/lib/products-registry";
import { validateReadingPaths } from "@/lib/reading-paths";

export type OverviewOperatingScore =
  | { ok: true; overall_score: number; max_score: number }
  | { ok: false; message: string };

export type OverviewEpicPulse =
  | {
      ok: true;
      activeEpics: number;
      wavePct: number;
      blockedEpics: { goalObjective: string; epicTitle: string }[];
    }
  | { ok: false; message: string };

export type OverviewPeoplePulse =
  | { ok: true; total: number; named: number }
  | { ok: false; message: string };

export type OverviewBrainFill =
  | { ok: true; utilizationPct: number }
  | { ok: false; message: string };

export type OverviewDispatches =
  | { ok: true; entries: DispatchLogEntry[] }
  | { ok: false; message: string };

export type ProductHealthRollup = {
  total: number;
  healthy: number;
  degraded: number;
  down: number;
  unknown: number;
  /** Products needing attention (degraded/down only when pulse known). */
  degradedOrDown: { slug: string; pulse: ProductHealthPulse }[];
};

function brainErrMessage(err: unknown, fallback: string): string {
  if (err instanceof BrainClientError) return err.message;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

async function safeBrain<T>(
  fn: () => Promise<T>,
  unavailableMessage: string,
): Promise<{ ok: true; data: T } | { ok: false; message: string }> {
  try {
    return { ok: true, data: await fn() };
  } catch (err) {
    return { ok: false, message: brainErrMessage(err, unavailableMessage) };
  }
}

export async function loadOperatingScorePulse(
  client: BrainClient | null,
): Promise<OverviewOperatingScore> {
  if (!client) {
    return { ok: false, message: "Brain not configured" };
  }
  const r = await safeBrain(() => client.getOperatingScore(), "Operating score unavailable");
  if (!r.ok) return { ok: false, message: r.message };
  return {
    ok: true,
    overall_score: r.data.overall_score,
    max_score: r.data.max_score,
  };
}

function collectEpics(goals: GoalItem[]): EpicItem[] {
  return goals.flatMap((g) => g.epics);
}

function computeEpicPulse(hierarchy: EpicHierarchyResponse): Omit<
  Extract<OverviewEpicPulse, { ok: true }>,
  "ok"
> {
  const all = collectEpics(hierarchy);
  const blockedEpics = hierarchy.flatMap((goal) =>
    goal.epics
      .filter((e) => e.status.toLowerCase() === "blocked")
      .map((e) => ({ goalObjective: goal.objective, epicTitle: e.title })),
  );
  const active = all.filter((e) => {
    const s = e.status.toLowerCase();
    return s !== "done" && s !== "paused";
  });
  const wavePct =
    active.length === 0
      ? 100
      : Math.round(
          active.reduce((sum, e) => sum + (Number.isFinite(e.percent_done) ? e.percent_done : 0), 0) /
            active.length,
        );
  return { activeEpics: active.length, wavePct, blockedEpics };
}

export async function loadEpicHierarchyPulse(
  client: BrainClient | null,
): Promise<OverviewEpicPulse> {
  if (!client) {
    return { ok: false, message: "Brain not configured" };
  }
  const r = await safeBrain(() => client.getEpicHierarchy(), "Epics unavailable");
  if (!r.ok) return { ok: false, message: r.message };
  const pulse = computeEpicPulse(r.data);
  return { ok: true, ...pulse };
}

export async function loadPeoplePulse(client: BrainClient | null): Promise<OverviewPeoplePulse> {
  if (!client) {
    return { ok: false, message: "Brain not configured" };
  }
  const r = await safeBrain(() => client.getEmployees(), "People unavailable");
  if (!r.ok) return { ok: false, message: r.message };
  const employees = r.data;
  const named = employees.filter(
    (e) => Boolean(e.named_at?.trim()) || Boolean(e.display_name?.trim()),
  ).length;
  return { ok: true, total: employees.length, named };
}

export async function loadBrainFillPulse(client: BrainClient | null): Promise<OverviewBrainFill> {
  if (!client) {
    return { ok: false, message: "Brain not configured" };
  }
  const r = await safeBrain(() => client.getBrainFillMeter(), "Memory utilization unavailable");
  if (!r.ok) return { ok: false, message: r.message };
  const pct = r.data.overall_utilization_pct;
  const utilizationPct =
    typeof pct === "number" && Number.isFinite(pct) ? Math.round(Math.min(100, Math.max(0, pct))) : 0;
  return { ok: true, utilizationPct };
}

export async function loadRecentDispatches(
  client: BrainClient | null,
  limit: number,
): Promise<OverviewDispatches> {
  if (!client) {
    return { ok: false, message: "Brain not configured" };
  }
  const r = await safeBrain(() => client.getDispatchLog(limit), "Activity unavailable");
  if (!r.ok) return { ok: false, message: r.message };
  return { ok: true, entries: r.data.dispatches ?? [] };
}

export async function loadProductHealthRollup(
  products: ProductRegistryEntry[],
): Promise<ProductHealthRollup> {
  const pulses = await Promise.all(
    products.map(async (p) => {
      try {
        const state = await loadProductHealthBrainState(p.slug);
        const { rollup } = deriveHeroRollup(state);
        return { slug: p.slug, pulse: heroRollupToProductPulse(rollup) };
      } catch {
        return { slug: p.slug, pulse: null as ProductHealthPulse | null };
      }
    }),
  );

  let healthy = 0;
  let degraded = 0;
  let down = 0;
  let unknown = 0;
  const degradedOrDown: { slug: string; pulse: ProductHealthPulse }[] = [];

  for (const row of pulses) {
    if (row.pulse === "ok") healthy++;
    else if (row.pulse === "degraded") {
      degraded++;
      degradedOrDown.push({ slug: row.slug, pulse: "degraded" });
    } else if (row.pulse === "down") {
      down++;
      degradedOrDown.push({ slug: row.slug, pulse: "down" });
    } else unknown++;
  }

  return {
    total: products.length,
    healthy,
    degraded,
    down,
    unknown,
    degradedOrDown,
  };
}

export function infraHealthyCounts(services: InfraStatus[]) {
  const materialized = services.filter((s) => s.configured);
  const healthy = materialized.filter((s) => s.healthy).length;
  const failing = materialized.filter((s) => !s.healthy && !s.deprecated);
  return { healthy, total: materialized.length, failing };
}

export function readingPathsUnresolvedSummary(): {
  pathCount: number;
  samples: { id: string; title: string; unresolvedCount: number }[];
} {
  const rows = validateReadingPaths();
  const broken = rows.filter((r) => r.unresolvedDocIds.length > 0);
  const samples = broken.slice(0, 5).map((r) => ({
    id: r.id,
    title: r.title,
    unresolvedCount: r.unresolvedDocIds.length,
  }));
  return { pathCount: broken.length, samples };
}
