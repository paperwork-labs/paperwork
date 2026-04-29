import { AlertCircle } from "lucide-react";

import type { SelfImprovementPayload } from "@/lib/self-improvement";

function asOfLine(meta: {
  asOfIso: string | null;
  missing: boolean;
  rawUpdatedAt?: string;
}) {
  const raw = "rawUpdatedAt" in meta && meta.rawUpdatedAt ? meta.rawUpdatedAt : null;
  const ts = raw ?? meta.asOfIso;
  return ts ? `As of ${ts} (point-in-time)` : "As-of timestamp unavailable";
}

export function LearningTab(props: {
  payload: SelfImprovementPayload;
  brainConfigured: boolean;
}) {
  const { payload, brainConfigured } = props;
  const { learning, repoRoot } = payload;
  const dispatch = learning.dispatchMeta;

  const vol7 = Object.values(learning.volumeByModel7d).reduce((a, b) => a + b, 0);
  const vol30 = Object.values(learning.volumeByModel30d).reduce((a, b) => a + b, 0);

  const sourceHint = repoRoot ? (
    <span className="text-zinc-500">
      Source: <code className="text-zinc-400">apis/brain/data/agent_dispatch_log.json</code>
    </span>
  ) : (
    <span className="text-amber-400/90">
      Monorepo root not resolved — mount Studio from the Paperwork repo so dispatch JSON can be read.
    </span>
  );

  return (
    <div className="space-y-6 text-zinc-200">
      <p className="text-xs text-zinc-500">{asOfLine(dispatch)}</p>
      {!brainConfigured && (
        <div className="flex gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100/90">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p>
            Live Brain learning API is optional here — tab reads committed JSON. To compare with live
            observability, set <code className="rounded bg-zinc-800 px-1">BRAIN_API_URL</code> and{" "}
            <code className="rounded bg-zinc-800 px-1">BRAIN_API_SECRET</code> and visit{" "}
            <a className="text-indigo-400 underline" href="/admin/brain/learning">
              /admin/brain/learning
            </a>
            .
          </p>
        </div>
      )}

      {dispatch.missing && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4 text-sm text-zinc-400">
          No dispatch log on disk yet — first dispatch writes{" "}
          <code className="text-zinc-300">agent_dispatch_log.json</code>.
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Dispatches (7d)", String(vol7)],
          ["Dispatches (30d)", String(vol30)],
          ["Success rate (7d)", learning.successRate7d != null ? `${learning.successRate7d}%` : "—"],
          ["Success rate (30d)", learning.successRate30d != null ? `${learning.successRate30d}%` : "—"],
        ].map(([k, v]) => (
          <div key={k} className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
            <p className="text-xs uppercase tracking-widest text-zinc-500">{k}</p>
            <p className="mt-2 text-2xl font-semibold text-zinc-50">{v}</p>
          </div>
        ))}
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">
          Volume by model (30d)
        </h2>
        <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
          <table className="w-full min-w-[320px] text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-800/80 text-xs uppercase tracking-wider text-zinc-500">
                <th className="p-3 font-medium">Model</th>
                <th className="p-3 font-medium">Dispatches</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(learning.volumeByModel30d).length === 0 ? (
                <tr>
                  <td colSpan={2} className="p-4 text-zinc-500">
                    No dispatch rows in the last 30 days.
                  </td>
                </tr>
              ) : (
                Object.entries(learning.volumeByModel30d)
                  .sort((a, b) => b[1] - a[1])
                  .map(([model, n]) => (
                    <tr key={model} className="border-b border-zinc-800/40 text-zinc-300">
                      <td className="p-3 font-mono text-xs">{model}</td>
                      <td className="p-3 tabular-nums">{n}</td>
                    </tr>
                  ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">
          Top 3 procedural patterns (last 30d)
        </h2>
        <p className="text-xs text-zinc-500">{asOfLine(learning.proceduralMeta)}</p>
        {learning.topPatterns30d.length === 0 ? (
          <p className="text-sm text-zinc-500">
            No rules with <code className="text-zinc-400">learned_at</code> in the rolling 30-day window,
            or procedural memory file missing.
          </p>
        ) : (
          <ul className="space-y-2">
            {learning.topPatterns30d.map((p) => (
              <li
                key={p.id}
                className="rounded-lg border border-zinc-800/80 bg-zinc-950/30 px-3 py-2 text-sm text-zinc-300"
              >
                <span className="mr-2 font-mono text-[10px] text-zinc-500">{p.id}</span>
                <span className="text-zinc-500">{p.learned_at}</span>
                <p className="mt-1 text-zinc-400">{p.summary}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-xs text-zinc-600">{sourceHint}</p>
    </div>
  );
}
