import { notFound } from "next/navigation";

import productsData from "@/data/products.json";
import { countOpenIssuesForProductLabel } from "@/lib/command-center";
import { loadDocsIndex } from "@/lib/docs";
import {
  deriveHeroRollup,
  loadProductHealthBrainState,
} from "@/lib/product-health-brain";
import { loadProductPlansBrainState } from "@/lib/product-hub-plans";
import { filterDocEntriesForProduct, filterEpicsForProductSlug } from "@/lib/product-hub-signals";
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

  const plansLoad = await loadProductPlansBrainState();
  const { goals: filteredGoals } = filterEpicsForProductSlug(plansLoad.hierarchy, slug);
  const docEntries = filterDocEntriesForProduct(loadDocsIndex().entries, product);
  const [openIssues, healthState] = await Promise.all([
    countOpenIssuesForProductLabel(slug),
    loadProductHealthBrainState(slug),
  ]);

  const { narrative: derivedNarrative } = deriveHeroRollup(healthState);
  const brainUnreachable =
    !healthState.brainConfigured || Boolean(healthState.brainDataPlaneError);
  const healthNarrative = brainUnreachable
    ? "Health probes unreachable. Check brain status."
    : derivedNarrative;

  return (
    <ProductCockpitClient
      product={product}
      openIssues={openIssues}
      plansLoad={plansLoad}
      filteredGoals={filteredGoals}
      docEntries={docEntries}
      healthState={healthState}
      healthNarrative={healthNarrative}
    />
  );
}
