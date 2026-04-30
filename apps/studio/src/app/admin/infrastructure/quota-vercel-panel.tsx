"use client";

import { Gauge } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  VERCEL_BUILD_30D_CAP,
  VERCEL_DEPLOY_DAILY_CAP,
  formatPercent1,
  pctOf,
  thresholdToneFromPct,
  toneAccentClass,
} from "@/lib/quota-monitor-format";
import type { VercelQuotaApiPayload, VercelQuotaSnapshotRow } from "@/lib/quota-monitor-types";
import { QuotaPanelFrame, fetchBrainEnvelope, quotaBar } from "./quota-shared";
import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";

const API = "/api/admin/quota/vercel";

function mergeProjectWindows(rows: VercelQuotaSnapshotRow[]) {
  const map = new Map<
    string,
    { name: string; project_id: string | null; d24: number; m30: number }
  >();
  for (const r of rows) {
    const key = r.project_id ?? `name:${r.project_name}`;
    let cur = map.get(key);
    if (!cur) {
      cur = { name: r.project_name, project_id: r.project_id, d24: 0, m30: 0 };
      map.set(key, cur);
    }
    if (r.window_days === 1) cur.d24 = r.deploy_count;
    if (r.window_days === 30) cur.m30 = r.build_minutes;
  }
  return [...map.values()];
}

export default function QuotaVercelPanel(props: { refreshSignal: number }) {
  const { refreshSignal } = props;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<VercelQuotaApiPayload | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const { data, error: err } = await fetchBrainEnvelope<VercelQuotaApiPayload>(API);
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

  const merged = useMemo(() => mergeProjectWindows(payload?.snapshots ?? []), [payload]);

  const { team, projects, headline, worstPct, recordedIso } = useMemo(() => {
    const teamMerged = merged.find((m) => m.name === "(team)");
    const projectsList = merged
      .filter((m) => m.name !== "(team)")
      .map((p) => {
        const pu = pctOf(p.d24, VERCEL_DEPLOY_DAILY_CAP) ?? 0;
        const pb = pctOf(p.m30, VERCEL_BUILD_30D_CAP) ?? 0;
        return { ...p, worst: Math.max(pu, pb), deployPct: pu, buildPct: pb };
      })
      .sort((a, b) => b.worst - a.worst);

    let worst = 0;
    let headlineInner = "";
    if (teamMerged) {
      const dPct = pctOf(teamMerged.d24, VERCEL_DEPLOY_DAILY_CAP) ?? 0;
      const bPct = pctOf(teamMerged.m30, VERCEL_BUILD_30D_CAP) ?? 0;
      worst = Math.max(dPct, bPct);
      headlineInner = `Team · 24h deploys ${teamMerged.d24}/${VERCEL_DEPLOY_DAILY_CAP} (${formatPercent1(dPct)} of proxy cap) · 30d build ${formatPipelineShort(teamMerged.m30)}/${VERCEL_BUILD_30D_CAP}m (${formatPercent1(bPct)})`;
    }
    return {
      team: teamMerged,
      projects: projectsList,
      headline: headlineInner,
      worstPct: worst,
      recordedIso: payload?.batch_at ?? null,
    };
  }, [merged, payload?.batch_at]);

  return (
    <QuotaPanelFrame
      testId="quota-panel-vercel"
      icon={Gauge}
      title="Vercel"
      subtitle="Rolling deploy velocity + build minutes (Brain hobby proxy caps)"
      brainHint={`GET …/admin/vercel-quota → proxied ${API}`}
      loading={loading}
      error={error}
      recordedIso={recordedIso}
      worstPctGuess={worstPct}
      headline={headline}
    >
      {!loading && !error && team ? (
        <div className="space-y-4 text-xs">
          <QuotaMetricBlock
            label="24h deploys (team)"
            pct={pctOf(team.d24, VERCEL_DEPLOY_DAILY_CAP)}
            caption={`${team.d24} / ${VERCEL_DEPLOY_DAILY_CAP} deployments`}
          />
          <QuotaMetricBlock
            label="30d build minutes (team)"
            pct={pctOf(team.m30, VERCEL_BUILD_30D_CAP)}
            caption={`${formatPipelineShort(team.m30)} / ${VERCEL_BUILD_30D_CAP}m`}
          />
          {projects.length > 0 ? (
            <div>
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                Per-project (same proxy caps)
              </p>
              <ul className="max-h-48 space-y-2 overflow-auto pr-1 text-zinc-300">
                {projects.map((p) => (
                  <li key={p.project_id ?? p.name} className="rounded border border-zinc-800 bg-zinc-950/40 px-2 py-1.5">
                    <span className="font-medium text-zinc-100">{p.name}</span>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      <div>
                        <p className="text-[10px] text-zinc-500">24h deploys</p>
                        <QuotaMetricInline pct={pctOf(p.d24, VERCEL_DEPLOY_DAILY_CAP)} />
                      </div>
                      <div>
                        <p className="text-[10px] text-zinc-500">30d build</p>
                        <QuotaMetricInline pct={pctOf(p.m30, VERCEL_BUILD_30D_CAP)} />
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : !loading && !error ? (
        <HqEmptyState
          title="No Vercel quota snapshots yet"
          description="Brain job `vercel_quota_monitor` has not written snapshots — quotas appear here once the first batch lands."
        />
      ) : null}
    </QuotaPanelFrame>
  );
}

function formatPipelineShort(mins: number) {
  if (!Number.isFinite(mins)) return "—";
  return mins >= 120 ? `${(mins / 60).toFixed(1)}h` : `${Math.round(mins)}m`;
}

function QuotaMetricBlock({
  label,
  pct,
  caption,
}: {
  label: string;
  pct: number | null;
  caption: string;
}) {
  const p = pct ?? 0;
  const tone = thresholdToneFromPct(p);
  const { text } = toneAccentClass(tone);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-zinc-400">{label}</span>
        <span className={`font-mono tabular-nums ${text}`}>{formatPercent1(p)}</span>
      </div>
      {quotaBar(p, tone)}
      <p className="mt-1 text-[10px] text-zinc-600">{caption}</p>
    </div>
  );
}

function QuotaMetricInline({ pct }: { pct: number | null }) {
  const p = pct ?? 0;
  const tone = thresholdToneFromPct(p);
  const { text } = toneAccentClass(tone);
  return (
    <div className="flex items-center gap-2">
      {quotaBar(p, tone)}
      <span className={`font-mono text-[10px] tabular-nums ${text}`}>{formatPercent1(p)}</span>
    </div>
  );
}
