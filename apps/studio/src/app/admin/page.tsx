import {
  getInfrastructureStatus,
  getN8nExecutions,
  getN8nWorkflows,
  getRecentPullRequests,
  getRecentCIRuns,
} from "@/lib/command-center";
import OverviewClient from "./overview-client";

export default async function AdminOverviewPage() {
  const [workflows, executions, prs, infrastructure, ciRuns] = await Promise.all([
    getN8nWorkflows(),
    getN8nExecutions(50),
    getRecentPullRequests(10),
    getInfrastructureStatus(),
    getRecentCIRuns(8),
  ]);

  return (
    <OverviewClient
      initial={{
        workflows,
        executions,
        prs,
        infrastructure,
        ciRuns,
        fetchedAt: new Date().toISOString(),
      }}
    />
  );
}
