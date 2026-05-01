"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ExternalLink, FileText, UserCircle, UsersRound, Wallet } from "lucide-react";
import { cn } from "@paperwork-labs/ui";

import { ProductSupportPanel } from "@/app/admin/products/[slug]/product-support-panel";
import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";
import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import type { ProductPlanDocRef } from "@/lib/product-cockpit-docs";
import type { HeroRollup } from "@/lib/product-health-brain";
import type { ProductRegistryEntry } from "@/lib/products-registry";
import {
  formatCurrencyUsd,
  parseProductStatus,
  productStageLabel,
  statusPillToneClass,
} from "@/lib/products-registry";

function formatTierPrice(priceMonthlyUsd: number | null): string {
  if (priceMonthlyUsd === null) return "Custom";
  return `${formatCurrencyUsd(priceMonthlyUsd)}/mo`;
}

function heroRollupDotClass(rollup: HeroRollup): string {
  switch (rollup) {
    case "healthy":
      return "bg-emerald-400";
    case "degraded":
      return "bg-amber-400";
    case "down":
      return "bg-rose-500";
    default:
      return "bg-zinc-500";
  }
}

function heroRollupShortLabel(rollup: HeroRollup): string {
  switch (rollup) {
    case "healthy":
      return "Healthy";
    case "degraded":
      return "Degraded";
    case "down":
      return "Down";
    default:
      return "Unknown";
  }
}

function OverviewPanel({
  product,
  healthRollup,
  healthNarrative,
}: {
  product: ProductRegistryEntry;
  healthRollup: HeroRollup;
  healthNarrative: string;
}) {
  const stage = parseProductStatus(product.status);
  const stageLabel = productStageLabel(stage);

  const rows: { label: string; value: ReactNode }[] = [
    { label: "Slug", value: <code className="text-zinc-300">{product.slug}</code> },
    {
      label: "Owner persona",
      value: (
        <span className="capitalize text-zinc-300">{product.owner_persona.replace(/_/g, " ")}</span>
      ),
    },
    {
      label: "Admin URL",
      value: (
        <Link
          href={product.admin_url}
          className="text-[var(--status-info)] underline-offset-2 hover:underline"
        >
          {product.admin_url}
        </Link>
      ),
    },
    {
      label: "Public URL",
      value: product.url ? (
        <a
          href={product.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-[var(--status-info)] underline-offset-2 hover:underline"
        >
          {product.url}
          <ExternalLink className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />
        </a>
      ) : (
        <span className="text-[var(--status-muted)]">Not set</span>
      ),
    },
  ];

  return (
    <div className="space-y-8">
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 flex-wrap items-center gap-3">
            <h3 className="text-sm font-semibold text-zinc-100">Health</h3>
            <span className="inline-flex items-center gap-1.5 text-xs text-zinc-300">
              <span className={cn("h-2 w-2 shrink-0 rounded-full", heroRollupDotClass(healthRollup))} />
              {heroRollupShortLabel(healthRollup)}
            </span>
          </div>
          <Link
            href={`/admin/products/${product.slug}/health`}
            className="shrink-0 text-xs text-sky-400 hover:underline"
          >
            View probes →
          </Link>
        </div>
        <p className="mt-2 text-xs text-zinc-400">{healthNarrative}</p>
      </div>

      <section
        className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-5"
        aria-label="Product summary"
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <h2
              className="truncate text-lg font-semibold tracking-tight"
              style={{ color: product.color_accent }}
            >
              {product.name}
            </h2>
            <p className="text-sm text-[var(--status-muted)]">{product.tagline}</p>
          </div>
          <span
            className={`inline-flex w-fit shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusPillToneClass(stage)}`}
          >
            {stageLabel}
          </span>
        </div>
        <div className="mt-6 flex flex-wrap gap-x-10 gap-y-3 border-t border-zinc-800/60 pt-5">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--status-muted)]">
              MRR
            </p>
            <p className="mt-0.5 text-base font-medium tabular-nums text-zinc-100">
              {formatCurrencyUsd(product.mrr)}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--status-muted)]">
              Active users
            </p>
            <p className="mt-0.5 text-base font-medium tabular-nums text-zinc-100">
              {product.active_users}
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-3 sm:grid-cols-3">
        <HqStatCard
          label="MRR"
          value={formatCurrencyUsd(product.mrr)}
          icon={<Wallet className="h-3.5 w-3.5 text-[var(--status-muted)]" />}
          variant="compact"
        />
        <HqStatCard
          label="Active users"
          value={product.active_users}
          icon={<UsersRound className="h-3.5 w-3.5 text-[var(--status-muted)]" />}
          variant="compact"
        />
        <HqStatCard
          label="Owner"
          value={product.owner_persona.replace(/_/g, " ")}
          icon={<UserCircle className="h-3.5 w-3.5 text-[var(--status-muted)]" />}
          variant="compact"
        />
      </div>

      <dl className="grid gap-4 sm:grid-cols-2">
        {rows.map((row) => (
          <div key={row.label} className="space-y-1">
            <dt className="text-[10px] font-semibold uppercase tracking-wider text-[var(--status-muted)]">
              {row.label}
            </dt>
            <dd className="text-sm text-zinc-400">{row.value}</dd>
          </div>
        ))}
      </dl>
      <Link
        href={`/admin/products/${product.slug}/plan`}
        className="inline-flex text-sm font-medium text-[var(--status-info)] underline-offset-2 hover:underline"
      >
        Open legacy plan rollup →
      </Link>
    </div>
  );
}

