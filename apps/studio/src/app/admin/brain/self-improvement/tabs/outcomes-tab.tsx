"use client";

import { useEffect, useState } from "react";

import { fetchSelfImprovementJson } from "../lib/fetch-self-improvement";

const BUCKET_ORDER = [
  "reverted",
  "7d_still_passing",
  "24h_still_passing",
  "1h_pass",
  "pending_observation",
] as const;

type BucketKey = (typeof BUCKET_ORDER)[number];

type OutcomesPayload = {
  count: number;
  buckets: Record<BucketKey, Record<string, unknown>[]>;
};

const BUCKET_LABEL: Record<BucketKey, string> = {
  reverted: "Reverted",
  "7d_still_passing": "7d still passing",
  "24h_still_passing": "24h still passing",
  "1h_pass": "1h pass",
  pending_observation: "Pending / incomplete observation",
};

export function OutcomesTab() {
  const [data, setData] = useState<OutcomesPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetchSelfImprovementJson<OutcomesPayload>("outcomes?limit=200");
      if (cancelled) return;
      if (res.success && res.data) setData(res.data);
      else setErr(res.error ?? "Failed to load outcomes");
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (err) {
    return (
      <p className="text-sm text-rose-200" role="alert">
        {err}
      </p>
    );
  }
  if (!data) return <p className="text-sm text-zinc-500">Loading…</p>;

  if (data.count === 0) {
    return (
      <p className="text-sm text-zinc-500" data-testid="outcomes-empty">
        No PR outcomes recorded yet. Brain appends merges to{" "}
        <code className="text-zinc-400">apis/brain/data/pr_outcomes.json</code> when the orchestrator runs.
      </p>
    );
  }

  return (
    <div className="space-y-8" data-testid="outcomes-tab">
      <p className="text-xs text-zinc-500">
        {data.count} outcome row(s), grouped by coarse health. Sorted by recency within each bucket on the server.
      </p>
      {BUCKET_ORDER.map((key) => {
        const rows = data.buckets[key] ?? [];
        if (rows.length === 0) return null;
        return (
          <section key={key}>
            <h2 className="text-sm font-semibold text-zinc-200">
              {BUCKET_LABEL[key]} <span className="text-zinc-500">({rows.length})</span>
            </h2>
            <ul className="mt-2 divide-y divide-zinc-800 rounded-lg border border-zinc-800">
              {rows.map((row) => {
                const pr = row.pr_number as number;
                const mergedAt = String(row.merged_at ?? "");
                return (
                  <li key={`${key}-${pr}-${mergedAt}`} className="px-3 py-2 text-sm">
                    <span className="font-mono text-zinc-200">#{pr}</span>{" "}
                    <span className="text-zinc-500">{mergedAt}</span>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
