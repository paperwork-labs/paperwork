import { notFound } from "next/navigation";

import productsData from "@/data/products.json";
import type { ProductsRegistryFile } from "@/lib/products-registry";
import { deriveHeroRollup, loadProductHealthBrainState } from "@/lib/product-health-brain";

import { ProductHealthShell } from "./product-health-shell";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export function generateStaticParams() {
  const { products } = productsData as ProductsRegistryFile;
  return products.map((p) => ({ slug: p.slug }));
}

function formatIso(iso: string | null): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return iso;
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(t) + " UTC";
}

export default async function ProductHealthPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const { products } = productsData as ProductsRegistryFile;
  const product = products.find((p) => p.slug === slug);
  if (!product) notFound();

  const state = await loadProductHealthBrainState(slug);
  const { rollup, narrative } = deriveHeroRollup(state);
  const lastCheckedLabel =
    formatIso(state.probesCheckedAt) ??
    (() => {
      const times = state.cujRows.map((r) => r.lastRunAt).filter(Boolean) as string[];
      if (times.length === 0) return null;
      const latest = times.sort().at(-1) ?? null;
      return formatIso(latest);
    })();

  return (
    <div className="min-h-0 space-y-6 pb-10">
      <ProductHealthShell
        productName={product.name}
        state={state}
        heroRollup={rollup}
        narrative={narrative}
        lastCheckedLabel={lastCheckedLabel}
      />
    </div>
  );
}
