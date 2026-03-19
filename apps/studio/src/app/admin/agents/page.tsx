import { getN8nExecutions, getN8nWorkflows, WORKFLOW_META } from "@/lib/command-center";
import Link from "next/link";

type AgentsPageProps = {
  searchParams: Promise<{ workflow?: string; sort?: string }>;
};

function parseTs(value?: string) {
  if (!value) return 0;
  const ts = Date.parse(value);
  return Number.isNaN(ts) ? 0 : ts;
}

function relativeTime(value?: string) {
  if (!value) return "never";
  const ts = parseTs(value);
  if (!ts) return "unknown";
  const minutes = Math.floor((Date.now() - ts) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function statusTone(status: string) {
  if (status === "success") return "text-emerald-300";
  if (status === "error" || status === "failed" || status === "crashed") return "text-rose-300";
  return "text-amber-300";
}

export default async function AgentsPage({ searchParams }: AgentsPageProps) {
  const params = await searchParams;
  const [workflows, executions] = await Promise.all([getN8nWorkflows(), getN8nExecutions(40)]);
  const workflowId = params.workflow ?? "all";
  const sortDirection = params.sort === "asc" ? "asc" : "desc";
  const executionsWithDerivedStatus = executions.map((execution) => {
    const status = (execution.status ?? (execution.finished ? "success" : "running")).toLowerCase();
    const timestamp = execution.startedAt ?? execution.stoppedAt;
    return {
      ...execution,
      derivedStatus: status,
      timestamp,
    };
  });
  const filteredExecutions =
    workflowId === "all"
      ? executionsWithDerivedStatus
      : executionsWithDerivedStatus.filter((execution) => execution.workflowId === workflowId);
  const sortedExecutions = [...filteredExecutions].sort((a, b) => {
    const diff = parseTs(a.timestamp) - parseTs(b.timestamp);
    return sortDirection === "asc" ? diff : -diff;
  });

  const now = Date.now();
  const workflowNameById = new Map(workflows.map((w) => [w.id, w.name]));
  const workflowStats = workflows.map((workflow) => {
    const runs = executionsWithDerivedStatus
      .filter((execution) => execution.workflowId === workflow.id)
      .sort((a, b) => parseTs(b.timestamp) - parseTs(a.timestamp));
    const latest = runs[0];
    const successCount = runs.filter((run) => run.derivedStatus === "success").length;
    const failureCount = runs.filter(
      (run) => run.derivedStatus === "error" || run.derivedStatus === "failed" || run.derivedStatus === "crashed",
    ).length;
    const latestTs = parseTs(latest?.timestamp);
    const latestStatus = latest?.derivedStatus ?? "unknown";
    const recentSuccess =
      latestStatus === "success" && latestTs > 0 && now - latestTs <= 24 * 60 * 60 * 1000;
    const recentFailure =
      (latestStatus === "error" || latestStatus === "failed" || latestStatus === "crashed") &&
      latestTs > 0 &&
      now - latestTs <= 24 * 60 * 60 * 1000;
    const healthTone = recentSuccess ? "bg-emerald-400" : recentFailure ? "bg-rose-400" : "bg-amber-400";
    const healthLabel = recentSuccess ? "healthy" : recentFailure ? "degraded" : "idle";

    return {
      workflow,
      latest,
      successCount,
      failureCount,
      healthTone,
      healthLabel,
    };
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Agent Activity</h1>
      <p className="text-zinc-400">Workflow-level status, recent executions, and persona activity.</p>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="mb-3 text-sm font-medium text-zinc-200">Workflow Health + Stats</p>
        <div className="grid gap-3 md:grid-cols-2">
          {workflowStats.map(({ workflow, latest, successCount, failureCount, healthLabel, healthTone }) => {
            const meta = WORKFLOW_META[workflow.name];
            return (
              <div key={workflow.id} className="rounded-md bg-zinc-800/60 px-3 py-3 text-sm">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-zinc-100">{workflow.name}</p>
                  <span className="flex items-center gap-2 text-xs uppercase tracking-wide text-zinc-400">
                    <span className={`h-2.5 w-2.5 rounded-full ${healthTone}`} />
                    {healthLabel}
                  </span>
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  {meta?.model && (
                    <span className="rounded-full bg-zinc-700/60 px-2 py-0.5 text-xs font-mono text-zinc-300">
                      {meta.model}
                    </span>
                  )}
                  {meta?.trigger && (
                    <span className="rounded-full bg-zinc-700/40 px-2 py-0.5 text-xs text-zinc-400">
                      {meta.trigger}
                    </span>
                  )}
                  {meta?.costPerRun && meta.costPerRun !== "$0" && (
                    <span className="rounded-full bg-zinc-700/40 px-2 py-0.5 text-xs text-zinc-500">
                      {meta.costPerRun}/run
                    </span>
                  )}
                  {meta?.deviation && (
                    <span className="rounded-full bg-amber-900/30 px-2 py-0.5 text-xs text-amber-400">
                      {meta.deviation}
                    </span>
                  )}
                </div>
                <p className="mt-1.5 text-zinc-400">
                  {workflow.active ? "active" : "inactive"} · last run{" "}
                  {relativeTime(latest?.timestamp)}
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  {successCount} success / {failureCount} failed
                  {meta?.role && meta.role !== "No AI" && (
                    <span className="ml-2 text-zinc-600">· role: {meta.role}</span>
                  )}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-medium text-zinc-200">Execution History</p>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-md border border-zinc-700 px-2 py-1 text-zinc-300">
              filter: {workflowId === "all" ? "all workflows" : workflowId}
            </span>
            <Link
              href={`/admin/agents?workflow=${workflowId}&sort=${sortDirection === "desc" ? "asc" : "desc"}`}
              className="rounded-md border border-zinc-700 px-2 py-1 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
            >
              sort: {sortDirection === "desc" ? "newest first" : "oldest first"}
            </Link>
          </div>
        </div>
        <div className="mb-3 flex flex-wrap gap-2 text-xs">
          <Link
            href={`/admin/agents?workflow=all&sort=${sortDirection}`}
            className={`rounded-md border px-2 py-1 ${
              workflowId === "all"
                ? "border-zinc-500 bg-zinc-800 text-zinc-100"
                : "border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
            }`}
          >
            All
          </Link>
          {workflows.map((workflow) => (
            <Link
              key={workflow.id}
              href={`/admin/agents?workflow=${workflow.id}&sort=${sortDirection}`}
              className={`rounded-md border px-2 py-1 ${
                workflowId === workflow.id
                  ? "border-zinc-500 bg-zinc-800 text-zinc-100"
                  : "border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
              }`}
            >
              {workflow.name}
            </Link>
          ))}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="py-2 pr-3">When</th>
                <th className="py-2 pr-3">Workflow</th>
                <th className="py-2 pr-3">Execution</th>
                <th className="py-2 pr-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {sortedExecutions.slice(0, 25).map((execution) => (
                <tr key={execution.id}>
                  <td className="py-2 pr-3 text-zinc-300">{relativeTime(execution.timestamp)}</td>
                  <td className="py-2 pr-3 text-zinc-200">
                    {workflowNameById.get(execution.workflowId ?? "") ??
                      execution.workflowId ??
                      "unknown"}
                  </td>
                  <td className="py-2 pr-3 text-zinc-400">#{execution.id}</td>
                  <td className={`py-2 pr-3 font-medium ${statusTone(execution.derivedStatus)}`}>
                    {execution.derivedStatus}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

