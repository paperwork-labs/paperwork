import productsData from "@/data/products.json";

import { ProductsPageClient } from "./products-page-client";
import type { ProductsRegistryFile } from "@/lib/products-registry";

export const dynamic = "force-static";

export default function ProductsIndexPage() {
  const data = productsData as ProductsRegistryFile;
  return <ProductsPageClient products={data.products} />;
}
