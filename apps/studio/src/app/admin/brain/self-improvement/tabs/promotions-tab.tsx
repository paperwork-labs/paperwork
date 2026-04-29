"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchSelfImprovementJson } from "../lib/fetch-self-improvement";

type MergeRow = {
  pr_number: number;
  merged_at: string;
  tier: string;
  paths_touched: string[];
  graduation_eligible: boolean;
};

type RevertRow = {
  pr_number: number;
  original_pr: number;
  reverted_at: string;
  reason: string;
};

type PromotionsPayload = {
  current_tier: string;
  clean_merge_count: number;
  eligible_for_promotion: boolean;
  progress_to_next_tier_pct: number;
  merges_required_for_next_tier: number;
  recent_merges_last_10: MergeRow[];
  recent_reverts_last_5: RevertRow[];
  graduation_rules_doc_slug: string;
};

export function PromotionsTab() {
  const [data, setData] = useState<PromotionsPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetchSelfImprovementJson<PromotionsPayload>("promotions");
      if (cancelled) return;
      if (res.success && res.data) setData(res.data);
      else setErr(res.error ?? "Failed to load promotions");
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (err) {
    return (
      <p className="text-sm text-rose-200" role="alert" data-testid="promotions-error">
        {err}
      </p>
    );
  }
  if (!data) return <p className="text-sm text-zinc-500">Loading…</p>;

  const pct = Number.isFinite(data.progress_to_next_tier_pct) ? data.progress_to_next_tier_pct : 0;

  return (
    <div className="space-y-6" data-testid="promotions-tab">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-zinc-500">Current tier</p>
          <p className="mt-1 inline-block rounded-md border border-emerald-900/50 bg-emerald-950/40 px-3 py-1 font-mono text-sm text-emerald-200">
            {data.current_tier}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-zinc-500">Progress to next tier</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-zinc-100" data-testid="tier-progress-pct">
            {pct.toFixed(1)}%
          </p>
          <p className="text-xs text-zinc-500">
            {data.clean_merge_count} / {data.merges_required_for_next_tier} clean merges
            {data.eligible_for_promotion ? " · eligible for promotion" : ""}
          </p>
        </div>
        <Link
          href={`/admin/docs/${data.graduation_rules_doc_slug}`}
          className="text-sm text-sky-400 underline decoration-sky-400/40 underline-offset-2"
        >
          Graduation rules (runbook)
        </Link>
      </div>

      <section>
        <h2 className="text-sm font-semibold text-zinc-200">Last 10 merges</h2>
        {data.recent_merges_last_10.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500" data-testid="merges-empty">
            No recorded self-merge promotions yet.
          </p>
        ) : (
          <ul className="mt-2 divide-y divide-zinc-800 rounded-lg border border-zinc-800">
            {data.recent_merges_last_10.map((m) => (
              <li key={m.pr_number} className="flex flex-wrap gap-2 px-3 py-2 text-sm">
                <span className="font-mono text-zinc-200">#{m.pr_number}</span>
                <span className="text-zinc-500">{m.merged_at}</span>
                <span className="text-zinc-400">{m.tier}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="text-sm font-semibold text-zinc-200">Recent reverts (up to 5)</h2>
        {data.recent_reverts_last_5.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500" data-testid="reverts-empty">
            No reverts recorded.
          </p>
        ) : (
          <ul className="mt-2 divide-y divide-zinc-800 rounded-lg border border-zinc-800">
            {data.recent_reverts_last_5.map((r) => (
              <li key={r.pr_number} className="px-3 py-2 text-sm">
                <span className="font-mono text-zinc-200">Revert #{r.pr_number}</span>{" "}
                <span className="text-zinc-500">original #{r.original_pr}</span>
                <p className="text-xs text-zinc-500">{r.reason}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
