"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Layers, Radar, UsersRound, Wallet } from "lucide-react";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";
import {
  type ProductRegistryEntry,
  type ProductStageFilter,
  computeProductsRollup,
  filterProductsByStage,
  formatCurrencyUsd,
  parseProductStatus,
  productStageLabel,
  statusPillToneClass,
} from "@/lib/products-registry";

const FILTERS: { id: ProductStageFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "concept", label: "Concept" },
  { id: "alpha", label: "Alpha" },
  { id: "beta", label: "Beta" },
  { id: "ga", label: "GA" },
];

export function ProductsPageClient({ products }: { products: ProductRegistryEntry[] }) {
  const [filter, setFilter] = useState<ProductStageFilter>("all");
  const visible = useMemo(() => filterProductsByStage(products, filter), [products, filter]);
  const rollup = useMemo(() => computeProductsRollup(products), [products]);

  return (
    <div className="space-y-8">
      <HqPageHeader
        title="Products"
        subtitle="All Paperwork Labs products"
        breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Products" }]}
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <HqStatCard
          label="Total Products"
          value={rollup.totalProducts}
          icon={<Layers className="h-3.5 w-3.5 text-zinc-500" />}
          variant="compact"
        />
        <HqStatCard
          label="Active"
          status="success"
          helpText="Beta + GA"
          value={rollup.activeBetaOrGa}
          icon={<Radar className="h-3.5 w-3.5 text-zinc-500" />}
          variant="compact"
        />
        <HqStatCard
          label="Total MRR"
          value={formatCurrencyUsd(rollup.totalMrr)}
          icon={<Wallet className="h-3.5 w-3.5 text-zinc-500" />}
          variant="compact"
        />
        <HqStatCard
          label="Active Users"
          value={rollup.activeUsers}
          icon={<UsersRound className="h-3.5 w-3.5 text-zinc-500" />}
          variant="compact"
        />
      </div>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Product stage">
        {FILTERS.map((f) => {
          const pressed = filter === f.id;
          return (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={pressed}
              onClick={() => setFilter(f.id)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                pressed
                  ? "border-[var(--status-info)]/50 bg-[rgb(12_74_110/0.22)] text-[rgb(224_242_254)]"
                  : "border-zinc-700 bg-zinc-900/50 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
              }`}
            >
              {f.label}
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {visible.map((product) => (
          <ProductCard key={product.slug} product={product} />
        ))}
      </div>
    </div>
  );
}

function ProductCard({ product }: { product: ProductRegistryEntry }) {
  const stage = parseProductStatus(product.status);
  return (
    <article
      data-testid="product-registry-card"
      data-product-slug={product.slug}
      className="flex flex-col overflow-hidden rounded-xl border border-zinc-800/90 bg-zinc-950/40 ring-1 ring-inset ring-black/5"
    >
      <div className="h-1 w-full shrink-0" style={{ backgroundColor: product.color_accent }} />
      <div className="flex flex-1 flex-col p-4">
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-base font-semibold tracking-tight text-zinc-100">{product.name}</h2>
          <span
            className={`inline-flex shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${statusPillToneClass(stage)}`}
          >
            {productStageLabel(stage)}
          </span>
        </div>
        <p className="mt-1 line-clamp-2 text-sm text-zinc-500">{product.tagline}</p>
        <p className="mt-3 text-xs text-zinc-500">
          MRR{" "}
          <span className="font-medium tabular-nums text-zinc-300">
            {formatCurrencyUsd(product.mrr)}
          </span>
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-zinc-800/80 pt-4">
          <Link
            href={`/admin/products/${product.slug}`}
            className="text-sm font-medium text-[var(--status-info)] transition hover:text-[rgb(186_230_253)]"
          >
            Open cockpit →
          </Link>
        </div>
      </div>
    </article>
  );
}
