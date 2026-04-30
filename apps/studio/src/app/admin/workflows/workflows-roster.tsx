import Link from "next/link";

import type {
  BrainPersonaSpec,
  N8nExecution,
  N8nWorkflow,
  WorkflowMeta,
} from "@/lib/command-center";

type RosterProps = {
  workflows: N8nWorkflow[];
  executions: N8nExecution[];
  personas: BrainPersonaSpec[];
  workflowMeta: Record<string, WorkflowMeta>;
  filterWorkflowId?: string;
  sort: "asc" | "desc";
};

function parseTs(value?: string): number {
  if (!value) return 0;
  const ts = Date.parse(value);
  return Number.isNaN(ts) ? 0 : ts;
}

function relativeTime(value?: string): string {
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

function statusTone(status: string): string {
  if (status === "success") return "text-emerald-300";
  if (status === "error" || status === "failed" || status === "crashed") return "text-rose-300";
  return "text-amber-300";
}

export default function WorkflowsRoster({
  workflows,
  executions,
  personas,
  workflowMeta,
  filterWorkflowId,
  sort,
}: RosterProps) {
  const workflowId = filterWorkflowId ?? "all";
  const executionsWithStatus = executions.map((execution) => {
    const status = (execution.status ?? (execution.finished ? "success" : "running")).toLowerCase();
    const timestamp = execution.startedAt ?? execution.stoppedAt;
    return { ...execution, derivedStatus: status, timestamp };
  });
  const filtered =
    workflowId === "all"
      ? executionsWithStatus
      : executionsWithStatus.filter(
          (e) =>
            String(e.workflowId ?? "") === String(workflowId) ||
            e.workflowData?.name === workflowId,
        );
  const sorted = [...filtered].sort((a, b) => {
    const diff = parseTs(a.timestamp) - parseTs(b.timestamp);
    return sort === "asc" ? diff : -diff;
  });

  const now = Date.now();
  const workflowNameById = new Map(
    workflows.map((w) => [String(w.id), w.name]),
  );
  const workflowStats = workflows.map((workflow) => {
    const runs = executionsWithStatus
      .filter(
        (e) =>
          String(e.workflowId ?? "") === String(workflow.id) ||
          e.workflowData?.name === workflow.name,
      )
      .sort((a, b) => parseTs(b.timestamp) - parseTs(a.timestamp));
    const latest = runs[0];
    const successCount = runs.filter((r) => r.derivedStatus === "success").length;
    const failureCount = runs.filter(
      (r) =>
        r.derivedStatus === "error" ||
        r.derivedStatus === "failed" ||
        r.derivedStatus === "crashed",
    ).length;
    const latestTs = parseTs(latest?.timestamp);
    const latestStatus = latest?.derivedStatus ?? "unknown";
    const recentSuccess =
      latestStatus === "success" && latestTs > 0 && now - latestTs <= 24 * 60 * 60 * 1000;
    const recentFailure =
      ["error", "failed", "crashed"].includes(latestStatus) &&
      latestTs > 0 &&
      now - latestTs <= 24 * 60 * 60 * 1000;
    const healthTone = recentSuccess
      ? "bg-emerald-400"
      : recentFailure
      ? "bg-rose-400"
      : "bg-amber-400";
    const healthLabel = recentSuccess ? "healthy" : recentFailure ? "degraded" : "idle";
    return { workflow, latest, successCount, failureCount, healthTone, healthLabel };
  });

  const sortedPersonas = [...personas].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-medium text-zinc-200">
            Brain Personas
            <span className="ml-2 text-xs text-zinc-500">
              ({sortedPersonas.length} specs loaded)
            </span>
          </p>
          {sortedPersonas.length === 0 && (
            <span className="text-xs text-amber-400">
              Set BRAIN_API_URL + BRAIN_API_SECRET to load.
            </span>
          )}
        </div>
        {sortedPersonas.length > 0 && (
          <div className="grid gap-3 md:grid-cols-2">
            {sortedPersonas.map((p) => (
              <div key={p.name} className="rounded-md bg-zinc-800/60 px-3 py-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate font-medium text-zinc-100">{p.name}</p>
                  <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide">
                    {p.compliance_flagged && (
                      <span className="rounded-full bg-rose-900/40 px-2 py-0.5 text-rose-300">
                        compliance
                      </span>
                    )}
                    <span className="rounded-full bg-zinc-700/60 px-2 py-0.5 text-zinc-300">
                      {p.mode}
                    </span>
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-zinc-400">{p.description}</p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
                  <span className="rounded-full bg-zinc-700/60 px-2 py-0.5 font-mono text-zinc-200">
                    {p.default_model}
                  </span>
                  {p.escalation_model && (
                    <>
                      <span className="text-zinc-600">→</span>
                      <span className="rounded-full bg-indigo-900/40 px-2 py-0.5 font-mono text-indigo-200">
                        {p.escalation_model}
                      </span>
                    </>
                  )}
                  {p.daily_cost_ceiling_usd !== null && (
                    <span className="rounded-full bg-zinc-700/30 px-2 py-0.5 text-zinc-500">
                      cap ${p.daily_cost_ceiling_usd.toFixed(2)}/day
                    </span>
                  )}
                  {p.requires_tools && (
                    <span className="rounded-full bg-emerald-900/30 px-2 py-0.5 text-emerald-300">
                      tools
                    </span>
                  )}
                </div>
                {p.owner_channel && (
                  <p className="mt-1 text-[11px] text-zinc-500">#{p.owner_channel}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="mb-3 text-sm font-medium text-zinc-200">Workflow Health + Stats</p>
        <div className="grid gap-3 md:grid-cols-2">
          {workflowStats.map(({ workflow, latest, successCount, failureCount, healthLabel, healthTone }) => {
            const meta = workflowMeta[workflow.name];
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
                </div>
                <p className="mt-1.5 text-zinc-400">
                  {workflow.active ? "active" : "inactive"} · last run {relativeTime(latest?.timestamp)}
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
              href={{
                pathname: "/admin/workflows",
                query: { tab: "roster", workflow: workflowId, sort: sort === "desc" ? "asc" : "desc" },
              }}
              className="rounded-md border border-zinc-700 px-2 py-1 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
            >
              sort: {sort === "desc" ? "newest first" : "oldest first"}
            </Link>
          </div>
        </div>
        <div className="mb-3 flex flex-wrap gap-2 text-xs">
          <Link
            href={{
              pathname: "/admin/workflows",
              query: { tab: "roster", workflow: "all", sort },
            }}
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
              href={{
                pathname: "/admin/workflows",
                query: { tab: "roster", workflow: workflow.id, sort },
              }}
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
        <div className="-mx-1 overflow-x-auto scroll-smooth pb-1 [scrollbar-gutter:stable] md:mx-0">
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
              {sorted.slice(0, 25).map((execution) => (
                <tr key={execution.id}>
                  <td className="py-2 pr-3 text-zinc-300">{relativeTime(execution.timestamp)}</td>
                  <td className="py-2 pr-3 text-zinc-200">
                    {workflowNameById.get(String(execution.workflowId ?? "")) ??
                      execution.workflowData?.name ??
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
