"use client";

import { StatusBadge } from "@paperwork-labs/ui";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";

import { usePersonasPagePayload } from "../personas-tabs-client";

export default function OpenRolesTab() {
  const { openRoles } = usePersonasPagePayload();

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Persona specs from{" "}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">.cursor/rules/*.mdc</code> missing a
        documented model assignment block — treat as unfilled &quot;open roles&quot; until the spec is
        completed.
      </p>

      {openRoles.length === 0 ? (
        <HqEmptyState
          title="No open roles"
          description="Every loaded persona rule file includes a Model Assignment section, or the roster is empty."
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[720px] border-collapse text-left text-sm">
            <thead className="border-b border-border bg-muted/40">
              <tr>
                <th className="px-3 py-2 font-medium">Persona id</th>
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">File</th>
                <th className="px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {openRoles.map((row) => (
                <tr key={row.personaId} className="border-b border-border/80 odd:bg-muted/20">
                  <td className="px-3 py-2 font-mono text-xs text-foreground">{row.personaId}</td>
                  <td className="px-3 py-2 text-foreground">{row.name}</td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    {row.relativePath}
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge tone="strategy-draft">Missing model assignment</StatusBadge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

