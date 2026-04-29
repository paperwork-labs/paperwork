import Link from "next/link";
import { ExternalLink } from "lucide-react";

import { loadTrackerIndex } from "@/lib/tracker";
import { activePlansForUi } from "@/lib/tracker-reconcile";

export const dynamic = "force-static";

export default function ProductsIndexPage() {
  const { products } = loadTrackerIndex();
  const allPlans = products.flatMap((p) => p.plans);
  const inFlightPlans = activePlansForUi(allPlans).length;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Products</h1>
        <p className="text-sm text-zinc-400">
          Per-product master plans, gap audits, and migration roadmaps. Each
          product owns its own folder under <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs">docs/&lt;product&gt;/plans/</code>;
          this page is the cross-product roll-up.
        </p>
        <p className="text-xs text-zinc-500">
          {inFlightPlans} in-flight plan{inFlightPlans === 1 ? "" : "s"} across{" "}
          {products.length} product{products.length === 1 ? "" : "s"} (same roll-up as Overview).
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        {products.map((product) => {
          const planCount = product.plans.length;
          return (
            <article
              key={product.slug}
              className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
            >
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-zinc-100">
                  {product.label}
                </h2>
                <span className="text-[10px] uppercase tracking-wide text-zinc-500">
                  {planCount} plan{planCount === 1 ? "" : "s"}
                </span>
              </div>
              {planCount === 0 ? (
                <p className="text-sm text-zinc-500">
                  No plans yet. Create{" "}
                  <code className="rounded bg-zinc-800 px-1 text-xs">
                    docs/{product.slug}/plans/MASTER_PLAN.md
                  </code>{" "}
                  to seed.
                </p>
              ) : (
                <ul className="space-y-1.5 text-sm">
                  {product.plans.slice(0, 5).map((plan) => (
                    <li key={plan.slug}>
                      <Link
                        href={`/admin/products/${product.slug}/plan#${plan.slug}`}
                        className="flex items-center justify-between gap-2 rounded-md border border-transparent px-2 py-1 transition hover:border-zinc-800 hover:bg-zinc-800/40"
                      >
                        <span className="truncate text-zinc-200">{plan.title}</span>
                        <span className="shrink-0 text-[10px] uppercase tracking-wide text-zinc-500">
                          {plan.status}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-4 flex items-center gap-3 text-xs text-zinc-500">
                <Link
                  href={`/admin/products/${product.slug}/plan`}
                  className="rounded-md border border-zinc-800 px-2 py-1 transition hover:border-zinc-700 hover:text-zinc-300"
                >
                  Open plan →
                </Link>
                {product.plans_dir ? (
                  <a
                    href={`https://github.com/paperwork-labs/paperwork/tree/main/${product.plans_dir}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-zinc-500 transition hover:text-zinc-300"
                  >
                    Source <ExternalLink className="h-3 w-3" />
                  </a>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
