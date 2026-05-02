import { notFound } from "next/navigation";

import { BrainClientError } from "@/lib/brain-client";
import { loadProductRegistryBySlug } from "@/lib/products-brain";
import { deriveHeroRollup, loadProductHealthBrainState } from "@/lib/product-health-brain";

import { ProductHealthShell } from "./product-health-shell";

export const dynamic = "force-dynamic";
export const revalidate = 0;

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
  let productName: string;
  try {
    const product = await loadProductRegistryBySlug(slug);
    productName = product.name;
  } catch (err) {
    if (err instanceof BrainClientError && err.status === 404) notFound();
    throw err;
  }

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
        productName={productName}
        state={state}
        heroRollup={rollup}
        narrative={narrative}
        lastCheckedLabel={lastCheckedLabel}
      />
    </div>
  );
}
