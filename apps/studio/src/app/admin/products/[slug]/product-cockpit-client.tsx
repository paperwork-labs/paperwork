"use client";

import Link from "next/link";
import {
  Activity,
  BookOpen,
  ExternalLink,
  GitBranch,
  Rocket,
  Target,
  UsersRound,
  Wallet,
} from "lucide-react";
import { Badge, Card, CardContent, cn, Progress } from "@paperwork-labs/ui";

import { ProductHubHeader } from "@/app/admin/products/[slug]/product-hub-header";
import { ProductHubHealthPanel } from "@/app/admin/products/[slug]/product-hub-health-panel";
import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";
import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import type { EpicHierarchyResponse } from "@/lib/brain-client";
import type { DocEntry } from "@/lib/docs";
import {
  deriveHeroRollup,
  type HeroRollup,
  type ProductHealthBrainState,
} from "@/lib/product-health-brain";
import type { HubSignalKind, ProductPlansLoadResult } from "@/lib/product-hub-signals";
import { computeHubTabSignals, overviewMetricWiring } from "@/lib/product-hub-signals";
import type { ProductRegistryEntry } from "@/lib/products-registry";
import {
  formatCurrencyUsd,
  getLatestReleaseShippedIso,
  githubRepoBrowseUrl,
  vercelDashboardProjectUrl,
} from "@/lib/products-registry";

const SIGNAL_DOT: Record<HubSignalKind, string> = {
  success: "bg-[var(--status-success)]",
  warning: "bg-[var(--status-warning)]",
  danger: "bg-[var(--status-danger)]",
  muted: "bg-zinc-600",
};

const SIGNAL_COPY: Record<
  HubSignalKind,
  { label: string; hint: string }
> = {
  success: { label: "Wired", hint: "Source connected" },
  warning: { label: "Not connected", hint: "Placeholder or registry-only" },
  danger: { label: "Error", hint: "Source reachable but erroring" },
  muted: { label: "Not configured", hint: "No data source" },
};

function SignalDot({ kind }: { kind: HubSignalKind }) {
  return (
    <span
      className={cn("inline-block h-2 w-2 shrink-0 rounded-full", SIGNAL_DOT[kind])}
      title={SIGNAL_COPY[kind].hint}
      aria-hidden
    />
  );
}

function countLinkedEpics(goals: EpicHierarchyResponse): number {
  return goals.reduce((n, g) => n + g.epics.length, 0);
}

function countActiveSprints(goals: EpicHierarchyResponse): number {
  const active = new Set(["active", "in_progress", "planned"]);
  let n = 0;
  for (const g of goals) {
    for (const e of g.epics) {
      for (const s of e.sprints ?? []) {
        if (active.has((s.status || "").toLowerCase())) n += 1;
      }
    }
  }
  return n;
}

