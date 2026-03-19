import { NextResponse } from "next/server";
import {
  cached,
  getInfrastructureStatus,
  getN8nExecutions,
  getN8nWorkflows,
  getRecentPullRequests,
  getRecentCIRuns,
} from "@/lib/command-center";

export const dynamic = "force-dynamic";

const CACHE_TTL = 60_000;

export async function GET() {
  const data = await cached("admin:overview", CACHE_TTL, async () => {
    const [workflows, executions, prs, infrastructure, ciRuns] = await Promise.all([
      getN8nWorkflows(),
      getN8nExecutions(50),
      getRecentPullRequests(10),
      getInfrastructureStatus(),
      getRecentCIRuns(8),
    ]);
    return { workflows, executions, prs, infrastructure, ciRuns };
  });

  return NextResponse.json({
    ...data,
    fetchedAt: new Date().toISOString(),
  });
}
