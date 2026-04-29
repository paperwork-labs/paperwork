"use client";

import { useEffect, useState } from "react";

import { fetchSelfImprovementJson } from "../lib/fetch-self-improvement";

type RetroSummary = {
  pos_total_change: number;
  merges: number;
  reverts: number;
  incidents: number;
  candidates_proposed: number;
  candidates_promoted: number;
};

type Retro = {
  week_ending: string;
  computed_at: string;
  summary: RetroSummary;
  highlights: string[];
  notes: string;
};

type RetrosPayload = {
  count: number;
  retros: Retro[];
};

export function RetrosTab() {
  const [data, setData] = useState<RetrosPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetchSelfImprovementJson<RetrosPayload>("retros?limit=12");
      if (cancelled) return;
      if (res.success && res.data) setData(res.data);
      else setErr(res.error ?? "Failed to load retros");
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
      <p className="text-sm text-zinc-500" data-testid="retros-empty">
        No weekly retros yet. The Monday cron writes{" "}
        <code className="text-zinc-400">apis/brain/data/weekly_retros.json</code>.
      </p>
    );
  }

  return (
    <ol className="space-y-4" data-testid="retros-tab">
      {data.retros.map((r) => (
        <li
          key={r.week_ending}
          className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4"
          data-testid="retro-card"
        >
          <p className="text-xs uppercase tracking-wide text-zinc-500">Week ending</p>
          <p className="font-mono text-sm text-zinc-200">{r.week_ending}</p>
          <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-3 lg:grid-cols-6">
            <RetroStat label="POS Δ" value={r.summary.pos_total_change.toFixed(2)} />
            <RetroStat label="Merges" value={String(r.summary.merges)} />
            <RetroStat label="Reverts" value={String(r.summary.reverts)} />
            <RetroStat label="Incidents" value={String(r.summary.incidents)} />
            <RetroStat label="Candidates Δ" value={`+${r.summary.candidates_proposed}`} />
            <RetroStat label="Promoted" value={String(r.summary.candidates_promoted)} />
          </dl>
          {r.highlights.length ? (
            <ul className="mt-3 list-inside list-disc text-xs text-zinc-400">
              {r.highlights.slice(0, 5).map((h) => (
                <li key={h}>{h}</li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

function RetroStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-zinc-600">{label}</dt>
      <dd className="font-semibold tabular-nums text-zinc-100">{value}</dd>
    </div>
  );
}
