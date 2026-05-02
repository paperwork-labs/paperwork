import { notFound } from "next/navigation";

import { BrainClientError } from "@/lib/brain-client";
import { countOpenIssuesForProductLabel } from "@/lib/command-center";
import { loadDocsIndex } from "@/lib/docs";
import {
  deriveHeroRollup,
  loadProductHealthBrainState,
} from "@/lib/product-health-brain";
import { loadProductPlansBrainState } from "@/lib/product-hub-plans";
import { filterDocEntriesForProduct, filterEpicsForProductSlug } from "@/lib/product-hub-signals";
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
