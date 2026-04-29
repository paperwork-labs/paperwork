"use client";

import { useMemo, useState } from "react";

import { Input } from "@paperwork-labs/ui";

import type { SelfImprovementPayload } from "@/lib/self-improvement";

export function OutcomesTab(props: { payload: SelfImprovementPayload }) {
  const { outcomes } = props.payload;
  const [modelQ, setModelQ] = useState("");
  const [personaQ, setPersonaQ] = useState("");
  const [wsQ, setWsQ] = useState("");

  const filtered = useMemo(() => {
    const mq = modelQ.trim().toLowerCase();
    const pq = personaQ.trim().toLowerCase();
    const wq = wsQ.trim().toLowerCase();
    return outcomes.rows.filter((r) => {
      if (mq && !r.agent_model.toLowerCase().includes(mq)) return false;
      if (pq && !r.merged_by_agent.toLowerCase().includes(pq)) return false;
      if (
        wq &&
        !r.workstream_ids.some((w) => w.toLowerCase().includes(wq)) &&
        !r.workstream_types.some((w) => w.toLowerCase().includes(wq))
      ) {
        return false;
      }
      return true;
    });
  }, [outcomes.rows, modelQ, personaQ, wsQ]);

  function horizonCell(
    h: { ci_pass: boolean; deploy_success: boolean; reverted: boolean } | null | undefined,
  ): string {
    if (!h) return "—";
    const bits = [
      h.ci_pass ? "ci" : "ci✗",
      h.deploy_success ? "deploy" : "deploy✗",
      h.reverted ? "revert" : "ok",
    ];
    return bits.join(" · ");
  }

  return (
    <div className="space-y-6 text-zinc-200">
      <p className="text-xs text-zinc-500">
        {outcomes.meta.asOfIso ? `As of ${outcomes.meta.asOfIso}` : "As-of unavailable"} · Last 50 merges by{" "}
        <code className="text-zinc-400">merged_at</code>
      </p>

      {outcomes.meta.missing ? (
        <p className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4 text-sm text-zinc-400">
          No PR outcomes recorded yet — first merged outcome populates{" "}
          <code className="text-zinc-300">apis/brain/data/pr_outcomes.json</code>.
        </p>
      ) : (
        <>
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <label className="flex flex-1 flex-col gap-1 text-xs text-zinc-500">
              Filter · agent model
              <Input
                value={modelQ}
                onChange={(e) => setModelQ(e.target.value)}
                placeholder="e.g. composer-1.5"
                className="border-zinc-700 bg-zinc-950 text-zinc-100"
              />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-xs text-zinc-500">
              Filter · merged_by_agent
              <Input
                value={personaQ}
                onChange={(e) => setPersonaQ(e.target.value)}
                placeholder="persona label"
                className="border-zinc-700 bg-zinc-950 text-zinc-100"
              />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-xs text-zinc-500">
              Filter · workstream
              <Input
                value={wsQ}
                onChange={(e) => setWsQ(e.target.value)}
                placeholder="workstream id substring"
                className="border-zinc-700 bg-zinc-950 text-zinc-100"
              />
            </label>
          </div>

          <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-800/80 text-xs uppercase tracking-wider text-zinc-500">
                  <th className="p-3 font-medium">PR</th>
                  <th className="p-3 font-medium">Merged</th>
                  <th className="p-3 font-medium">Agent</th>
                  <th className="p-3 font-medium">Model</th>
                  <th className="p-3 font-medium">Workstreams</th>
                  <th className="p-3 font-medium">h1</th>
                  <th className="p-3 font-medium">h24</th>
                  <th className="p-3 font-medium">d7</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-4 text-zinc-500">
                      No rows match filters.
                    </td>
                  </tr>
                ) : (
                  filtered.map((r) => (
                    <tr key={r.pr_number} className="border-b border-zinc-800/40 align-top">
                      <td className="p-3 font-mono text-xs">{r.pr_number}</td>
                      <td className="p-3 text-xs text-zinc-500">{r.merged_at}</td>
                      <td className="p-3 text-xs">{r.merged_by_agent}</td>
                      <td className="p-3 font-mono text-xs">{r.agent_model}</td>
                      <td className="max-w-[200px] p-3 text-xs text-zinc-400">
                        {(r.workstream_ids ?? []).join(", ") || "—"}
                      </td>
                      <td className="p-3 text-xs text-zinc-400">{horizonCell(r.outcomes?.h1)}</td>
                      <td className="p-3 text-xs text-zinc-400">{horizonCell(r.outcomes?.h24)}</td>
                      <td className="p-3 text-xs text-zinc-400">{r.outcomes?.d7 ? "tracked" : "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      <p className="text-xs text-zinc-600">
        Source: <code className="text-zinc-400">apis/brain/data/pr_outcomes.json</code>
      </p>
    </div>
  );
}
