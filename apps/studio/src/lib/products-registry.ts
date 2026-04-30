/** Static product registry helpers — `@/data/products.json`. */

export type ProductStage = "concept" | "alpha" | "beta" | "ga";

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
};

export type ProductsRegistryFile = {
  products: ProductRegistryEntry[];
};

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