function OverviewPanel({
  product,
  openIssues,
  healthRollup,
  healthNarrative,
  filteredGoals,
  docCount,
}: {
  product: ProductRegistryEntry;
  openIssues: number | null;
  healthRollup: HeroRollup;
  healthNarrative: string;
  filteredGoals: EpicHierarchyResponse;
  docCount: number;
}) {
  const metricWires = overviewMetricWiring({ product, openIssues });
  const lastShippedIso = getLatestReleaseShippedIso(product);
  const openIssuesDisplay = openIssues === null ? "—" : String(openIssues);
  const linkedEpics = countLinkedEpics(filteredGoals);
  const activeSprints = countActiveSprints(filteredGoals);
  const vercelTeam =
    typeof process.env.NEXT_PUBLIC_VERCEL_TEAM_SLUG === "string" &&
    process.env.NEXT_PUBLIC_VERCEL_TEAM_SLUG.trim()
      ? process.env.NEXT_PUBLIC_VERCEL_TEAM_SLUG.trim()
      : null;

  const domainHref =
    product.url ??
    (product.domain && !product.domain.includes("://")
      ? `https://${product.domain}`
      : product.domain);

  const repoHref = product.repo_path ? githubRepoBrowseUrl(product.repo_path) : null;
  const vercelHref = product.vercel_project
    ? vercelDashboardProjectUrl(product.vercel_project, vercelTeam)
    : null;

  return (
    <div className="space-y-8" data-testid="product-hub-overview">
      <section className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-5 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="border-zinc-600 text-zinc-200">
            {product.status}
          </Badge>
          {domainHref ? (
            <a
              href={domainHref}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-sm font-medium text-[var(--status-info)] hover:underline"
            >
              <ExternalLink className="h-3.5 w-3.5 opacity-70" aria-hidden />
              {product.domain ?? domainHref.replace(/^https?:\/\//, "")}
            </a>
          ) : (
            <span className="text-xs text-zinc-500">No domain on Brain row</span>
          )}
        </div>
        {product.tagline ? <p className="text-sm text-zinc-400">{product.tagline}</p> : null}

        {product.tech_stack.length ? (
          <div className="flex flex-wrap gap-1.5">
            {product.tech_stack.map((t) => (
              <span
                key={t}
                className="rounded-md border border-zinc-700/90 bg-zinc-900/50 px-2 py-0.5 text-[11px] text-zinc-300"
              >
                {t}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-xs text-zinc-500">No tech stack entries on Brain row.</p>
        )}

        <div className="flex flex-wrap gap-2">
          {repoHref ? (
            <a
              href={repoHref}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800/90 bg-zinc-950/50 px-3 py-2 text-xs font-medium text-zinc-200 hover:border-zinc-600"
            >
              <GitBranch className="h-3.5 w-3.5 opacity-70" aria-hidden />
              Repo
              <ExternalLink className="h-3 w-3 opacity-50" aria-hidden />
            </a>
          ) : (
            <span className="text-xs text-zinc-500">No repo_path on Brain row</span>
          )}
          {vercelHref ? (
            <a
              href={vercelHref}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800/90 bg-zinc-950/50 px-3 py-2 text-xs font-medium text-zinc-200 hover:border-zinc-600"
            >
              <Rocket className="h-3.5 w-3.5 opacity-70" aria-hidden />
              Vercel ({product.vercel_project})
              <ExternalLink className="h-3 w-3 opacity-50" aria-hidden />
            </a>
          ) : (
            <span className="text-xs text-zinc-500">No vercel_project on Brain row</span>
          )}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <HqStatCard
          label="Linked epics"
          value={linkedEpics}
          icon={<Target className="h-3.5 w-3.5 text-zinc-500" />}
          variant="compact"
          helpText="From Brain — product filter"
        />
        <HqStatCard
          label="Indexed docs"
          value={docCount}
          icon={<BookOpen className="h-3.5 w-3.5 text-zinc-500" />}
          variant="compact"
          helpText="docs/_index.yaml tags + path fallback"
        />
        <HqStatCard
          label="Active sprints"
          value={activeSprints}
          icon={<Activity className="h-3.5 w-3.5 text-zinc-500" />}
          variant="compact"
          helpText="Sprints marked active / in progress / planned"
        />
      </div>

      <section className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-zinc-100">Health snapshot</h2>
          <Link
            href={`/admin/products/${product.slug}?tab=health`}
            className="text-xs text-[var(--status-info)] hover:underline"
          >
            Open Health tab →
          </Link>
        </div>
        <p className="mt-2 text-sm text-zinc-400">{healthNarrative}</p>
        <p className="mt-1 text-xs text-zinc-500">
          Rollup:{" "}
          <span className="font-medium text-zinc-300">
            {healthRollup === "healthy"
              ? "Healthy"
              : healthRollup === "degraded"
                ? "Degraded"
                : healthRollup === "down"
                  ? "Down"
                  : "Unknown"}
          </span>
        </p>
      </section>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <HqStatCard
          label="MRR"
          value={formatCurrencyUsd(product.mrr)}
          icon={<Wallet className="h-3.5 w-3.5 text-zinc-500" />}
          variant="compact"
          helpText="Registry — not live billing"
        />
        <HqStatCard
          label="Active users"
          value={product.active_users}
          icon={<UsersRound className="h-3.5 w-3.5 text-zinc-500" />}
          variant="compact"
          helpText="Registry field"
        />
        <HqStatCard
          label="Open issues"
          value={openIssuesDisplay}
          icon={<Target className="h-3.5 w-3.5 text-zinc-500" />}
          variant="compact"
          helpText={openIssues === null ? "GitHub token not wired" : "GitHub label product:<slug>"}
        />
        <HqStatCard
          label="Last shipped"
          value={lastShippedIso ?? "—"}
          icon={<Activity className="h-3.5 w-3.5 text-zinc-500" />}
          variant="compact"
          helpText={lastShippedIso ? "From Brain product metadata releases" : "No releases[] on product"}
        />
      </div>

      <section aria-label="Signal wiring" className="space-y-3">
        <h3 className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
          Signal wiring
        </h3>
        <Card className="border-zinc-800/80 bg-zinc-900/35">
          <CardContent className="p-0">
            <ul className="divide-y divide-zinc-800/70">
              {metricWires.map((row) => (
                <li
                  key={row.id}
                  className="flex items-center justify-between gap-3 px-4 py-3 text-sm"
                >
                  <span className="flex items-center gap-2 text-zinc-300">
                    <SignalDot kind={row.signal} />
                    {row.label}
                  </span>
                  <span className="text-xs text-zinc-500">{SIGNAL_COPY[row.signal].label}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function PlansSprintsPanel({
  productSlug,
  plansLoad,
  filteredGoals,
}: {
  productSlug: string;
  plansLoad: ProductPlansLoadResult;
  filteredGoals: EpicHierarchyResponse;
}) {
  if (!plansLoad.configured) {
    return (
      <HqEmptyState
        title="Brain not configured"
        description="Set BRAIN_API_URL and BRAIN_API_SECRET to load epics and sprints."
      />
    );
  }
  if (plansLoad.fetchError) {
    return (
      <div role="alert" className="rounded-xl border border-red-500/40 bg-red-950/25 p-4 text-sm text-red-100">
        <p className="font-semibold">Brain unreachable</p>
        <p className="mt-2 text-xs text-red-200/90">{plansLoad.fetchError}</p>
      </div>
    );
  }
  if (filteredGoals.length === 0) {
    return (
      <HqEmptyState
        title="No linked epics"
        description={`No Brain epics match product "${productSlug}" (product_slug or brief_tag). Link epics in Brain to see plans here.`}
      />
    );
  }

  return (
    <div className="space-y-6">
      {filteredGoals.map((goal) => (
        <section key={goal.id} className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-4">
          <h3 className="text-sm font-semibold text-zinc-100">{goal.objective}</h3>
          <p className="text-xs text-zinc-500">
            {goal.horizon} · {goal.status}
          </p>
          <ul className="mt-4 space-y-3">
            {goal.epics.map((epic) => (
              <li key={epic.id} className="rounded-lg border border-zinc-800/70 bg-zinc-900/40 p-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-medium text-zinc-200">{epic.title}</span>
                  <span className="text-[10px] uppercase tracking-wide text-zinc-500">
                    {epic.status} · {epic.percent_done ?? 0}%
                  </span>
                </div>
                <Progress value={epic.percent_done ?? 0} className="mt-2 h-1.5 bg-zinc-800" />
                {epic.sprints?.length ? (
                  <ul className="mt-2 space-y-1 border-t border-zinc-800/60 pt-2">
                    {epic.sprints.map((sp) => (
                      <li key={sp.id} className="text-xs text-zinc-400">
                        <span className="font-medium text-zinc-300">{sp.title}</span>
                        <span className="text-zinc-600"> · {sp.status}</span>
                        {sp.tasks?.length ? (
                          <span className="text-zinc-600"> · {sp.tasks.length} tasks</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-zinc-600">No sprints on this epic.</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function DocsHubPanel({ entries }: { entries: DocEntry[] }) {
  if (entries.length === 0) {
    return (
      <HqEmptyState
        title="No indexed docs"
        description="No documentation entries matched this product tag in docs/_index.yaml (or path/name fallback)."
      />
    );
  }
  return (
    <ul className="space-y-2">
      {entries.map((doc) => (
        <li
          key={doc.slug}
          className="flex items-start gap-3 rounded-xl border border-zinc-800/80 bg-zinc-950/40 px-4 py-3"
        >
          <BookOpen className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
          <div className="min-w-0">
            <Link
              href={`/admin/docs/${doc.slug}`}
              className="text-sm font-medium text-[var(--status-info)] hover:underline"
            >
              {doc.title}
            </Link>
            <p className="font-mono text-[11px] text-zinc-500">/{doc.slug}</p>
            {doc.tags.length ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {doc.tags.map((t) => (
                  <span
                    key={t}
                    className="rounded border border-zinc-800/80 bg-zinc-950/60 px-1.5 py-0.5 text-[10px] text-zinc-400"
                  >
                    {t}
                  </span>
                ))}
              </div>
            ) : null}
            <p className="mt-1 font-mono text-[10px] text-zinc-600">{doc.path}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function GtmHubPanel({ product }: { product: ProductRegistryEntry }) {
  const visitors = 0;
  const signups = 0;
  const conversion = 0;

  return (
    <div className="space-y-8" data-testid="product-hub-gtm">
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline" className="border-[var(--status-warning)]/50 text-[var(--status-warning)]">
          MISSING_CRED
        </Badge>
        <span className="text-xs text-zinc-500">GTM analytics not wired for this product.</span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <HqStatCard
          label="Visitors"
          value={visitors}
          variant="compact"
          helpText="PostHog / marketing — not connected"
        />
        <HqStatCard
          label="Signups"
          value={signups}
          variant="compact"
          helpText="Acquisition — not connected"
        />
        <HqStatCard
          label="Conversion"
          value={`${conversion}%`}
          variant="compact"
          helpText="Derived funnel — not connected"
        />
      </div>
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-zinc-500">
          <span>Funnel (placeholder)</span>
          <span>{conversion}%</span>
        </div>
        <Progress value={conversion} className="h-2 bg-zinc-800" />
      </div>
      <HqEmptyState
        title="Honest empty state"
        description={`Live GTM metrics for ${product.name} are intentionally not fabricated. Connect PostHog / billing attribution to replace zeros.`}
      />
    </div>
  );
}

export function ProductCockpitClient({
  product,
  openIssues,
  plansLoad,
  filteredGoals,
  docEntries,
  healthState,
  healthNarrative,
}: {
  product: ProductRegistryEntry;
  openIssues: number | null;
  plansLoad: ProductPlansLoadResult;
  filteredGoals: EpicHierarchyResponse;
  docEntries: DocEntry[];
  healthState: ProductHealthBrainState;
  healthNarrative: string;
}) {
  const { rollup: healthRollup } = deriveHeroRollup(healthState);

  const signals = computeHubTabSignals({
    product,
    openIssues,
    plans: plansLoad,
    filteredEpicCount: filteredGoals.reduce((n, g) => n + g.epics.length, 0),
    docCount: docEntries.length,
    healthState,
  });

  const tabs = [
    {
      id: "overview" as const,
      label: "Overview",
      signal: signals.overview,
      content: (
        <OverviewPanel
          product={product}
          openIssues={openIssues}
          healthRollup={healthRollup}
          healthNarrative={healthNarrative}
          filteredGoals={filteredGoals}
          docCount={docEntries.length}
        />
      ),
    },
    {
      id: "plans" as const,
      label: "Plans & Sprints",
      signal: signals.plans,
      content: (
        <PlansSprintsPanel
          productSlug={product.slug}
          plansLoad={plansLoad}
          filteredGoals={filteredGoals}
        />
      ),
    },
    {
      id: "docs" as const,
      label: "Docs",
      signal: signals.docs,
      content: <DocsHubPanel entries={docEntries} />,
    },
    {
      id: "health" as const,
      label: "Health",
      signal: signals.health,
      content: (
        <ProductHubHealthPanel
          state={healthState}
          heroRollup={healthRollup}
          narrative={healthNarrative}
        />
      ),
    },
    {
      id: "gtm" as const,
      label: "GTM",
      signal: signals.gtm,
      content: <GtmHubPanel product={product} />,
    },
  ];

  return (
    <div className="space-y-6">
      <ProductHubHeader product={product} />
      <TabbedPageShell tabs={tabs} defaultTab="overview" />
    </div>
  );
}
