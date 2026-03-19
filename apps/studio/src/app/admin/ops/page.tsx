import { getN8nExecutions, getN8nWorkflows } from "@/lib/command-center";

function getMcpConnectionStatus() {
  const slackConfigured = !!process.env.SLACK_BOT_TOKEN?.trim();
  const githubConfigured = !!process.env.GITHUB_TOKEN?.trim();
  const vercelConfigured = !!process.env.VERCEL_TOKEN?.trim();
  return [
    { service: "Slack", configured: slackConfigured },
    { service: "GitHub", configured: githubConfigured },
    { service: "GDrive", configured: true, note: "configured via MCP" },
    { service: "Vercel", configured: vercelConfigured },
  ];
}

const costs = [
  { service: "Render (FileFree API)", monthly: "$7.00", type: "compute" },
  { service: "Render (LaunchFree API)", monthly: "$7.00", type: "compute" },
  { service: "Hetzner (n8n + Postiz)", monthly: "$5.49", type: "ops" },
  { service: "Google Workspace", monthly: "$6.00", type: "productivity" },
  { service: "Vercel (5 apps)", monthly: "$0.00", type: "hosting", note: "Hobby tier" },
  { service: "Neon PostgreSQL", monthly: "$0.00", type: "database", note: "Free tier" },
  { service: "Upstash Redis", monthly: "$0.00", type: "cache", note: "Free tier" },
  { service: "GCP Cloud Vision", monthly: "~$0.00", type: "ai", note: "1K free pages/mo" },
];

export default async function OpsPage() {
  const [workflows, executions] = await Promise.all([getN8nWorkflows(), getN8nExecutions(25)]);

  const latest = executions.slice(0, 10);
  const workflowCountLabel = workflows.length > 0 ? String(workflows.length) : "n/a";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Operations Dashboard</h1>
      <p className="text-zinc-400">Slack-first agent operations and infra heartbeat.</p>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="mb-3 text-sm font-medium text-zinc-200">Workflow Roster ({workflowCountLabel})</p>
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
            {getMcpConnectionStatus().map(({ service, configured, note }) => (
              <div key={service} className="rounded-md bg-zinc-800/60 px-3 py-2 text-sm">
                {service}: {configured ? "configured" : "not configured"}
                {note && <span className="ml-2 text-zinc-500">({note})</span>}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="mb-3 text-sm font-medium text-zinc-200">Cost Snapshot</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700 text-left text-zinc-400">
                <th className="pb-2 pr-4 font-medium">Service</th>
                <th className="pb-2 pr-4 font-medium">Monthly</th>
                <th className="pb-2 pr-4 font-medium">Type</th>
                <th className="pb-2 font-medium">Note</th>
              </tr>
            </thead>
            <tbody>
              {costs.map((c) => (
                <tr key={c.service} className="border-b border-zinc-800/60">
                  <td className="py-2 pr-4 text-zinc-100">{c.service}</td>
                  <td className="py-2 pr-4 text-zinc-300">{c.monthly}</td>
                  <td className="py-2 pr-4 text-zinc-400">{c.type}</td>
                  <td className="py-2 text-zinc-500">{c.note ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm font-medium text-zinc-200">
          Total: ~$
          {costs
            .reduce(
              (sum, c) =>
                sum + parseFloat((c.monthly.match(/[\d.]+/)?.[0] ?? "0")),
              0
            )
            .toFixed(2)}
          /mo
        </p>
      </section>
    </div>
  );
}

