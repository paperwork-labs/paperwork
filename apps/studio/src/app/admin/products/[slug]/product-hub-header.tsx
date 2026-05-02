import type { ProductRegistryEntry } from "@/lib/products-registry";
import {
  parseProductStatus,
  productStageLabel,
  statusPillToneClass,
} from "@/lib/products-registry";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";

export function ProductHubHeader({ product }: { product: ProductRegistryEntry }) {
  const stage = parseProductStatus(product.status);
  return (
    <div className="overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-950/40">
      <div
        className="h-1 w-full shrink-0"
        style={{ backgroundColor: product.color_accent }}
        aria-hidden
      />
      <div className="p-4 md:p-5">
        <HqPageHeader
          breadcrumbs={[
            { label: "Admin", href: "/admin" },
            { label: "Products", href: "/admin/products" },
            { label: product.name },
          ]}
          title={<span style={{ color: product.color_accent }}>{product.name}</span>}
          subtitle={product.tagline}
          actions={
            <span
              className={`inline-flex shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusPillToneClass(stage)}`}
            >
              {productStageLabel(stage)}
            </span>
          }
        />
      </div>
    </div>
  );
}
