import { getN8nExecutions, getN8nWorkflows } from "@/lib/command-center";

export default async function SprintsPage() {
  const [workflows, executions] = await Promise.all([getN8nWorkflows(), getN8nExecutions(50)]);

  const kickoffWorkflow = workflows.find(
    (w) => w.name.toLowerCase().includes("sprint") && w.name.toLowerCase().includes("kickoff")
  );
  const closeWorkflow = workflows.find(
    (w) => w.name.toLowerCase().includes("sprint") && w.name.toLowerCase().includes("close")
  );
  const kickoffId = kickoffWorkflow?.id;
  const closeId = closeWorkflow?.id;

  const kickoffRuns = kickoffId ? executions.filter((e) => e.workflowId === kickoffId) : [];
  const closeRuns = closeId ? executions.filter((e) => e.workflowId === closeId) : [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Sprint Tracker</h1>
      <p className="text-zinc-400">5-day sprint cadence in Slack (#sprints).</p>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Current cadence</p>
          <p className="mt-2 text-xl font-semibold">Mon-Fri</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Kickoff runs</p>
          <p className="mt-2 text-2xl font-semibold">{kickoffRuns.length}</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Close runs</p>
          <p className="mt-2 text-2xl font-semibold">{closeRuns.length}</p>
        </div>
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="mb-3 text-sm font-medium text-zinc-200">Recent Sprint Executions</p>
        <div className="space-y-2">
          {(kickoffId || closeId
            ? executions.filter(
                (e) =>
                  (kickoffId && e.workflowId === kickoffId) || (closeId && e.workflowId === closeId)
              )
            : []
          )
            .slice(0, 10)
            .map((e) => (
              <div key={e.id} className="rounded-md bg-zinc-800/60 px-3 py-2 text-sm">
                #{e.id} - {e.workflowId === kickoffId ? "Kickoff" : "Close"} -{" "}
                {e.finished ? "finished" : "running"}
              </div>
            ))}
          {!kickoffId && !closeId && (
            <p className="text-sm text-zinc-400">
              No Sprint Kickoff or Sprint Close workflows found. Add them in n8n to track executions.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

