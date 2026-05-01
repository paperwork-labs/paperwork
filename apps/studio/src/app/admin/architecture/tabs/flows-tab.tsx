// Content moved from /admin/workflows (WS-69 PR C). The /admin/workflows route
// now redirects here via next.config.mjs.
//
// Roster filter/sort links use /admin/architecture?tab=flows&... so query
// params are not stripped by the /admin/workflows → architecture redirect.

import {
  getBrainPersonas,
  getN8nExecutions,
  getN8nWorkflows,
  WORKFLOW_META,
} from "@/lib/command-center";
import OpsClient from "../../ops/ops-client";
import {
  checkGithubToken,
  checkGoogleDrive,
  checkSlackToken,
  checkVercelToken,
} from "@/lib/service-tokens";
import WorkflowsRoster from "../../workflows/workflows-roster";
import { N8nGraphList } from "../../workflows/n8n-graph";

export default async function WorkflowsTab() {
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
      <p className="text-sm text-zinc-400">
        n8n wiring + Brain personas + the running execution feed.
      </p>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
          Workflow roster
        </h2>
        <WorkflowsRoster
          workflows={workflows}
          executions={executions}
          personas={personas}
          workflowMeta={WORKFLOW_META}
          filterWorkflowId={undefined}
          sort="desc"
        />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
          Live activity
        </h2>
        <OpsClient
          initial={{
            workflows,
            executions,
            serviceTokens: [slack, github, vercel, gdrive],
            workflowMeta: WORKFLOW_META,
            fetchedAt: new Date().toISOString(),
          }}
        />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
          Graph view
        </h2>
        <N8nGraphList />
      </section>
    </div>
  );
}
