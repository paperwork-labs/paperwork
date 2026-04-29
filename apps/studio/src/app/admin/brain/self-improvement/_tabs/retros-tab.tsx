import type { SelfImprovementPayload } from "@/lib/self-improvement";

export function RetrosTab(props: { payload: SelfImprovementPayload }) {
  const { retros } = props.payload;

  return (
    <div className="space-y-6 text-zinc-200">
      <p className="text-xs text-zinc-500">
        {retros.meta.asOfIso ? `As of ${retros.meta.asOfIso}` : "As-of unavailable"} · Last 12 weekly entries
      </p>

      {retros.meta.missing ? (
        <p className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4 text-sm text-zinc-400">
          No retros yet — Brain writes <code className="text-zinc-300">weekly_retros.json</code> from the
          self-improvement scheduler.
        </p>
      ) : retros.rows.length === 0 ? (
        <p className="text-sm text-zinc-500">Retros array is empty.</p>
      ) : (
        <ul className="space-y-4">
          {retros.rows.map((r) => (
            <li
              key={`${r.week_ending}-${r.computed_at}`}
              className="rounded-xl border border-zinc-800/80 bg-zinc-950/30 p-4"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-medium text-zinc-100">Week ending {r.week_ending}</p>
                <p className="text-xs text-zinc-500">Computed {r.computed_at}</p>
              </div>
              <p className="mt-2 text-sm text-zinc-400">{r.summaryText}</p>
              {r.highlights.length > 0 && (
                <ul className="mt-3 list-inside list-disc text-sm text-zinc-400">
                  {r.highlights.map((h) => (
                    <li key={h}>{h}</li>
                  ))}
                </ul>
              )}
              {r.ruleChanges.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs uppercase tracking-widest text-zinc-500">Rule changes proposed</p>
                  <ul className="mt-1 space-y-1 text-sm">
                    {r.ruleChanges.map((c) => (
                      <li key={`${c.rule_id}-${c.action}`} className="text-zinc-400">
                        <span className="font-mono text-xs text-zinc-300">{c.rule_id}</span> · {c.action} —{" "}
                        {c.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <p className="text-xs text-zinc-600">
        Source: <code className="text-zinc-400">apis/brain/data/weekly_retros.json</code>
      </p>
    </div>
  );
}
