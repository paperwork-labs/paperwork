import { notFound } from "next/navigation";

import { BrainClientError } from "@/lib/brain-client";
import { countOpenIssuesForProductLabel } from "@/lib/command-center";
import { loadDocsEntriesWithYamlTags } from "@/lib/docs-yaml-tags";
import {
  deriveHeroRollup,
  loadProductHealthBrainState,
} from "@/lib/product-health-brain";
import { loadProductPlansBrainStateForSlug } from "@/lib/product-hub-plans";
import { filterDocEntriesForProduct } from "@/lib/product-hub-signals";
import { loadProductRegistryBySlug } from "@/lib/products-brain";

import { ProductCockpitClient } from "./product-cockpit-client";

export const dynamic = "force-dynamic";

export default async function ProductCockpitPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let product;
  try {
    product = await loadProductRegistryBySlug(slug);
  } catch (err) {
    if (err instanceof BrainClientError && err.status === 404) notFound();
    throw err;
  }

  const plansLoad = await loadProductPlansBrainStateForSlug(slug);
  const filteredGoals = plansLoad.hierarchy ?? [];
  const docEntries = filterDocEntriesForProduct(loadDocsEntriesWithYamlTags(), product);
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
