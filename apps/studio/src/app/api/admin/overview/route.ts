import { NextResponse } from "next/server";
import {
  getInfrastructureStatus,
  getN8nExecutions,
  getN8nWorkflows,
  getRecentPullRequests,
} from "@/lib/command-center";

export const dynamic = "force-dynamic";

export async function GET() {
  const [workflows, executions, prs, infrastructure] = await Promise.all([
    getN8nWorkflows(),
    getN8nExecutions(50),
    getRecentPullRequests(10),
    getInfrastructureStatus(),
  ]);

  return NextResponse.json({
    workflows,
    executions,
    prs,
    infrastructure,
    fetchedAt: new Date().toISOString(),
  });
}
