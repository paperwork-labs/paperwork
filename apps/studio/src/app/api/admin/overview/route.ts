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
} from "@/lib/command-center";

export const dynamic = "force-dynamic";

const CACHE_TTL = 60_000;

export async function GET() {
  const data = await cached("admin:overview", CACHE_TTL, async () => {
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
        return { workflows, executions, prs: prsWithReview, infrastructure, ciRuns, slackActivity };
      });

  return NextResponse.json({
    ...data,
    fetchedAt: new Date().toISOString(),
  });
}
