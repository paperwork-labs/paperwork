import productsData from "@/data/products.json";
import { countOpenIssuesForProductLabel } from "@/lib/command-center";
import {
  deriveHeroRollup,
  heroRollupToProductPulse,
  loadProductHealthBrainState,
} from "@/lib/product-health-brain";
import type { ProductRegistryEntry, ProductsRegistryFile } from "@/lib/products-registry";
import { getLatestReleaseShippedIso } from "@/lib/products-registry";

import type { ProductIndexSummaryBySlug } from "./products-page-client";
import { ProductsPageClient } from "./products-page-client";

export const dynamic = "force-dynamic";

async function buildSummaryMap(products: ProductRegistryEntry[]): Promise<ProductIndexSummaryBySlug> {
  const entries = await Promise.all(
    products.map(async (p) => {
      const [openIssues, brainState] = await Promise.all([
        countOpenIssuesForProductLabel(p.slug),
        loadProductHealthBrainState(p.slug),
      ]);
      const { rollup } = deriveHeroRollup(brainState);
      const health = heroRollupToProductPulse(rollup);
      const lastShipped = getLatestReleaseShippedIso(p);
      return [
        p.slug,
        {
          openIssues,
          health,
          lastShipped,
        },
      ] as const;
    }),
  );
  return Object.fromEntries(entries);
}

export default async function ProductsIndexPage() {
  const data = productsData as ProductsRegistryFile;
  const summaryBySlug = await buildSummaryMap(data.products);
  return <ProductsPageClient products={data.products} summaryBySlug={summaryBySlug} />;
}
