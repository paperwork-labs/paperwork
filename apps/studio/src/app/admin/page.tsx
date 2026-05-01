import { BrainImprovementGauge } from "@/components/admin/BrainImprovementGauge";
import { OperatingScoreGauge } from "@/components/admin/OperatingScoreGauge";
import { SprintVelocityTile } from "@/components/admin/SprintVelocityTile";
import {
  getBrainPRReviews,
  getInfrastructureStatus,
  getN8nExecutions,
  getN8nWorkflows,
  getRecentCIRuns,
  getRecentPullRequests,
  getRecentSlackActivity,
  isN8nIntegrationConfigured,
} from "@/lib/command-center";
import { PushSubscribeCard } from "@/components/pwa/PushSubscribeCard";
import { TrackersRail } from "./_components/trackers-rail";
import OverviewClient from "./overview-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function AdminOverviewPage() {
  const [workflows, executions, prsResult, infrastructure, ciRunsResult, brainReviews, slackActivity] =
    await Promise.all([
      getN8nWorkflows(),
      getN8nExecutions(50),
      getRecentPullRequests(10),
      getInfrastructureStatus(),
      getRecentCIRuns(8),
      getBrainPRReviews(50),
      getRecentSlackActivity(15),
    ]);
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

  return (
    <div className="space-y-6">
      <PushSubscribeCard />
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
