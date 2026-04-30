"use client";

import { Cloud } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  formatPercent1,
  formatPipelineMinutes,
  pctOf,
  thresholdToneFromPct,
  toneAccentClass,
} from "@/lib/quota-monitor-format";
import type { RenderQuotaApiPayload, RenderTopServiceMinutes } from "@/lib/quota-monitor-types";
import {
  QuotaPanelFrame,
  QUOTA_CRON_STALE_THRESHOLD_MINUTES,
  fetchBrainEnvelope,
  quotaBar,
} from "./quota-shared";
import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";

const API = "/api/admin/quota/render";

export default function QuotaRenderPanel(props: { refreshSignal: number }) {
  const { refreshSignal } = props;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<RenderQuotaApiPayload | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const { data, error: err } = await fetchBrainEnvelope<RenderQuotaApiPayload>(API);
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

  const { worstPct, headline, recordedIso, snap } = useMemo(() => {
    const s = payload?.snapshot;
    if (!s) {
      return {
        worstPct: 0,
        headline: "",
        recordedIso: null as string | null,
        snap: null as typeof s,
      };
    }
    const pipePct =
      pctOf(s.pipeline_minutes_used, s.pipeline_minutes_included) ??
      (Number.isFinite(s.usage_ratio) ? Math.min(100, Math.max(0, s.usage_ratio * 100)) : 0);
    let bwPct = 0;
    const bu = s.bandwidth_gb_used;
    const bi = s.bandwidth_gb_included;
    if (typeof bu === "number" && typeof bi === "number" && bi > 0) {
      bwPct = pctOf(bu, bi) ?? 0;
    }
    const worst = Math.max(pipePct, bwPct);
    const bwLine =
      typeof bu === "number" && typeof bi === "number"
        ? ` · bandwidth ${bu.toFixed(2)} / ${bi.toFixed(0)} GB (${formatPercent1(bwPct)})`
        : "";
    const head = `${s.month} · pipeline ${formatPipelineMinutes(s.pipeline_minutes_used)} / ${formatPipelineMinutes(s.pipeline_minutes_included)} (${formatPercent1(pipePct)})${bwLine} · derived ${s.derived_from}`;
    return {
      worstPct: worst,
      headline: head,
      recordedIso: s.recorded_at,
      snap: s,
    };
  }, [payload?.snapshot]);

  const tops = payload?.top_services_by_minutes ?? [];

  const pipePctDisplay = snap
    ? pctOf(snap.pipeline_minutes_used, snap.pipeline_minutes_included) ??
      (Number.isFinite(snap.usage_ratio) ? Math.min(100, snap.usage_ratio * 100) : 0)
    : 0;

  const bwPctDisplay =
    snap &&
    typeof snap.bandwidth_gb_used === "number" &&
    typeof snap.bandwidth_gb_included === "number" &&
    snap.bandwidth_gb_included > 0
      ? pctOf(snap.bandwidth_gb_used, snap.bandwidth_gb_included) ?? 0
      : null;

  return (
    <QuotaPanelFrame
      testId="quota-panel-render"
      icon={Cloud}
      title="Render"
      subtitle="Pipeline build minutes + bandwidth (workspace monitor)"
      brainHint={`GET …/admin/render-quota → proxied ${API}`}
      loading={loading}
      error={error}
      recordedIso={recordedIso}
      worstPctGuess={worstPct}
      headline={headline}
      staleThresholdMinutes={QUOTA_CRON_STALE_THRESHOLD_MINUTES.render}
    >
      {!loading && !error && snap ? (
        <div className="space-y-4 text-xs">
          <div>
            <div className="mb-1 flex justify-between gap-2 text-[10px] text-zinc-500">
              <span>Pipeline minutes</span>
              <span className={toneAccentClass(thresholdToneFromPct(pipePctDisplay)).text}>
                {formatPercent1(pipePctDisplay)}
              </span>
            </div>
            {quotaBar(pipePctDisplay, thresholdToneFromPct(pipePctDisplay))}
          </div>
          {bwPctDisplay !== null ? (
            <div>
              <div className="mb-1 flex justify-between gap-2 text-[10px] text-zinc-500">
                <span>Bandwidth (GB)</span>
                <span className={toneAccentClass(thresholdToneFromPct(bwPctDisplay)).text}>
                  {formatPercent1(bwPctDisplay)}
                </span>
              </div>
              {quotaBar(bwPctDisplay, thresholdToneFromPct(bwPctDisplay))}
            </div>
          ) : null}
          {typeof snap.unbilled_charges_usd === "number" && snap.unbilled_charges_usd > 0 ? (
            <p className="text-[10px] text-amber-200/90">
              Unbilled (workspace) ≈ ${snap.unbilled_charges_usd.toFixed(2)} USD — confirm in Render billing.
            </p>
          ) : null}
          {tops.length > 0 ? (
            <div>
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                Top services by pipeline minutes
              </p>
              <ul className="max-h-36 space-y-1 overflow-auto font-mono text-[10px] text-zinc-400">
                {tops.slice(0, 12).map((t: RenderTopServiceMinutes, idx: number) => (
                  <li key={`${String(t.service_id ?? t.name ?? idx)}`}>
                    {(t.name ?? t.service_id ?? "?") + ": "}
                    {typeof t.approx_minutes === "number" ? `${t.approx_minutes.toFixed(1)}m` : "—"}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : !loading && !error ? (
        <HqEmptyState
          title="No Render workspace snapshot yet"
          description="Brain job `render_quota_monitor` has not written a workspace snapshot — check Brain schedulers and Render API wiring."
        />
      ) : null}
    </QuotaPanelFrame>
  );
}
