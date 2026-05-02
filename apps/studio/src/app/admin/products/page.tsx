import { countOpenIssuesForProductLabel } from "@/lib/command-center";
import { loadDocsIndex } from "@/lib/docs";
import {
  deriveHeroRollup,
  heroRollupToProductPulse,
  loadProductHealthBrainState,
} from "@/lib/product-health-brain";
import { loadProductPlansBrainState } from "@/lib/product-hub-plans";
import {
  computeHubTabSignals,
  filterDocEntriesForProduct,
  filterEpicsForProductSlug,
  hubSignalsToTuple,
} from "@/lib/product-hub-signals";
import { loadProductsRegistry } from "@/lib/products-brain";
import type { ProductRegistryEntry } from "@/lib/products-registry";
import { getLatestReleaseShippedIso } from "@/lib/products-registry";

import type { ProductIndexSummaryBySlug } from "./products-page-client";
import { ProductsPageClient } from "./products-page-client";

export const dynamic = "force-dynamic";

async function buildSummaryMap(products: ProductRegistryEntry[]): Promise<ProductIndexSummaryBySlug> {
  const plansLoad = await loadProductPlansBrainState();
  const { entries: docEntries } = loadDocsIndex();
  const entries = await Promise.all(
    products.map(async (p) => {
      const [openIssues, brainState] = await Promise.all([
        countOpenIssuesForProductLabel(p.slug),
        loadProductHealthBrainState(p.slug),
      ]);
      const { rollup } = deriveHeroRollup(brainState);
      const health = heroRollupToProductPulse(rollup);
      const lastShipped = getLatestReleaseShippedIso(p);
      const { goals } = filterEpicsForProductSlug(plansLoad.hierarchy, p.slug);
      const docsForProduct = filterDocEntriesForProduct(docEntries, p);
      const signals = computeHubTabSignals({
        product: p,
        openIssues,
        plans: plansLoad,
        filteredEpicCount: goals.reduce((n, g) => n + g.epics.length, 0),
        docCount: docsForProduct.length,
        healthState: brainState,
      });
      return [
        p.slug,
        {
          openIssues,
          health,
          lastShipped,
          hubSignals: hubSignalsToTuple(signals),
        },
      ] as const;
    }),
  );
  return Object.fromEntries(entries);
}

export default async function ProductsIndexPage() {
  const products = await loadProductsRegistry();
  const summaryBySlug = await buildSummaryMap(products);
  return <ProductsPageClient products={products} summaryBySlug={summaryBySlug} />;
}
