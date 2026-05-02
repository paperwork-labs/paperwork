import Link from "next/link";
import productsData from "@/data/products.json";
import { BrainImprovementGauge } from "@/components/admin/BrainImprovementGauge";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { OperatingScoreGauge } from "@/components/admin/OperatingScoreGauge";
import { SprintVelocityTile } from "@/components/admin/SprintVelocityTile";
import {
  buildAttentionItems,
  NeedsAttentionSection,
  OverviewSectionChrome,
  QuickPulseSection,
  RecentActivitySection,
  SectionDivider,
} from "@/app/admin/_components/overview-founder-sections";
import {
  infraHealthyCounts,
  loadBrainFillPulse,
  loadEpicHierarchyPulse,
  loadOperatingScorePulse,
  loadPeoplePulse,
  loadProductHealthRollup,
  loadRecentDispatches,
  readingPathsUnresolvedSummary,
} from "@/app/admin/_lib/overview-founder-data";
import {
  getBrainPersonaDispatchSummary,
  getBrainPRReviews,
  getInfrastructureStatus,
  getN8nExecutions,
  getN8nWorkflows,
  getRecentCIRuns,
  getRecentPullRequests,
  getRecentSlackActivity,
  isN8nIntegrationConfigured,
} from "@/lib/command-center";
import { BrainClient } from "@/lib/brain-client";
import {
  brainNarrative,
  personaDispatchSummaryFromResponse,
  type PersonaDispatchSummary,
} from "./brain-overview-narrative";
import type { ProductsRegistryFile } from "@/lib/products-registry";
import { PushSubscribeCard } from "@/components/pwa/PushSubscribeCard";
import { TrackersRail } from "./_components/trackers-rail";
import OverviewClient from "./overview-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function BrainSaysOverviewCard({ summary }: { summary: PersonaDispatchSummary | null }) {
  const pendingReview = summary?.pendingReview ?? 0;
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 ring-1 ring-zinc-800">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">Brain says</p>
      <p className="mt-2 text-sm text-zinc-200">{brainNarrative(summary)}</p>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <Link
          href="/admin/autopilot"
          className="text-zinc-400 underline-offset-2 transition hover:text-zinc-200 hover:underline"
        >
          → View Autopilot
        </Link>
        {pendingReview > 0 ? (
          <Link
            href="/admin/autopilot"
            className="text-zinc-400 underline-offset-2 transition hover:text-zinc-200 hover:underline"
          >
            → Review pending
          </Link>
        ) : null}
      </div>
    </section>
  );
}

export default async function AdminOverviewPage() {
  const products = (productsData as ProductsRegistryFile).products;

  const client = BrainClient.fromEnv();
  const [
    workflows,
    executions,
    prsResult,
    infrastructure,
    ciRunsResult,
    brainReviews,
    slackActivity,
    personaDispatchRaw,
    operatingScore,
    epicPulse,
    peoplePulse,
    brainFill,
    dispatches,
    productRollup,
  ] = await Promise.all([
    getN8nWorkflows(),
    getN8nExecutions(50),
    getRecentPullRequests(10),
    getInfrastructureStatus(),
    getRecentCIRuns(8),
    getBrainPRReviews(50),
    getRecentSlackActivity(15),
    getBrainPersonaDispatchSummary(),
    loadOperatingScorePulse(client),
    loadEpicHierarchyPulse(client),
    loadPeoplePulse(client),
    loadBrainFillPulse(client),
    loadRecentDispatches(client, 5),
    loadProductHealthRollup(products),
  ]);

  const personaDispatchSummary = personaDispatchSummaryFromResponse(personaDispatchRaw.data);
  const prsWithReview = prsResult.data.map((pr) => {
    const review = brainReviews.get(pr.number);
    return review
      ? {
          ...pr,
          brain_review: {
            verdict: review.verdict,
            head_sha: review.head_sha,
            model: review.model,
            summary: review.summary,
            created_at: review.created_at,
          },
        }
      : pr;
  });

  const slackDailyBriefingHref =
    process.env.NEXT_PUBLIC_SLACK_DAILY_BRIEFING_URL?.trim() ||
    process.env.SLACK_DAILY_BRIEFING_URL?.trim() ||
    null;

  const { healthy: infraHealthy, total: infraTotal } = infraHealthyCounts(infrastructure);
  const infraFailingRows = infrastructure.filter(
    (s) => s.configured && !s.healthy && !s.deprecated,
  );
  const readingPaths = readingPathsUnresolvedSummary();

  const attentionItems = buildAttentionItems({
    epicPulse,
    productBad: productRollup.degradedOrDown,
    infraFailing: infraFailingRows,
    readingPaths,
  });

  return (
    <div className="space-y-6">
      <HqPageHeader
        title="Overview"
        eyebrow="Studio HQ"
        subtitle="Monday morning founder view — health, blockers, and what Brain shipped recently."
        breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Overview" }]}
      />

      <OverviewSectionChrome>
        <QuickPulseSection
          operatingScore={operatingScore}
          productRollup={productRollup}
          epicPulse={epicPulse}
          peoplePulse={peoplePulse}
          infraHealthy={infraHealthy}
          infraTotal={infraTotal}
          brainFill={brainFill}
        />
        <SectionDivider />
        <NeedsAttentionSection items={attentionItems} />
        <SectionDivider />
        <RecentActivitySection dispatches={dispatches} />
      </OverviewSectionChrome>

      <PushSubscribeCard />
      <BrainSaysOverviewCard summary={personaDispatchSummary} />
      <TrackersRail />
      <section className="space-y-4">
        <div className="rounded-2xl border border-amber-500/20 bg-gradient-to-b from-zinc-950 to-zinc-950/80 p-1 shadow-[0_0_0_1px_rgba(39,39,42,0.6)] ring-1 ring-zinc-800/90 lg:p-2">
          <OperatingScoreGauge />
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <BrainImprovementGauge />
          <SprintVelocityTile />
        </div>
      </section>
      <OverviewClient
        initial={{
          workflows,
          executions,
          prs: prsWithReview,
          infrastructure,
          ciRuns: ciRunsResult.data,
          githubPrMissingCred: prsResult.missingCred,
          githubCiMissingCred: ciRunsResult.missingCred,
          githubPrFetchError: prsResult.fetchError,
          githubCiFetchError: ciRunsResult.fetchError,
          slackActivity,
          n8nConfigured: isN8nIntegrationConfigured(),
          slackDailyBriefingHref,
          fetchedAt: new Date().toISOString(),
        }}
      />
    </div>
  );
}
