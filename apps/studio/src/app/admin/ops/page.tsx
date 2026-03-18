import { getN8nExecutions, getN8nWorkflows } from "@/lib/command-center";

const mcpServices = ["Slack", "GitHub", "GDrive", "Vercel"];

export default async function OpsPage() {
  const [workflows, executions] = await Promise.all([getN8nWorkflows(), getN8nExecutions(25)]);

  const latest = executions.slice(0, 10);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Operations Dashboard</h1>
      <p className="text-zinc-400">Slack-first agent operations and infra heartbeat.</p>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="mb-3 text-sm font-medium text-zinc-200">Workflow Roster (13)</p>
        <div className="grid gap-2 md:grid-cols-2">
          {workflows.map((workflow) => (
            <div key={workflow.id} className="rounded-md bg-zinc-800/60 px-3 py-2 text-sm">
              <span className="font-medium text-zinc-100">{workflow.name}</span>
              <span className="ml-2 text-zinc-400">{workflow.active ? "active" : "inactive"}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-3 text-sm font-medium text-zinc-200">Recent Executions</p>
          <div className="space-y-2">
            {latest.map((execution) => (
              <div key={execution.id} className="rounded-md bg-zinc-800/60 px-3 py-2 text-sm">
                #{execution.id} - {execution.finished ? "finished" : "running"}
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-3 text-sm font-medium text-zinc-200">MCP Connections</p>
          <div className="space-y-2">
            {mcpServices.map((service) => (
              <div key={service} className="rounded-md bg-zinc-800/60 px-3 py-2 text-sm">
                {service}: configured
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="text-sm text-zinc-300">
          Cost snapshot: Render x2 ($14), Hetzner ($5.49), plus provider free tiers.
        </p>
      </section>
    </div>
  );
}

