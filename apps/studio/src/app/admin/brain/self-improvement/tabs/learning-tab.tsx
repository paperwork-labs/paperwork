"use client";

import { useEffect, useState } from "react";

import { fetchSelfImprovementJson } from "../lib/fetch-self-improvement";

type LearningState = {
  ok?: boolean;
  error?: string | null;
  open_candidates: number;
  accepted_candidates: number;
  declined_candidates: number;
  superseded_candidates: number;
  conversion_rate: number | null;
  generated_at: string | null;
};

export function LearningTab() {
  const [row, setRow] = useState<LearningState | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetchSelfImprovementJson<LearningState>("learning-state");
      if (cancelled) return;
      if (res.success && res.data) setRow(res.data);
      else
        setRow({
          ok: false,
          error: res.error ?? "Unknown error",
          open_candidates: 0,
          accepted_candidates: 0,
          declined_candidates: 0,
          superseded_candidates: 0,
          conversion_rate: null,
          generated_at: null,
        });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!row) {
    return <p className="text-sm text-zinc-500">Loading…</p>;
  }

  const conv =
    row.conversion_rate == null || Number.isNaN(row.conversion_rate)
      ? "—"
      : `${row.conversion_rate.toFixed(1)}%`;

  return (
    <div className="space-y-4" data-testid="learning-tab">
      {row.ok === false && row.error ? (
        <p className="rounded-md border border-amber-900/50 bg-amber-950/30 p-3 text-sm text-amber-100" role="status">
          {row.error}
        </p>
      ) : null}
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Open candidates" value={row.open_candidates} testId="open-candidates" />
        <Stat label="Accepted (promoted)" value={row.accepted_candidates} testId="accepted-candidates" />
        <Stat label="Declined" value={row.declined_candidates} testId="declined-candidates" />
        <Stat label="Superseded" value={row.superseded_candidates} testId="superseded-candidates" />
      </dl>
      <p className="text-sm text-zinc-300">
        Conversion (accepted / (accepted + declined)): <span className="font-semibold text-zinc-100">{conv}</span>
      </p>
      <p className="text-xs text-zinc-500">
        Source: <code className="text-zinc-400">apis/brain/data/workstream_candidates.json</code>
        {row.generated_at ? ` · generated_at ${row.generated_at}` : ""}
      </p>
    </div>
  );
}

function Stat({ label, value, testId }: { label: string; value: number; testId: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
      <dt className="text-xs uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tabular-nums text-zinc-100" data-testid={testId}>
        {value}
      </dd>
    </div>
  );
}
