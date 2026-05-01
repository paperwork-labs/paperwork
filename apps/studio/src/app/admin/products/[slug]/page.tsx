import { notFound } from "next/navigation";

import productsData from "@/data/products.json";
import { listProductMarkdownDocs } from "@/lib/product-cockpit-docs";
import type { ProductsRegistryFile } from "@/lib/products-registry";

import { ProductCockpitClient } from "./product-cockpit-client";

export const dynamic = "force-static";

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
  return (
    <ProductCockpitClient product={product} planDocs={planDocs} allProducts={products} />
  );
}
