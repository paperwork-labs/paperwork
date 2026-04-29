import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import type { BrainImprovementCurrent, BrainImprovementResponse } from "@/types/brain-improvement";

import { BrainImprovementGaugeBody } from "./BrainImprovementGaugeBody";

function emptyBrainImprovementCurrent(): BrainImprovementCurrent {
  return {
    score: 0,
    acceptance_rate_pct: 0,
    promotion_progress_pct: 0,
    rules_count: 0,
    retro_delta_pct: 0,
    computed_at: new Date().toISOString(),
    note: "insufficient data: no PR outcomes measured yet",
  };
}

function emptyBrainImprovementResponse(): BrainImprovementResponse {
  return {
    current: emptyBrainImprovementCurrent(),
    history_12w: [],
  };
}

export async function BrainImprovementGauge() {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return <BrainImprovementGaugeBody data={emptyBrainImprovementResponse()} brainConfigured={false} />;
  }

  const res = await fetch(`${auth.root}/admin/brain-improvement-index`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });

  if (!res.ok) {
    return (
      <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-5">
        <p className="text-xs uppercase tracking-wide text-rose-300/80">Brain growth</p>
        <p className="mt-2 text-sm text-rose-200">
          Could not load Brain Improvement Index from Brain (HTTP {res.status}).
        </p>
      </div>
    );
  }

  const json = (await res.json()) as {
    success?: boolean;
    data?: BrainImprovementResponse;
    error?: string;
  };

  if (json.success === false || json.data == null) {
    return (
      <div className="rounded-xl border border-rose-900/40 bg-rose-950/20 p-5">
        <p className="text-xs uppercase tracking-wide text-rose-300/80">Brain growth</p>
        <p className="mt-2 text-sm text-rose-200">
          {json.error ?? "Brain returned an invalid Brain Improvement payload."}
        </p>
      </div>
    );
  }

  return <BrainImprovementGaugeBody data={json.data} brainConfigured />;
}
