import type { ProductRegistryEntry } from "@/lib/products-registry";

/** Ordered slugs for the Studio admin product breadcrumb switcher (Wave 4). */
export const STUDIO_PRODUCT_BREADCRUMB_SLUGS = [
  "studio",
  "axiomfolio",
  "filefree",
  "launchfree",
  "distill",
  "trinkets",
] as const;

export function studioProductBreadcrumbOptions(
  products: ProductRegistryEntry[],
): { slug: string; label: string }[] {
  const bySlug = new Map(products.map((p) => [p.slug, p]));
  return STUDIO_PRODUCT_BREADCRUMB_SLUGS.flatMap((slug) => {
    const p = bySlug.get(slug);
    if (!p) return [];
    return [{ slug: p.slug, label: p.name }];
  });
}
