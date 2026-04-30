"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ExternalLink } from "lucide-react";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import type { ProductRegistryEntry } from "@/lib/products-registry";
import {
  formatCurrencyUsd,
  parseProductStatus,
  productStageLabel,
  statusPillToneClass,
} from "@/lib/products-registry";

function OverviewPanel({ product }: { product: ProductRegistryEntry }) {
  const rows: { label: string; value: ReactNode }[] = [
    { label: "Slug", value: <code className="text-zinc-300">{product.slug}</code> },
    { label: "Tagline", value: product.tagline },
    {
      label: "Owner persona",
      value: <span className="capitalize text-zinc-300">{product.owner_persona}</span>,
    },
    {
      label: "MRR",
      value: <span className="tabular-nums text-zinc-300">{formatCurrencyUsd(product.mrr)}</span>,
    },
    {
      label: "Active users",
      value: <span className="tabular-nums text-zinc-300">{product.active_users}</span>,
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
        <span className="text-zinc-500">Not set</span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <dl className="grid gap-4 sm:grid-cols-2">
        {rows.map((row) => (
          <div key={row.label} className="space-y-1">
            <dt className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
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

export function ProductCockpitClient({ product }: { product: ProductRegistryEntry }) {
  const stage = parseProductStatus(product.status);

  const tabs = [
    {
      id: "overview" as const,
      label: "Overview",
      content: <OverviewPanel product={product} />,
    },
    {
      id: "plans" as const,
      label: "Plans",
      content: (
        <HqEmptyState title="Plans" description="Product plans and roadmap will appear here." />
      ),
    },
    {
      id: "releases" as const,
      label: "Releases",
      content: (
        <HqEmptyState
          title="Releases"
          description="Release trains and changelog will appear here."
        />
      ),
    },
    {
      id: "pricing" as const,
      label: "Pricing",
      content: (
        <HqEmptyState
          title="Pricing"
          description="SKU and pricing experiments will appear here."
        />
      ),
    },
    {
      id: "metrics" as const,
      label: "Metrics",
      content: (
        <HqEmptyState title="Metrics" description="Usage and revenue metrics will appear here." />
      ),
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
          <span
            className={`inline-flex shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusPillToneClass(stage)}`}
          >
            {productStageLabel(stage)}
          </span>
        }
      />
      <TabbedPageShell tabs={tabs} defaultTab="overview" />
    </div>
  );
}
