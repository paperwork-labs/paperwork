import Link from "next/link";

import {
  getBrainPersonas,
  getN8nExecutions,
  getN8nWorkflows,
  WORKFLOW_META,
} from "@/lib/command-center";
import OpsClient from "../ops/ops-client";
import {
  checkGithubToken,
  checkGoogleDrive,
  checkSlackToken,
  checkVercelToken,
} from "@/lib/service-tokens";
import WorkflowsRoster from "./workflows-roster";
import { N8nGraphList } from "./n8n-graph";

type Tab = "roster" | "activity" | "graph";

type PageProps = {
  searchParams: Promise<{ tab?: string; workflow?: string; sort?: string }>;
};

function resolveTab(raw: string | undefined): Tab {
  if (raw === "activity" || raw === "graph" || raw === "roster") return raw;
  return "roster";
}

export default async function WorkflowsPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const tab = resolveTab(params.tab);

  const [workflows, executions, personas, slack, github, vercel] = await Promise.all([
    getN8nWorkflows(),
    getN8nExecutions(50),
    getBrainPersonas(),
    checkSlackToken(),
    checkGithubToken(),
    checkVercelToken(),
  ]);
  const gdrive = await checkGoogleDrive();

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Workflows
        </h1>
        <p className="text-sm text-zinc-400">
          n8n wiring + Brain personas + the running execution feed. Replaces the
          old Ops and Agents pages.
        </p>
        <nav className="mt-3 inline-flex rounded-lg border border-zinc-800 bg-zinc-900/60 p-1 text-sm">
          <TabLink tab="roster" active={tab === "roster"} label="Roster" />
          <TabLink tab="activity" active={tab === "activity"} label="Activity" />
          <TabLink tab="graph" active={tab === "graph"} label="Graph" />
        </nav>
      </header>

      {tab === "roster" && (
        <WorkflowsRoster
          workflows={workflows}
          executions={executions}
          personas={personas}
          workflowMeta={WORKFLOW_META}
          filterWorkflowId={params.workflow}
          sort={params.sort === "asc" ? "asc" : "desc"}
        />
      )}

      {tab === "activity" && (
        <OpsClient
          initial={{
            workflows,
            executions,
            serviceTokens: [slack, github, vercel, gdrive],
            workflowMeta: WORKFLOW_META,
            fetchedAt: new Date().toISOString(),
          }}
        />
      )}

      {tab === "graph" && <N8nGraphList />}
    </div>
  );
}

function TabLink({ tab, active, label }: { tab: Tab; active: boolean; label: string }) {
  return (
    <Link
      href={{ pathname: "/admin/workflows", query: { tab } }}
      className={`rounded-md px-3 py-1.5 transition ${
        active
          ? "bg-zinc-800 text-zinc-100"
          : "text-zinc-400 hover:text-zinc-200"
      }`}
    >
      {label}
    </Link>
  );
}
