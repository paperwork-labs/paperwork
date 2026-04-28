"use client";

import { Workflow } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  formatBytesIEC,
  formatPercent1,
  formatPipelineMinutes,
  pctOf,
  thresholdToneFromPct,
  toneAccentClass,
} from "@/lib/quota-monitor-format";
import type { GitHubActionsQuotaApiPayload, GitHubActionsQuotaSnapshotRow } from "@/lib/quota-monitor-types";
import { QuotaPanelFrame, fetchBrainEnvelope, quotaBar } from "./quota-shared";

const API = "/api/admin/quota/github-actions";

function latestSnapshotPerRepo(rows: GitHubActionsQuotaSnapshotRow[]): GitHubActionsQuotaSnapshotRow[] {
  const map = new Map<string, GitHubActionsQuotaSnapshotRow>();
  for (const r of rows) {
    const prev = map.get(r.repo);
    const curT = Date.parse(r.recorded_at ?? "");
    const prevT = prev?.recorded_at ? Date.parse(prev.recorded_at) : -Infinity;
    if (!prev || (Number.isFinite(curT) && curT >= prevT)) {
      map.set(r.repo, r);
    }
  }
  return [...map.values()].sort((a, b) => a.repo.localeCompare(b.repo));
}

/** Single-row risk score 0–100 for banding (public: any paid minutes drive high band). */
function rowPct(row: GitHubActionsQuotaSnapshotRow): number {
  if (row.is_public) {
    const paid = row.paid_minutes_used ?? 0;
    if (paid > 0) return 95;
    return 0;
  }
  const used = row.minutes_used ?? 0;
  const inc = row.included_minutes;
  if (typeof inc === "number" && inc > 0) {
    return pctOf(used, inc) ?? 0;
  }
  const lim = row.minutes_limit;
  if (typeof lim === "number" && lim > 0) {
    return pctOf(used, lim) ?? 0;
  }
  return 0;
}

function PaidOsBreakdown({ row }: { row: GitHubActionsQuotaSnapshotRow }) {
  const b = row.total_paid_minutes_used_breakdown ?? {};
  const entries = Object.entries(b).filter(([, v]) => typeof v === "number" && (v as number) > 0) as [
    string,
    number,
  ][];
  if (!entries.length) return null;
  entries.sort((a, b) => b[1] - a[1]);
  const line = entries
    .slice(0, 5)
    .map(([k, v]) => `${k}: ${v.toFixed(1)}m`)
    .join(" · ");
  return <p className="text-[10px] text-zinc-500">Paid by OS: {line}</p>;
}

function MinutesUsedMicroBreakdown({ row }: { row: GitHubActionsQuotaSnapshotRow }) {
  const u = row.minutes_used_breakdown ?? {};
  const entries = Object.entries(u).filter(([, v]) => typeof v === "number" && (v as number) > 0) as [
    string,
    number,
  ][];
  if (!entries.length) return null;
  entries.sort((a, b) => b[1] - a[1]);
  const line = entries
    .slice(0, 4)
    .map(([k, v]) => `${k}: ${formatPipelineMinutes(v)}`)
    .join(" · ");
  return <p className="text-[10px] text-zinc-600">Burn mix: {line}</p>;
}

export default function QuotaGitHubActionsPanel(props: { refreshSignal: number }) {
  const { refreshSignal } = props;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<GitHubActionsQuotaApiPayload | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const { data, error: err } = await fetchBrainEnvelope<GitHubActionsQuotaApiPayload>(API);
    if (err) setError(err);
    setPayload(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (refreshSignal > 0) void load();
  }, [refreshSignal, load]);

  const repos = useMemo(
    () => latestSnapshotPerRepo(payload?.snapshots ?? []),
    [payload?.snapshots],
  );

  const { worstPct, headline, recordedIso } = useMemo(() => {
    if (!repos.length) {
      return {
        worstPct: 0,
        headline: "No GitHub Actions billing snapshots yet (Brain github_actions_quota_monitor).",
        recordedIso: payload?.batch_at ?? null,
      };
    }
    let worst = 0;
    for (const r of repos) worst = Math.max(worst, rowPct(r));
    const priv = repos.filter((x) => !x.is_public);
    const headlineInner =
      priv.length === 1
        ? `${priv[0]!.repo} · ${formatPercent1(rowPct(priv[0]!))} vs included (${formatPipelineMinutes(priv[0]!.minutes_used ?? 0)} / ${priv[0]!.included_minutes ?? "—"}m)`
        : `${repos.length} repos · peak pressure ${formatPercent1(worst)}`;
    return {
      worstPct: worst,
      headline: headlineInner,
      recordedIso: payload?.batch_at ?? repos[0]?.recorded_at ?? null,
    };
  }, [payload?.batch_at, repos]);

  return (
    <QuotaPanelFrame
      testId="quota-panel-github-actions"
      icon={Workflow}
      title="GitHub Actions"
      subtitle="Org billing minutes · paid runners · Actions cache footprint"
      brainHint={`GET …/admin/quota/github-actions → proxied ${API}`}
      loading={loading}
      error={error}
      recordedIso={recordedIso}
      worstPctGuess={worstPct}
      headline={headline}
    >
      {!loading && !error && repos.length ? (
        <div className="space-y-3 text-xs">
          <ul className="max-h-56 space-y-2 overflow-auto pr-1">
            {repos.map((row) => {
              const pct = rowPct(row);
              const tone = thresholdToneFromPct(pct);
              return (
                <li
                  key={row.repo}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-2 py-2 text-zinc-300"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-mono text-[11px] text-zinc-200">{row.repo}</span>
                    <span className="shrink-0 rounded border border-zinc-800 px-1 py-0.5 text-[10px] text-zinc-500">
                      {row.is_public ? "public" : "private"}
                    </span>
                  </div>
                  <div className="mt-2 space-y-1">
                    <div className="flex justify-between gap-2 text-[10px] text-zinc-500">
                      <span>Quota pressure</span>
                      <span className={`font-mono ${toneAccentClass(tone).text}`}>{formatPercent1(pct)}</span>
                    </div>
                    {quotaBar(pct, tone)}
                    <p className="text-[10px] text-zinc-500">
                      Used {formatPipelineMinutes(row.minutes_used ?? 0)}
                      {typeof row.included_minutes === "number" && row.included_minutes > 0
                        ? ` · included ${row.included_minutes}m`
                        : ""}
                      {typeof row.minutes_limit === "number" && row.minutes_limit > 0
                        ? ` · limit ${row.minutes_limit}m`
                        : ""}
                      {(row.paid_minutes_used ?? 0) > 0 ? ` · paid ${(row.paid_minutes_used ?? 0).toFixed(1)}m` : ""}
                    </p>
                    <PaidOsBreakdown row={row} />
                    <MinutesUsedMicroBreakdown row={row} />
                    {row.cache_size_bytes != null && row.cache_size_bytes > 0 ? (
                      <p className="text-[10px] text-zinc-600">
                        Cache {formatBytesIEC(row.cache_size_bytes)}
                        {row.cache_count != null ? ` (${row.cache_count} keys)` : ""}
                      </p>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </QuotaPanelFrame>
  );
}
