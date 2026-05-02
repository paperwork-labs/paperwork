/** Product registry helpers — Brain-backed rows mapped to Studio cockpit fields. */

import type { BrainProduct } from "@/lib/brain-client";

export type ProductStage = "concept" | "alpha" | "beta" | "ga";

export type ProductPricingTier = {
  id: string;
  name: string;
  /** Monthly USD; `null` means custom / contact sales */
  price_monthly_usd: number | null;
  blurb?: string;
};

/** Optional ship history on a registry row — any ISO-like date field is accepted. */
export type ProductReleaseEntry = {
  published_at?: string;
  date?: string;
  shipped_at?: string;
};

export type ProductRegistryEntry = {
  slug: string;
  name: string;
  tagline: string;
  status: string;
  color_accent: string;
  mrr: number;
  active_users: number;
  owner_persona: string;
  url: string | null;
  admin_url: string;
  pricing_tiers?: ProductPricingTier[];
  releases?: ProductReleaseEntry[];
};

export type ProductsRegistryFile = {
  products: ProductRegistryEntry[];
};

function parsePricingTiers(meta: Record<string, unknown>): ProductPricingTier[] | undefined {
  const raw = meta.pricing_tiers;
  if (!Array.isArray(raw)) return undefined;
  return raw as ProductPricingTier[];
}

function parseReleases(meta: Record<string, unknown>): ProductReleaseEntry[] | undefined {
  const raw = meta.releases;
  if (!Array.isArray(raw)) return undefined;
  return raw as ProductReleaseEntry[];
}

/**
 * Map a Brain ``/admin/products`` row to the richer ``ProductRegistryEntry`` the Studio UI expects.
 * Registry-only fields (accent, MRR, tiers, …) live under ``metadata`` on the Brain row.
 */
export function brainProductToRegistryEntry(p: BrainProduct): ProductRegistryEntry {
  const meta = p.metadata ?? {};
  const domain = p.domain?.trim() || null;
  const urlFromDomain = domain && !domain.includes("://") ? `https://${domain}` : null;
  const metaUrl = meta.url;
  return {
    slug: p.id,
    name: p.name,
    tagline: p.tagline?.trim() ?? "",
    status: p.status,
    color_accent: typeof meta.color_accent === "string" ? meta.color_accent : "#6366f1",
    mrr: typeof meta.mrr === "number" && Number.isFinite(meta.mrr) ? meta.mrr : 0,
    active_users:
      typeof meta.active_users === "number" && Number.isFinite(meta.active_users)
        ? meta.active_users
        : 0,
    owner_persona:
      typeof meta.owner_persona === "string" && meta.owner_persona.trim()
        ? meta.owner_persona
        : "founder",
    url: typeof metaUrl === "string" && metaUrl.trim() ? metaUrl : urlFromDomain,
    admin_url:
      typeof meta.admin_url === "string" && meta.admin_url.trim()
        ? meta.admin_url
        : `/admin/products/${p.id}`,
    pricing_tiers: parsePricingTiers(meta),
    releases: parseReleases(meta),
  };
}

export type ProductStageFilter = "all" | ProductStage;

export function parseProductStatus(raw: string): ProductStage {
  const s = raw.trim().toLowerCase();
  if (s === "ga" || s === "general availability") return "ga";
  if (s === "beta") return "beta";
  if (s === "alpha") return "alpha";
  if (s === "concept") return "concept";
  return "concept";
}

export function productStageLabel(stage: ProductStage): string {
  if (stage === "ga") return "GA";
  return stage.charAt(0).toUpperCase() + stage.slice(1);
}

export function statusPillToneClass(stage: ProductStage): string {
  switch (stage) {
    case "concept":
      return "border-zinc-600 bg-zinc-900/80 text-zinc-400";
    case "alpha":
      return "border-[rgb(217_119_6/0.45)] bg-[rgb(120_53_15/0.22)] text-[rgb(254_243_199)]";
    case "beta":
      return "border-[rgb(2_132_199/0.45)] bg-[rgb(12_74_110/0.22)] text-[rgb(224_242_254)]";
    case "ga":
      return "border-[rgb(22_163_74/0.4)] bg-[rgb(20_83_45/0.2)] text-[rgb(187_247_208)]";
    default: {
      const _exhaustive: never = stage;
      return _exhaustive;
    }
  }
}

export function filterProductsByStage(
  products: ProductRegistryEntry[],
  filter: ProductStageFilter,
): ProductRegistryEntry[] {
  if (filter === "all") return products;
  return products.filter((p) => parseProductStatus(p.status) === filter);
}

export function computeProductsRollup(products: ProductRegistryEntry[]) {
  const activeBetaOrGa = products.filter((p) => {
    const s = parseProductStatus(p.status);
    return s === "beta" || s === "ga";
  }).length;
  return {
    totalProducts: products.length,
    activeBetaOrGa,
    totalMrr: products.reduce((sum, p) => sum + (Number.isFinite(p.mrr) ? p.mrr : 0), 0),
    activeUsers: products.reduce(
      (sum, p) => sum + (Number.isFinite(p.active_users) ? p.active_users : 0),
      0,
    ),
  };
}

export function formatCurrencyUsd(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

/** Latest ship timestamp from `releases` entries, or null when absent / unparsable. */
export function getLatestReleaseShippedIso(product: ProductRegistryEntry): string | null {
  const list = product.releases;
  if (!list?.length) return null;
  let best: number | null = null;
  let bestIso: string | null = null;
  for (const r of list) {
    const raw = r.published_at ?? r.date ?? r.shipped_at;
    if (!raw) continue;
    const t = Date.parse(raw);
    if (!Number.isFinite(t)) continue;
    if (best === null || t > best) {
      best = t;
      bestIso = raw;
    }
  }
  return bestIso;
}
