import { getN8nExecutions } from "@/lib/command-center";

const KICKOFF_ID = "f7a8b9c0-d1e2-4f3a-b4c5-d6e7f8a9b0c1";
const CLOSE_ID = "a9b0c1d2-e3f4-4a5b-b6c7-d8e9f0a1b2c3";

export default async function SprintsPage() {
  const executions = await getN8nExecutions(50);

  const kickoffRuns = executions.filter((e) => e.workflowId === KICKOFF_ID);
  const closeRuns = executions.filter((e) => e.workflowId === CLOSE_ID);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Sprint Tracker</h1>
      <p className="text-zinc-400">3-day sprint cadence in Slack (#sprints).</p>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Current cadence</p>
          <p className="mt-2 text-xl font-semibold">Mon-Thu + Thu-Sat</p>
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
          {executions
            .filter((e) => e.workflowId === KICKOFF_ID || e.workflowId === CLOSE_ID)
            .slice(0, 10)
            .map((e) => (
              <div key={e.id} className="rounded-md bg-zinc-800/60 px-3 py-2 text-sm">
                #{e.id} - {e.workflowId === KICKOFF_ID ? "Kickoff" : "Close"} -{" "}
                {e.finished ? "finished" : "running"}
              </div>
            ))}
        </div>
      </section>
    </div>
  );
}

