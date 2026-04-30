import { NextResponse } from "next/server";
import {
  cached,
  getBrainPRReviews,
  getInfrastructureStatus,
  getN8nExecutions,
  getN8nWorkflows,
  getRecentCIRuns,
  getRecentPullRequests,
  getRecentSlackActivity,
  isN8nIntegrationConfigured,
} from "@/lib/command-center";

export const dynamic = "force-dynamic";

const CACHE_TTL = 60_000;

export async function GET() {
  const data = await cached("admin:overview", CACHE_TTL, async () => {
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
        return {
          workflows,
          executions,
          prs: prsWithReview,
          infrastructure,
          ciRuns: ciRunsResult.data,
          githubPrMissingCred: prsResult.missingCred,
          githubCiMissingCred: ciRunsResult.missingCred,
          slackActivity,
          n8nConfigured: isN8nIntegrationConfigured(),
          slackDailyBriefingHref:
            process.env.NEXT_PUBLIC_SLACK_DAILY_BRIEFING_URL?.trim() ||
            process.env.SLACK_DAILY_BRIEFING_URL?.trim() ||
            null,
        };
      });

  return NextResponse.json({
    ...data,
    fetchedAt: new Date().toISOString(),
  });
}
