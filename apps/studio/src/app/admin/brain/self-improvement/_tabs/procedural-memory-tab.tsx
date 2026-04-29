"use client";

import { useMemo, useState } from "react";

import { Input } from "@paperwork-labs/ui";

import type { SelfImprovementPayload } from "@/lib/self-improvement";

export function ProceduralMemoryTab(props: { payload: SelfImprovementPayload }) {
  const { procedural } = props.payload;
  const [q, setQ] = useState("");

  const rows = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return procedural.rows;
    return procedural.rows.filter(
      (r) =>
        r.id.toLowerCase().includes(s) ||
        r.when.toLowerCase().includes(s) ||
        r.do.toLowerCase().includes(s) ||
        r.source.toLowerCase().includes(s),
    );
  }, [procedural.rows, q]);

  return (
    <div className="space-y-6 text-zinc-200">
      <p className="text-xs text-zinc-500">
        {procedural.meta.asOfIso ? `As of ${procedural.meta.asOfIso}` : "As-of unavailable"} · Read-only
      </p>

      {procedural.meta.missing ? (
        <p className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4 text-sm text-zinc-400">
          <code className="text-zinc-300">procedural_memory.yaml</code> not found.
        </p>
      ) : (
        <>
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search rules…"
            className="max-w-md border-zinc-700 bg-zinc-950 text-zinc-100"
          />
          <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-800/80 text-xs uppercase tracking-wider text-zinc-500">
                  <th className="p-3 font-medium">Rule</th>
                  <th className="p-3 font-medium">When</th>
                  <th className="p-3 font-medium">Do</th>
                  <th className="p-3 font-medium">learned_at</th>
                  <th className="p-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-4 text-zinc-500">
                      No matching rules.
                    </td>
                  </tr>
                ) : (
                  rows.map((r) => (
                    <tr key={r.id} className="border-b border-zinc-800/40 align-top">
                      <td className="p-3 font-mono text-xs text-zinc-300">{r.id}</td>
                      <td className="max-w-[280px] p-3 text-xs text-zinc-400">{r.when}</td>
                      <td className="max-w-[320px] p-3 text-xs text-zinc-400">{r.do}</td>
                      <td className="p-3 text-xs text-zinc-500">{r.learned_at || "—"}</td>
                      <td className="p-3 text-xs text-zinc-400">{r.status}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      <p className="text-xs text-zinc-600">
        Source: <code className="text-zinc-400">apis/brain/data/procedural_memory.yaml</code>
      </p>
    </div>
  );
}
