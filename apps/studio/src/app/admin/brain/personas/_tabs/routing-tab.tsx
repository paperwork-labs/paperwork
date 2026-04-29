"use client";

import { usePersonasPagePayload } from "../personas-tabs-client";

export default function RoutingTab() {
  const { routing } = usePersonasPagePayload();

  return (
    <div className="space-y-4">
      {!routing.source.ok ? (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100" role="alert">
          <p className="font-medium">Could not load EA routing table</p>
          <p className="mt-1">
            {"message" in routing.source ? routing.source.message : "Read failed"}{" "}
            <code className="rounded bg-zinc-900/80 px-1">{routing.source.path}</code>
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Parsed from{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">.cursor/rules/ea.mdc</code> — Tag
          Directory + Smart Persona Routing (read-only v1).
        </p>
      )}

      {routing.source.ok && routing.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No tag rows parsed — check ea.mdc Tag Directory table formatting.
        </p>
      ) : null}

      {routing.rows.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[480px] border-collapse text-left text-sm">
            <thead className="border-b border-border bg-muted/40">
              <tr>
                <th className="px-3 py-2 font-medium">Tag</th>
                <th className="px-3 py-2 font-medium">Routing target persona</th>
              </tr>
            </thead>
            <tbody>
              {routing.rows.map((row) => (
                <tr key={row.tag} className="border-b border-border/80 odd:bg-muted/20">
                  <td className="px-3 py-2 font-mono text-xs">{row.tag}</td>
                  <td className="px-3 py-2">{row.routingTarget}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
