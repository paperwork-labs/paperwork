"use client";

import { useCallback, useEffect, useState } from "react";

type SystemHealthData = {
  brain_paused?: boolean;
  brain_paused_reason?: string | null;
  writeback_last_run?: string | null;
  last_pr_opened?: {
    pr_number: number;
    branch: string;
    opened_at: string;
  } | null;
  last_drift_check?: string | null;
  scheduler_skew_seconds?: number | null;
  merge_queue_depth?: number;
  pending_workstreams?: number;
  procedural_rules_count?: number;
};

type Envelope = { success?: boolean; data?: SystemHealthData; error?: string };

function freshnessValueClass(iso: string | null | undefined): string {
  if (iso == null || iso === "") return "text-zinc-500";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "text-zinc-500";
  const ageSec = (Date.now() - t) / 1000;
  if (ageSec < 5 * 60) return "text-emerald-400";
  if (ageSec < 30 * 60) return "text-amber-400";
  return "text-rose-400";
}

function Row({
  label,
  value,
  toneClass,
}: {
  label: string;
  value: string;
  toneClass: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-zinc-800/80 py-2 last:border-b-0">
      <span className="text-xs uppercase tracking-wide text-zinc-500">{label}</span>
      <span className={`max-w-[65%] text-right text-sm break-words ${toneClass}`}>{value}</span>
    </div>
  );
}

export function BrainFreshnessTile() {
  const [data, setData] = useState<SystemHealthData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/admin/system-health");
      const json = (await res.json()) as Envelope;
      if (!res.ok || json.success === false) {
        setError(json.error ?? `HTTP ${res.status}`);
        setData(null);
        return;
      }
      setData(json.data ?? null);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), 60_000);
    return () => clearInterval(id);
  }, [load]);

  if (loading && data == null && !error) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6 ring-1 ring-zinc-800">
        <p className="text-sm text-zinc-500">Loading Brain freshness…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6 ring-1 ring-rose-500/25">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-rose-300/90">
          Brain freshness
        </p>
        <p className="mt-2 text-sm text-rose-200">{error}</p>
      </div>
    );
  }

  const d = data ?? {};
  const paused = Boolean(d.brain_paused);
  const pr = d.last_pr_opened;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6 ring-1 ring-zinc-800">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
        Brain freshness
      </p>
      <p className="mt-1 text-xs text-zinc-500">
        Proxied Live from Brain <code className="text-zinc-400">/api/v1/admin/system-health</code>
      </p>
      <div className="mt-3">
        <Row
          label="Brain paused"
          value={paused ? "Yes" : "No"}
          toneClass={paused ? "text-rose-400" : "text-emerald-400"}
        />
        <Row
          label="Pause reason"
          value={d.brain_paused_reason ?? "—"}
          toneClass={
            d.brain_paused_reason == null || d.brain_paused_reason === ""
              ? "text-zinc-500"
              : "text-amber-400"
          }
        />
        <Row
          label="Writeback last run"
          value={d.writeback_last_run ?? "—"}
          toneClass={freshnessValueClass(d.writeback_last_run)}
        />
        <Row
          label="Last PR opened"
          value={
            pr
              ? `#${pr.pr_number} ${pr.branch} @ ${pr.opened_at}`
              : "—"
          }
          toneClass={freshnessValueClass(pr?.opened_at)}
        />
        <Row
          label="Last drift check"
          value={d.last_drift_check ?? "—"}
          toneClass={freshnessValueClass(d.last_drift_check)}
        />
        <Row
          label="Scheduler skew (s)"
          value={
            d.scheduler_skew_seconds == null ? "—" : String(d.scheduler_skew_seconds)
          }
          toneClass="text-zinc-500"
        />
        <Row
          label="Merge queue depth"
          value={String(d.merge_queue_depth ?? 0)}
          toneClass="text-zinc-300"
        />
        <Row
          label="Pending workstreams"
          value={String(d.pending_workstreams ?? 0)}
          toneClass="text-zinc-300"
        />
        <Row
          label="Procedural rules"
          value={String(d.procedural_rules_count ?? 0)}
          toneClass="text-zinc-300"
        />
      </div>
    </div>
  );
}