function PlansPanel({ docs, productSlug }: { docs: ProductPlanDocRef[]; productSlug: string }) {
  if (docs.length === 0) {
    return (
      <HqEmptyState
        title="No plans on disk"
        description={`No markdown files found under docs/${productSlug}/. Add docs there to list them here.`}
      />
    );
  }

  return (
    <ul className="space-y-2">
      {docs.map((doc) => (
        <li
          key={doc.path}
          className="flex items-start gap-3 rounded-xl border border-zinc-800/80 bg-zinc-950/40 px-4 py-3"
        >
          <FileText
            className="mt-0.5 h-4 w-4 shrink-0 text-[var(--status-muted)]"
            aria-hidden
          />
          <div className="min-w-0 flex-1">
            {doc.hubSlug ? (
              <Link
                href={`/admin/docs/${doc.hubSlug}`}
                className="text-sm font-medium text-[var(--status-info)] underline-offset-2 hover:underline"
              >
                {doc.title}
              </Link>
            ) : (
              <span className="text-sm font-medium text-zinc-200">{doc.title}</span>
            )}
            <p className="mt-0.5 truncate font-mono text-xs text-[var(--status-muted)]">{doc.path}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function MetricsPanel({ product }: { product: ProductRegistryEntry }) {
  return (
    <div className="space-y-10" data-testid="product-metrics-tab">
      <section aria-label="PostHog analytics" className="space-y-4">
        <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--status-muted)]">
          PostHog
        </h3>
        <div
          data-testid="metrics-posthog-placeholder"
          className="flex min-h-[140px] flex-col items-center justify-center rounded-xl border border-dashed border-zinc-700/70 bg-zinc-950/25 px-6 text-center"
        >
          <p className="text-sm font-medium text-zinc-400">Insight embed placeholder</p>
          <p className="mt-1 max-w-sm text-xs text-zinc-600">
            Reserved region for PostHog dashboard or shared insights — not rendered until configured.
          </p>
        </div>
        <HqEmptyState
          title="PostHog not configured"
          description="Set embed / project credentials to show live product analytics (configured: false). This is an explicit empty state — not synthetic traffic."
        />
      </section>

      <section aria-label="Stripe revenue" className="space-y-4">
        <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--status-muted)]">
          Stripe MRR
        </h3>
        <HqEmptyState
          title="Stripe MRR not connected"
          description={`Live MRR from Stripe is not wired for ${product.name} (configured: false). Overview uses registry figures only.`}
        />
      </section>
    </div>
  );
}

function PricingPanel({ product }: { product: ProductRegistryEntry }) {
  const tiers = product.pricing_tiers ?? [];
  if (tiers.length === 0) {
    return (
      <HqEmptyState
        title="Pricing"
        description="No pricing tiers in products.json yet. Add a pricing_tiers array to this product to show plans here."
      />
    );
  }

  return (
    <ul className="space-y-3">
      {tiers.map((tier) => (
        <li
          key={tier.id}
          className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 px-4 py-3"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-medium text-zinc-100">{tier.name}</span>
            <span className="tabular-nums text-sm font-semibold text-[var(--status-success)]">
              {formatTierPrice(tier.price_monthly_usd)}
            </span>
          </div>
          {tier.blurb ? (
            <p className="mt-1.5 text-sm text-[var(--status-muted)]">{tier.blurb}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function ProductCockpitClient({
  product,
  planDocs,
  healthRollup,
  healthNarrative,
}: {
  product: ProductRegistryEntry;
  planDocs: ProductPlanDocRef[];
  healthRollup: HeroRollup;
  healthNarrative: string;
}) {
  const stage = parseProductStatus(product.status);

  const tabs = [
    {
      id: "overview" as const,
      label: "Overview",
      content: (
        <OverviewPanel
          product={product}
          healthRollup={healthRollup}
          healthNarrative={healthNarrative}
        />
      ),
    },
    {
      id: "plans" as const,
      label: "Plans",
      content: <PlansPanel docs={planDocs} productSlug={product.slug} />,
    },
    {
      id: "releases" as const,
      label: "Releases",
      content: <HqEmptyState title="No releases yet" description="Ship trains will show up here." />,
    },
    {
      id: "pricing" as const,
      label: "Pricing",
      content: <PricingPanel product={product} />,
    },
    {
      id: "customers" as const,
      label: "Customers",
      content: (
        <HqEmptyState title="Customers" description="Customer data coming in WS-77" />
      ),
    },
    {
      id: "support" as const,
      label: "Support",
      content: <ProductSupportPanel productSlug={product.slug} productName={product.name} />,
    },
    {
      id: "metrics" as const,
      label: "Metrics",
      content: <MetricsPanel product={product} />,
    },
  ] as const;

  return (
    <div className="space-y-6">
      <HqPageHeader
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "Products", href: "/admin/products" },
          { label: product.name },
        ]}
        title={<span style={{ color: product.color_accent }}>{product.name}</span>}
        subtitle={product.tagline}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/admin/products/${product.slug}/health`}
              className="inline-flex rounded-lg border border-zinc-700/90 bg-zinc-900/60 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-200 transition hover:border-zinc-600 hover:bg-zinc-800/80"
            >
              Health
            </Link>
            <span
              className={`inline-flex shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusPillToneClass(stage)}`}
            >
              {productStageLabel(stage)}
            </span>
          </div>
        }
      />
      <TabbedPageShell tabs={tabs} defaultTab="overview" />
    </div>
  );
}
