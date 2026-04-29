"use client";

import { StatusBadge } from "@paperwork-labs/ui";

import { usePersonasPagePayload } from "../personas-tabs-client";

export default function RegistryTab() {
  const { registry } = usePersonasPagePayload();

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Rules read from{" "}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">.cursor/rules/*.mdc</code> at build
        time (server filesystem).
      </p>
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <thead className="border-b border-border bg-muted/40">
            <tr>
              <th className="px-3 py-2 font-medium">Persona id</th>
              <th className="px-3 py-2 font-medium">Name</th>
              <th className="px-3 py-2 font-medium">Description</th>
              <th className="px-3 py-2 font-medium">File</th>
              <th className="px-3 py-2 font-medium">Model assignment</th>
              <th className="px-3 py-2 font-medium">Routing</th>
            </tr>
          </thead>
          <tbody>
            {registry.map((row) => (
              <tr key={row.personaId} className="border-b border-border/80 odd:bg-muted/20">
                <td className="px-3 py-2 font-mono text-xs text-foreground">{row.personaId}</td>
                <td className="px-3 py-2 text-foreground">{row.name}</td>
                <td className="max-w-[280px] px-3 py-2 text-muted-foreground">
                  {row.description ?? "—"}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{row.relativePath}</td>
                <td className="max-w-[240px] px-3 py-2 text-muted-foreground">
                  {row.modelAssignment ? (
                    <span className="line-clamp-4 whitespace-pre-wrap">{row.modelAssignment}</span>
                  ) : (
                    <span className="text-muted-foreground">— (no ## Model Assignment section)</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <StatusBadge tone={row.routingActive ? "strategy-active" : "strategy-paused"}>
                    {row.routingActive ? "active" : "inactive"}
                  </StatusBadge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
