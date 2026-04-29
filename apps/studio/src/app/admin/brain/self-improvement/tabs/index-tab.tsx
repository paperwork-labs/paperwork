"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { OperatingScoreGaugeBody } from "@/components/admin/OperatingScoreGaugeBody";
import type { OperatingScoreResponse } from "@/types/operating-score";

import { fetchSelfImprovementJson } from "../lib/fetch-self-improvement";

type Summary = {
  current_tier: string;
  clean_merge_count: number;
  progress_to_next_tier_pct: number;
  positive_retro_streak_weeks: number;
  spotlight_rule: { id: string; when: string; confidence: string; note: string } | null;
};

function emptyOperating(): OperatingScoreResponse {
  return { current: null, history_last_12: [], gates: { l4_pass: false, l5_pass: false, lowest_pillar: "" } };
}

export function IndexTab() {
  const [os, setOs] = useState<OperatingScoreResponse | null>(null);
  const [osConfigured, setOsConfigured] = useState(true);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [osRes, sumRes] = await Promise.all([
        fetch("/api/admin/operating-score", { cache: "no-store" }),
        fetchSelfImprovementJson<Summary>("summary"),
      ]);
      if (cancelled) return;
      if (osRes.status === 503) {
        setOsConfigured(false);
        setOs(emptyOperating());
      } else if (!osRes.ok) {
        setOsConfigured(true);
        setOs(emptyOperating());
        setLoadErr(`Operating score HTTP ${osRes.status}`);
      } else {
        setOsConfigured(true);
        const j = (await osRes.json()) as { success?: boolean; data?: OperatingScoreResponse };
        setOs(j.data ?? emptyOperating());
      }
      if (sumRes.success && sumRes.data) setSummary(sumRes.data);
      else if (sumRes.error) setLoadErr(sumRes.error);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6" data-testid="self-improvement-index-tab">
      {loadErr ? (
        <p className="text-sm text-amber-200/90" role="status">
          {loadErr}
        </p>
      ) : null}
      {os ? <OperatingScoreGaugeBody data={os} brainConfigured={osConfigured} /> : null}

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
          <p className="text-xs uppercase tracking-wide text-zinc-500">Self-merge tier</p>
          <p className="mt-2 font-mono text-lg text-zinc-100" data-testid="summary-tier">
            {summary ? summary.current_tier : "—"}
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            {summary ? `${summary.clean_merge_count} clean merges toward next tier` : "Loading…"}
          </p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
          <p className="text-xs uppercase tracking-wide text-zinc-500">Positive retro streak</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-zinc-100" data-testid="summary-streak">
            {summary ? `${summary.positive_retro_streak_weeks} wk` : "—"}
          </p>
          <p className="mt-1 text-xs text-zinc-500">Consecutive weekly retros with POS Δ &gt; 0 and merges ≥ reverts.</p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
          <p className="text-xs uppercase tracking-wide text-zinc-500">Procedural spotlight</p>
          {summary?.spotlight_rule ? (
            <>
              <p className="mt-2 font-mono text-sm text-emerald-300/90" data-testid="spotlight-rule-id">
                {summary.spotlight_rule.id}
              </p>
              <p className="mt-1 line-clamp-3 text-xs text-zinc-400">{summary.spotlight_rule.when}</p>
              <p className="mt-1 text-[10px] text-zinc-600">{summary.spotlight_rule.note}</p>
            </>
          ) : (
            <p className="mt-2 text-sm text-zinc-500">No rules loaded yet.</p>
          )}
        </div>
      </div>

      <p className="text-sm text-zinc-500">
        Drill into{" "}
        <Link href="/admin/brain/self-improvement?tab=learning" className="text-sky-400 underline">
          learning
        </Link>
        ,{" "}
        <Link href="/admin/brain/self-improvement?tab=promotions" className="text-sky-400 underline">
          promotions
        </Link>
        , and other tabs for WS-64 loop telemetry.
      </p>
    </div>
  );
}
