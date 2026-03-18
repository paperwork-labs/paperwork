import Link from "next/link";
import {
  getInfrastructureStatus,
  getN8nExecutions,
  getN8nWorkflows,
  getRecentPullRequests,
} from "@/lib/command-center";

type ActivityItem = {
  id: string;
  timestamp: string;
  label: string;
  detail: string;
  href?: string;
};

function parseTs(value?: string) {
  if (!value) return 0;
  const ts = Date.parse(value);
  return Number.isNaN(ts) ? 0 : ts;
}

function relativeTime(value?: string) {
  if (!value) return "unknown time";
  const ts = parseTs(value);
  if (!ts) return "unknown time";
  const diffMs = Date.now() - ts;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default async function AdminOverviewPage() {
  const [workflows, executions, prs, infrastructure] = await Promise.all([
    getN8nWorkflows(),
    getN8nExecutions(50),
    getRecentPullRequests(10),
    getInfrastructureStatus(),
  ]);

  const activeWorkflows = workflows.filter((workflow) => workflow.active).length;
  const workflowHealthLabel = workflows.length > 0 ? `${activeWorkflows}/${workflows.length}` : "n/a";
  const workflowNameById = new Map(workflows.map((workflow) => [workflow.id, workflow.name]));
  const now = Date.now();
  const dayAgo = now - 24 * 60 * 60 * 1000;
  const executionsLastDay = executions.filter((execution) => {
    const ts = parseTs(execution.startedAt) || parseTs(execution.stoppedAt);
    return ts >= dayAgo;
  });
  const successfulLastDay = executionsLastDay.filter((execution) => {
    const status = (execution.status ?? "").toLowerCase();
    if (status) return status === "success";
    return execution.finished;
  }).length;
  const failedLastDay = executionsLastDay.filter((execution) => {
    const status = (execution.status ?? "").toLowerCase();
    if (!status) return false;
    return status === "error" || status === "failed" || status === "crashed";
  }).length;
  const healthyInfrastructure = infrastructure.filter((service) => service.healthy).length;
  const infrastructureLabel =
    infrastructure.length > 0 ? `${healthyInfrastructure}/${infrastructure.length}` : "n/a";

  const activity: ActivityItem[] = [
    ...executions.slice(0, 20).map((execution) => {
      const status = (execution.status ?? "").toLowerCase();
      const label = status ? status : execution.finished ? "finished" : "running";
      const ts = execution.startedAt ?? execution.stoppedAt ?? "";
      return {
        id: `exec-${execution.id}`,
        timestamp: ts,
        label: `Workflow ${label}`,
        detail: `${workflowNameById.get(execution.workflowId ?? "") ?? "Unknown workflow"} (#${execution.id})`,
      };
    }),
    ...prs.slice(0, 10).map((pr) => ({
      id: `pr-${pr.number}`,
      timestamp: pr.created_at,
      label: `PR #${pr.number} opened`,
      detail: pr.title,
      href: pr.html_url,
    })),
  ]
    .filter((item) => Boolean(item.timestamp))
    .sort((a, b) => parseTs(b.timestamp) - parseTs(a.timestamp))
    .slice(0, 10);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Paperwork Labs Admin</h1>
      <p className="text-zinc-400">One-glance health for agents, sprints, and delivery.</p>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Active workflows</p>
          <p className="mt-2 text-2xl font-semibold">{workflowHealthLabel}</p>
          <p className="text-sm text-zinc-400">n8n workflows currently enabled</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Last 24h executions</p>
          <p className="mt-2 text-2xl font-semibold">{executionsLastDay.length}</p>
          <p className="text-sm text-zinc-400">
            {successfulLastDay} success / {failedLastDay} failed
          </p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Open PRs</p>
          <p className="mt-2 text-2xl font-semibold">{prs.length}</p>
          <p className="text-sm text-zinc-400">Across `paperwork-labs/paperwork`</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Infra health</p>
          <p className="mt-2 text-2xl font-semibold">{infrastructureLabel}</p>
          <p className="text-sm text-zinc-400">Provider checks passing</p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-3 text-sm font-medium text-zinc-200">Activity Feed</p>
          <div className="space-y-2">
            {activity.length === 0 ? (
              <p className="rounded-md bg-zinc-800/60 px-3 py-2 text-sm text-zinc-400">
                No recent execution or PR activity found.
              </p>
            ) : (
              activity.map((item) => (
                <div key={item.id} className="rounded-md bg-zinc-800/60 px-3 py-2 text-sm">
                  <p className="font-medium text-zinc-100">{item.label}</p>
                  {item.href ? (
                    <a
                      href={item.href}
                      target="_blank"
                      rel="noreferrer"
                      className="text-zinc-300 hover:text-zinc-100"
                    >
                      {item.detail}
                    </a>
                  ) : (
                    <p className="text-zinc-300">{item.detail}</p>
                  )}
                  <p className="text-xs text-zinc-500">{relativeTime(item.timestamp)}</p>
                </div>
              ))
            )}
          </div>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-3 text-sm font-medium text-zinc-200">Quick Links</p>
          <div className="space-y-2 text-sm">
            <Link href="/admin/ops" className="block text-zinc-300 hover:text-zinc-100">
              Operations dashboard
            </Link>
            <Link href="/admin/sprints" className="block text-zinc-300 hover:text-zinc-100">
              Sprint tracker
            </Link>
            <Link href="/admin/agents" className="block text-zinc-300 hover:text-zinc-100">
              Agent monitor
            </Link>
            <Link href="/admin/infrastructure" className="block text-zinc-300 hover:text-zinc-100">
              Infrastructure health
            </Link>
            <a
              href="https://n8n.paperworklabs.com"
              target="_blank"
              rel="noreferrer"
              className="block text-zinc-300 hover:text-zinc-100"
            >
              n8n editor
            </a>
            <a
              href="https://dashboard.render.com"
              target="_blank"
              rel="noreferrer"
              className="block text-zinc-300 hover:text-zinc-100"
            >
              Render dashboard
            </a>
            <a
              href="https://vercel.com/dashboard"
              target="_blank"
              rel="noreferrer"
              className="block text-zinc-300 hover:text-zinc-100"
            >
              Vercel dashboard
            </a>
            <a
              href="https://github.com/paperwork-labs/paperwork"
              target="_blank"
              rel="noreferrer"
              className="block text-zinc-300 hover:text-zinc-100"
            >
              GitHub repository
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}

