"use client";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";

import { usePersonasPagePayload } from "../personas-tabs-client";

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
    return String(v);
  }
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

export default function PromotionsQueueTab() {
  const { promotions } = usePersonasPagePayload();

  return (
    <div className="space-y-4">
      {!promotions.source.ok ? (
        <div
          className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
          role="alert"
        >
          <p className="font-medium">Promotions queue unavailable</p>
          <p className="mt-1">
            {"message" in promotions.source ? promotions.source.message : "Read failed"}{" "}
            <code className="rounded bg-zinc-900/80 px-1">{promotions.source.path}</code>
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Rows from{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">
            apis/brain/data/self_merge_promotions.json
          </code>
          . Personas that earn self-merge graduation appear here as Brain records promotion events.
        </p>
      )}

      {promotions.source.ok && promotions.promotions.length === 0 ? (
        <HqEmptyState
          title="No personas in the promotions queue"
          description="The promotions array is empty — no self-merge graduations are queued yet. Track record data will surface here as Brain automation fills self_merge_promotions.json."
        />
      ) : null}

      {promotions.promotions.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[640px] border-collapse text-left text-sm">
            <thead className="border-b border-border bg-muted/40">
              <tr>
                <th className="px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Payload (preview)</th>
              </tr>
            </thead>
            <tbody>
              {promotions.promotions.map((row, i) => (
                <tr key={i} className="border-b border-border/80 odd:bg-muted/20">
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-muted-foreground">
                    {i + 1}
                  </td>
                  <td className="max-w-[720px] break-all px-3 py-2 font-mono text-xs">
                    {formatCell(row)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

