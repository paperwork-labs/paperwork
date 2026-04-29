import type { SelfImprovementPayload } from "@/lib/self-improvement";

export function AutomationStateTab(props: { payload: SelfImprovementPayload }) {
  const { schedulers } = props.payload;

  return (
    <div className="space-y-6 text-zinc-200">
      <p className="text-xs text-zinc-500">
        Schedules parsed statically from <code className="text-zinc-400">apis/brain/app/schedulers/</code>{" "}
        (best-effort). Run telemetry requires{" "}
        <code className="text-zinc-400">scheduler_state.json</code> —{" "}
        {schedulers.meta.missing ? (
          <span className="text-amber-400/90">not present; last/next run shown as —.</span>
        ) : (
          <span>found at {schedulers.meta.path}</span>
        )}
      </p>

      <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-800/80 text-xs uppercase tracking-wider text-zinc-500">
              <th className="p-3 font-medium">Job ID</th>
              <th className="p-3 font-medium">Module</th>
              <th className="p-3 font-medium">Schedule</th>
              <th className="p-3 font-medium">Last run</th>
              <th className="p-3 font-medium">Last status</th>
              <th className="p-3 font-medium">Next run</th>
            </tr>
          </thead>
          <tbody>
            {schedulers.rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-4 text-zinc-500">
                  No scheduler modules parsed — verify repo checkout includes Brain sources.
                </td>
              </tr>
            ) : (
              schedulers.rows.map((r) => (
                <tr key={`${r.jobId}-${r.moduleFile}`} className="border-b border-zinc-800/40 align-top">
                  <td className="p-3 font-mono text-xs text-zinc-300">{r.jobId}</td>
                  <td className="p-3 font-mono text-xs text-zinc-500">{r.moduleFile}</td>
                  <td className="p-3 text-xs text-zinc-400">{r.schedule}</td>
                  <td className="p-3 text-xs text-zinc-500">{r.lastRun ?? "—"}</td>
                  <td className="p-3 text-xs text-zinc-500">{r.lastStatus ?? "—"}</td>
                  <td className="p-3 text-xs text-zinc-500">{r.nextRun ?? "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-zinc-600">
        APScheduler registers jobs conditionally in Python — some rows may only apply when feature flags or
        vault ownership match runtime Brain configuration.
      </p>
    </div>
  );
}
