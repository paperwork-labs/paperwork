import Link from "next/link";

import { BrainImprovementGaugeBody } from "@/components/admin/BrainImprovementGaugeBody";
import { BII_FORMULA } from "@/lib/brain-improvement-formula";
import type { SelfImprovementPayload } from "@/lib/self-improvement";
import type { BrainImprovementResponse } from "@/types/brain-improvement";

const GH_MAIN =
  "https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/data";

function fallbackImprovementResponse(note: string): BrainImprovementResponse {
  return {
    current: {
      score: 0,
      acceptance_rate_pct: 0,
      promotion_progress_pct: 0,
      rules_count: 0,
      retro_delta_pct: 0,
      computed_at: new Date().toISOString(),
      note,
    },
    history_12w: [],
  };
}

export function IndexTab(props: {
  payload: SelfImprovementPayload;
  brainConfigured: boolean;
}) {
  const { payload, brainConfigured } = props;

  let err = payload.brainImprovementError;
  let data: BrainImprovementResponse;
  if (payload.brainImprovement) {
    data = payload.brainImprovement;
  } else if (!brainConfigured) {
    data = fallbackImprovementResponse("Brain API not configured for Studio.");
    err = null;
  } else {
    data = fallbackImprovementResponse(
      err ? `Could not load Brain Improvement Index (${err}).` : "No payload returned from Brain.",
    );
  }

  return (
    <div className="space-y-8 text-zinc-200">
      <p className="text-xs text-zinc-500">
        Composite score uses the same weights as{" "}
        <code className="text-zinc-400">compute_brain_improvement_index</code> in Brain (
        <code className="text-zinc-400">apis/brain/app/services/self_improvement.py</code>). PR P may extend
        sub-metrics.
      </p>

      {err && brainConfigured ? (
        <p className="rounded-lg border border-rose-800/50 bg-rose-950/30 px-3 py-2 text-sm text-rose-200">
          API error: {err}
        </p>
      ) : null}

      <BrainImprovementGaugeBody data={data} brainConfigured={brainConfigured} />

      <section className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-widest text-zinc-400">Formula</h2>
        <p className="mt-2 text-sm leading-relaxed text-zinc-400">
          Score = round(
          <span className="text-zinc-200">
            {" "}
            {BII_FORMULA.W_ACCEPTANCE} × acceptance_rate_pct + {BII_FORMULA.W_PROMOTION} ×
            promotion_progress_pct + {BII_FORMULA.W_RULES} × rules_normalized + {BII_FORMULA.W_RETRO} ×
            retro_delta_normalized
          </span>
          ), clamped 0–100.
        </p>
        <ul className="mt-4 space-y-2 text-sm text-zinc-400">
          <li>
            <strong className="text-zinc-300">acceptance_rate_pct</strong> — % of h24-measured PRs where{" "}
            <code className="text-zinc-500">reverted=false</code> (0 when none measured).
          </li>
          <li>
            <strong className="text-zinc-300">promotion_progress_pct</strong> — clean merges toward the next
            self-merge tier / {BII_FORMULA.PROMOTION_THRESHOLD}, capped 100.
          </li>
          <li>
            <strong className="text-zinc-300">rules_normalized</strong> —{" "}
            <code className="text-zinc-500">min(rules_count / {BII_FORMULA.RULES_CAP}, 1) × 100</code>
          </li>
          <li>
            <strong className="text-zinc-300">retro_delta_normalized</strong> — from latest weekly retro{" "}
            <code className="text-zinc-500">pos_total_change</code>:{" "}
            <code className="text-zinc-500">
              clamp(0, 100, {BII_FORMULA.RETRO_NEUTRAL} + pos_total_change × {BII_FORMULA.RETRO_SCALE})
            </code>
            ; 0 when no retros yet.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-widest text-zinc-400">Source files</h2>
        <ul className="space-y-1 text-sm text-indigo-400">
          <li>
            <Link className="hover:underline" href={`${GH_MAIN}/pr_outcomes.json`}>
              pr_outcomes.json
            </Link>
          </li>
          <li>
            <Link className="hover:underline" href={`${GH_MAIN}/self_merge_promotions.json`}>
              self_merge_promotions.json
            </Link>
          </li>
          <li>
            <Link className="hover:underline" href={`${GH_MAIN}/procedural_memory.yaml`}>
              procedural_memory.yaml
            </Link>
          </li>
          <li>
            <Link className="hover:underline" href={`${GH_MAIN}/weekly_retros.json`}>
              weekly_retros.json
            </Link>
          </li>
        </ul>
      </section>

      <p className="text-xs text-zinc-600">
        12-week sparkline fills after Brain persists weekly history (currently often empty on disk — honest
        empty state in the gauge above).
      </p>
    </div>
  );
}
