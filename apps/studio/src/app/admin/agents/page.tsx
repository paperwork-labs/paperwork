import { getN8nExecutions, getN8nWorkflows } from "@/lib/command-center";

export default async function AgentsPage() {
  const [workflows, executions] = await Promise.all([getN8nWorkflows(), getN8nExecutions(40)]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Agent Activity</h1>
      <p className="text-zinc-400">Workflow-level status, recent executions, and persona activity.</p>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="mb-3 text-sm font-medium text-zinc-200">Workflow Grid</p>
        <div className="grid gap-2 md:grid-cols-2">
          {workflows.map((workflow) => {
            const runs = executions.filter((e) => e.workflowId === workflow.id).length;
            return (
              <div key={workflow.id} className="rounded-md bg-zinc-800/60 px-3 py-2 text-sm">
                <span className="font-medium text-zinc-100">{workflow.name}</span>
                <span className="ml-2 text-zinc-400">{workflow.active ? "active" : "inactive"}</span>
                <span className="ml-2 text-zinc-500">{runs} recent runs</span>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="mb-3 text-sm font-medium text-zinc-200">Recent Execution Feed</p>
        <div className="space-y-2">
          {executions.slice(0, 12).map((execution) => (
            <div key={execution.id} className="rounded-md bg-zinc-800/60 px-3 py-2 text-sm">
              #{execution.id} - {execution.workflowId ?? "unknown"} -{" "}
              {execution.finished ? "finished" : "running"}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

