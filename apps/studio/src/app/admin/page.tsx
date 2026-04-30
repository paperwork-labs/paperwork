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
} from "@/lib/command-center";
import { PushSubscribeCard } from "@/components/pwa/PushSubscribeCard";
import { TrackersRail } from "./_components/trackers-rail";
import OverviewClient from "./overview-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function AdminOverviewPage() {
  const [workflows, executions, prs, infrastructure, ciRuns, brainReviews, slackActivity] =
    await Promise.all([
      getN8nWorkflows(),
      getN8nExecutions(50),
      getRecentPullRequests(10),
      getInfrastructureStatus(),
      getRecentCIRuns(8),
      getBrainPRReviews(50),
      getRecentSlackActivity(15),
    ]);
  const prsWithReview = prs.map((pr) => {
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

  return (
    <div className="space-y-6">
      <PushSubscribeCard />
      <TrackersRail />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <OperatingScoreGauge />
        <BrainImprovementGauge />
        <SprintVelocityTile />
      </div>
      <OverviewClient
        initial={{
          workflows,
          executions,
          prs: prsWithReview,
          infrastructure,
          ciRuns,
          slackActivity,
          fetchedAt: new Date().toISOString(),
        }}
      />
    </div>
  );
}
