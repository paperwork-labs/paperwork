import { notFound } from "next/navigation";
import { ExternalLink } from "lucide-react";

import { findProduct, listTrackerProducts } from "@/lib/tracker";

import { PlanCardTitle } from "./plan-card-title";
import { ProductPlanBreadcrumb } from "./product-plan-breadcrumb";

export const dynamic = "force-static";

export function generateStaticParams() {
  return listTrackerProducts().map((p) => ({ slug: p.slug }));
}

export default async function ProductPlanPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const product = findProduct(slug);
  if (!product) notFound();

  const productCrumbs = listTrackerProducts()
    .map((p) => ({
      slug: p.slug,
      label: p.label,
    }))
    .sort((a, b) => a.label.localeCompare(b.label));

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <ProductPlanBreadcrumb currentSlug={slug} products={productCrumbs} />
        <h1 className="text-2xl font-semibold tracking-tight">
          {product.label} — Plans
        </h1>
        <p className="text-sm text-zinc-400">
          Master plans, gap audits, and migration roadmaps for {product.label}. Sourced from{" "}
          {product.plans_dir ? (
            <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs">
              {product.plans_dir}/
            </code>
          ) : (
            "the docs tree"
          )}
          .
        </p>
      </header>

      {product.plans.length === 0 ? (
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 text-sm text-zinc-400">
          No plans tracked yet. Add a markdown file under{" "}
          <code className="rounded bg-zinc-800 px-1 text-xs">
            docs/{product.slug}/plans/
          </code>{" "}
          with frontmatter (
          <code className="text-xs">owner</code>, <code className="text-xs">status</code>,
          <code className="text-xs">doc_kind: plan</code>) and re-run{" "}
          <code className="rounded bg-zinc-800 px-1 text-xs">
            scripts/generate_tracker_index.py
          </code>
          .
        </section>
      ) : (
        <section className="space-y-3">
          {product.plans.map((plan) => (
            <article
              key={plan.slug}
              id={plan.slug}
              className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1 pr-2">
                  <PlanCardTitle title={plan.title} />
                  <p className="mt-1 break-all text-xs text-zinc-500">
                    <code className="text-[11px]">{plan.path}</code>
                    {plan.last_reviewed ? <> · reviewed {plan.last_reviewed}</> : null}
                  </p>
                </div>
                <span className="shrink-0 rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-300">
                  {plan.status}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                {plan.owner ? (
                  <span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-sky-300">
                    owner: {plan.owner}
                  </span>
                ) : null}
                {plan.doc_kind ? (
                  <span className="rounded-full bg-zinc-800 px-2 py-0.5">
                    {plan.doc_kind}
                  </span>
                ) : null}
                <a
                  href={`https://github.com/paperwork-labs/paperwork/blob/main/${plan.path}`}
                  target="_blank"
                  rel="noreferrer"
                  className="ml-auto inline-flex items-center gap-1 transition hover:text-zinc-200"
                >
                  Open in GitHub <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
