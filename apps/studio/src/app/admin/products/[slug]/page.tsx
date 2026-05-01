import { notFound } from "next/navigation";

import productsData from "@/data/products.json";
import { listProductMarkdownDocs } from "@/lib/product-cockpit-docs";
import { deriveHeroRollup, loadProductHealthBrainState } from "@/lib/product-health-brain";
import type { ProductsRegistryFile } from "@/lib/products-registry";

import { ProductCockpitClient } from "./product-cockpit-client";

export const dynamic = "force-dynamic";

export function generateStaticParams() {
  const { products } = productsData as ProductsRegistryFile;
  return products.map((p) => ({ slug: p.slug }));
}

export default async function ProductCockpitPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const { products } = productsData as ProductsRegistryFile;
  const product = products.find((p) => p.slug === slug);
  if (!product) notFound();
  const planDocs = listProductMarkdownDocs(slug);
  const healthState = await loadProductHealthBrainState(slug);
  const { rollup: healthRollup, narrative: derivedNarrative } = deriveHeroRollup(healthState);
  const brainUnreachable =
    !healthState.brainConfigured || Boolean(healthState.brainDataPlaneError);
  const healthNarrative = brainUnreachable
    ? "Health probes unreachable. Check brain status."
    : derivedNarrative;
  return (
    <ProductCockpitClient
      product={product}
      planDocs={planDocs}
      healthRollup={healthRollup}
      healthNarrative={healthNarrative}
    />
  );
}
