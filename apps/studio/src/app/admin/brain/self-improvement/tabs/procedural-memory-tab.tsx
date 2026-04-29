"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchSelfImprovementJson } from "../lib/fetch-self-improvement";

type Rule = {
  id: string;
  when: string;
  do: string;
  source: string;
  learned_at: string;
  confidence: string;
  applies_to: string[];
};

type ProcPayload = {
  count: number;
  rules: Rule[];
  applies_to_values: string[];
  error?: string | null;
};

const ALL = "__all__";

export function ProceduralMemoryTab() {
  const [data, setData] = useState<ProcPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<string>(ALL);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetchSelfImprovementJson<ProcPayload>("procedural-memory");
      if (cancelled) return;
      if (res.success && res.data) setData(res.data);
      else setErr(res.error ?? "Failed to load procedural memory");
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    if (!data?.rules) return [];
    const needle = q.trim().toLowerCase();
    return data.rules.filter((r) => {
      if (scope !== ALL && !r.applies_to.includes(scope)) return false;
      if (!needle) return true;
      return (
        r.id.toLowerCase().includes(needle) ||
        r.when.toLowerCase().includes(needle) ||
        r.do.toLowerCase().includes(needle) ||
        r.source.toLowerCase().includes(needle)
      );
    });
  }, [data, q, scope]);

  if (err && !data) {
    return (
      <p className="text-sm text-rose-200" role="alert">
        {err}
      </p>
    );
  }
  if (!data) return <p className="text-sm text-zinc-500">Loading…</p>;

  if (data.error || data.count === 0) {
    return (
      <p className="text-sm text-zinc-500" data-testid="procedural-empty">
        {data.error ?? "No procedural rules in scope."}
      </p>
    );
  }

  const chips = [ALL, ...data.applies_to_values];

  return (
    <div className="space-y-4" data-testid="procedural-tab">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <label className="block flex-1 text-sm text-zinc-400">
          Search rules
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none ring-sky-500/30 focus:ring-2"
            placeholder="id, when, do, source…"
            data-testid="procedural-search"
          />
        </label>
      </div>
      <div className="flex flex-wrap gap-2" role="toolbar" aria-label="Filter by applies_to">
        {chips.map((c) => {
          const label = c === ALL ? "All scopes" : c;
          const active = scope === c;
          return (
            <button
              key={c}
              type="button"
              onClick={() => setScope(c)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                active
                  ? "border-sky-600 bg-sky-950/50 text-sky-200"
                  : "border-zinc-800 bg-zinc-900/60 text-zinc-400 hover:text-zinc-200"
              }`}
              data-testid={c === ALL ? "chip-all" : `chip-${c}`}
            >
              {label}
            </button>
          );
        })}
      </div>
      <p className="text-xs text-zinc-500">
        Showing {filtered.length} of {data.count} rules ·{" "}
        <code className="text-zinc-400">apis/brain/data/procedural_memory.yaml</code>
      </p>
      <ul className="space-y-3">
        {filtered.map((r) => (
          <li
            key={r.id}
            className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4"
            data-testid="procedural-rule"
          >
            <p className="font-mono text-sm text-emerald-300/90">{r.id}</p>
            <p className="mt-1 text-xs text-zinc-500">
              {r.confidence} · {r.learned_at} · applies_to: {r.applies_to.join(", ")}
            </p>
            <p className="mt-2 text-sm text-zinc-200">
              <span className="text-zinc-500">When:</span> {r.when}
            </p>
            <p className="mt-1 text-sm text-zinc-300">
              <span className="text-zinc-500">Do:</span> {r.do}
            </p>
            <p className="mt-1 text-xs text-zinc-500">Source: {r.source}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
