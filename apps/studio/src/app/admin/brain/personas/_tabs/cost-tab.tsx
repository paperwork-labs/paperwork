"use client";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";

import { usePersonasPagePayload } from "../personas-tabs-client";

function SourceBanner(props: { ok: boolean; path: string; message?: string }) {
  if (props.ok) return null;
  return (
    <div
      className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
      role="alert"
    >
      <p className="font-medium">Data unavailable</p>
      <p className="mt-1 text-amber-100/90">
        {props.message ?? "Could not read file."}{" "}
        <code className="rounded bg-zinc-900/80 px-1">{props.path}</code>
      </p>
    </div>
  );
}

export default function CostTab() {
  const { cost } = usePersonasPagePayload();

  return (
    <div className="space-y-4">
      <HqEmptyState
        title="Per-persona daily cost rollup"
        description="Spend roll-up as estimated dollars per persona per day ships in PR-10 (WS-76). Detailed dispatch counts and registry hints remain in the table below."
      />

      <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
        Detailed dispatch & registry estimates
      </p>

      <SourceBanner
        ok={cost.dispatchSource.ok}
        path={cost.dispatchSource.path}
        message={"message" in cost.dispatchSource ? cost.dispatchSource.message : undefined}
      />
      <SourceBanner
        ok={cost.outcomesSource.ok}
        path={cost.outcomesSource.path}
        message={"message" in cost.outcomesSource ? cost.outcomesSource.message : undefined}
      />

      {cost.attributionNote ? (
        <div className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          {cost.attributionNote}
        </div>
      ) : null}

      {cost.avgTokensNote ? (
        <div className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          {cost.avgTokensNote}
        </div>
      ) : null}

      {cost.dispatchSource.ok &&
      cost.globalDispatch7d !== null &&
      cost.globalDispatch30d !== null ? (
        <p className="text-sm text-muted-foreground">
          All personas (dispatch log aggregate, last 7d / 30d):{" "}
          <strong className="text-foreground">{cost.globalDispatch7d}</strong> /{" "}
          <strong className="text-foreground">{cost.globalDispatch30d}</strong>
        </p>
      ) : null}

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[880px] border-collapse text-left text-sm">
          <thead className="border-b border-border bg-muted/40">
            <tr>
              <th className="px-3 py-2 font-medium">Persona</th>
              <th className="px-3 py-2 font-medium">Dispatches 7d</th>
              <th className="px-3 py-2 font-medium">Dispatches 30d</th>
              <th className="px-3 py-2 font-medium">Avg tokens / dispatch</th>
              <th className="px-3 py-2 font-medium">Est. cost notes</th>
            </tr>
          </thead>
          <tbody>
            {cost.rows.map((row) => (
              <tr key={row.personaId} className="border-b border-border/80 odd:bg-muted/20">
                <td className="px-3 py-2 font-mono text-xs">{row.personaId}</td>
                <td className="px-3 py-2">
                  {row.dispatch7d === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    row.dispatch7d
                  )}
                </td>
                <td className="px-3 py-2">
                  {row.dispatch30d === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    row.dispatch30d
                  )}
                </td>
                <td className="px-3 py-2">
                  {row.avgTokensPerDispatch === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    row.avgTokensPerDispatch.toFixed(1)
                  )}
                </td>
                <td className="max-w-md px-3 py-2 text-muted-foreground">{row.costNote}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
