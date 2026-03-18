import Link from "next/link";
import { getN8nExecutions, getN8nWorkflows, getRecentPullRequests } from "@/lib/command-center";

export default async function AdminOverviewPage() {
  const [workflows, executions, prs] = await Promise.all([
    getN8nWorkflows(),
    getN8nExecutions(10),
    getRecentPullRequests(5),
  ]);

  const healthy = workflows.filter((w) => w.active).length;
  const workflowHealthLabel = workflows.length > 0 ? `${healthy}/${workflows.length}` : "n/a";
  const sprintRuns = executions.filter(
    (e) => e.workflowId === "f7a8b9c0-d1e2-4f3a-b4c5-d6e7f8a9b0c1" || e.workflowId === "a9b0c1d2-e3f4-4a5b-b6c7-d8e9f0a1b2c3",
  ).length;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Paperwork Labs Admin</h1>
      <p className="text-zinc-400">One-glance health for agents, sprints, and delivery.</p>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Service Health</p>
          <p className="mt-2 text-2xl font-semibold">{workflowHealthLabel}</p>
          <p className="text-sm text-zinc-400">Active n8n workflows</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Current Sprint</p>
          <p className="mt-2 text-2xl font-semibold">5-day cadence</p>
          <p className="text-sm text-zinc-400">{sprintRuns} kickoff/close executions tracked</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Open PRs</p>
          <p className="mt-2 text-2xl font-semibold">{prs.length}</p>
          <p className="text-sm text-zinc-400">Across the main repository</p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-3 text-sm font-medium text-zinc-200">Recent Agent Executions</p>
          <div className="space-y-2">
            {executions.slice(0, 5).map((execution) => (
              <div key={execution.id} className="rounded-md bg-zinc-800/60 px-3 py-2 text-sm">
                <span className="font-medium text-zinc-100">#{execution.id}</span>{" "}
                <span className="text-zinc-400">{execution.finished ? "finished" : "running"}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-3 text-sm font-medium text-zinc-200">Quick Links</p>
          <div className="space-y-2 text-sm">
            <Link href="/admin/ops" className="block text-zinc-300 hover:text-zinc-100">
              /admin/ops
            </Link>
            <Link href="/admin/sprints" className="block text-zinc-300 hover:text-zinc-100">
              /admin/sprints
            </Link>
            <Link href="/admin/agents" className="block text-zinc-300 hover:text-zinc-100">
              /admin/agents
            </Link>
            <a
              href="https://n8n.paperworklabs.com"
              target="_blank"
              rel="noreferrer"
              className="block text-zinc-300 hover:text-zinc-100"
            >
              n8n.paperworklabs.com
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}

