"use client";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";

import { usePersonasPagePayload } from "../personas-tabs-client";

export default function ActivityTab() {
  const { activity } = usePersonasPagePayload();

  return (
    <div className="space-y-4">
      {!activity.source.ok ? (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100" role="alert">
          <p className="font-medium">Dispatch log unavailable</p>
          <p className="mt-1">
            {"message" in activity.source ? activity.source.message : "Read failed"}{" "}
            <code className="rounded bg-zinc-900/80 px-1">{activity.source.path}</code>
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Recent persona-backed dispatches (newest first) from{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">
            apis/brain/data/agent_dispatch_log.json
          </code>
          .
        </p>
      )}

      {activity.note && activity.rows.length > 0 ? (
        <div className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          {activity.note}
        </div>
      ) : null}

      {activity.source.ok && activity.rows.length === 0 ? (
        <HqEmptyState
          title="No dispatch activity yet"
          description={
            activity.note ??
            "Cheap-agent dispatches will appear here once agent_dispatch_log.json records events."
          }
        />
      ) : null}

      {activity.rows.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[880px] border-collapse text-left text-sm">
            <thead className="border-b border-border bg-muted/40">
              <tr>
                <th className="px-3 py-2 font-medium">Timestamp</th>
                <th className="px-3 py-2 font-medium">Persona / model</th>
                <th className="px-3 py-2 font-medium">Workstream tag</th>
                <th className="px-3 py-2 font-medium">Outcome</th>
                <th className="px-3 py-2 font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {activity.rows.map((row, i) => (
                <tr key={`${row.dispatchedAt}-${i}`} className="border-b border-border/80 odd:bg-muted/20">
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-muted-foreground">
                    {row.dispatchedAt}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{row.persona}</td>
                  <td className="px-3 py-2 font-mono text-xs">{row.workstreamTag}</td>
                  <td className="px-3 py-2">{row.successLabel}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.costLabel}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

