import type { SelfImprovementPayload } from "@/lib/self-improvement";

export function PromotionsTab(props: { payload: SelfImprovementPayload }) {
  const { promotions } = props.payload;
  const meta = promotions.promotionsMeta;

  return (
    <div className="space-y-6 text-zinc-200">
      <p className="text-xs text-zinc-500">
        {meta.asOfIso ? `As of ${meta.asOfIso} (file mtime)` : "As-of unavailable"}
      </p>

      {meta.missing ? (
        <p className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4 text-sm text-zinc-400">
          <code className="text-zinc-300">self_merge_promotions.json</code> not found — promotions data will
          populate after Brain records merges.
        </p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
              <p className="text-xs uppercase tracking-widest text-zinc-500">Current tier</p>
              <p className="mt-2 text-xl font-semibold capitalize text-zinc-50">
                {promotions.currentTier.replace(/-/g, " ")}
              </p>
            </div>
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
              <p className="text-xs uppercase tracking-widest text-zinc-500">Clean merges (tier / 30d)</p>
              <p className="mt-2 text-xl font-semibold tabular-nums text-zinc-50">
                {promotions.cleanMergesCurrentTier}{" "}
                <span className="text-sm font-normal text-zinc-500">
                  / {promotions.promotionThreshold}
                </span>
              </p>
            </div>
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
              <p className="text-xs uppercase tracking-widest text-zinc-500">Threshold per tier</p>
              <p className="mt-2 text-xl font-semibold tabular-nums text-zinc-50">
                {promotions.promotionThreshold}
              </p>
            </div>
          </div>

          <section className="space-y-2">
            <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">
              Recent reverts
            </h2>
            <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead>
                  <tr className="border-b border-zinc-800/80 text-xs uppercase tracking-wider text-zinc-500">
                    <th className="p-3 font-medium">Revert PR</th>
                    <th className="p-3 font-medium">Original PR</th>
                    <th className="p-3 font-medium">When</th>
                    <th className="p-3 font-medium">Rationale</th>
                  </tr>
                </thead>
                <tbody>
                  {promotions.reverts.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="p-4 text-zinc-500">
                        No reverts recorded.
                      </td>
                    </tr>
                  ) : (
                    promotions.reverts.map((r) => (
                      <tr key={`${r.pr_number}-${r.original_pr}`} className="border-b border-zinc-800/40">
                        <td className="p-3 font-mono text-xs">{r.pr_number}</td>
                        <td className="p-3 font-mono text-xs">{r.original_pr}</td>
                        <td className="p-3 text-xs text-zinc-500">{r.reverted_at}</td>
                        <td className="p-3 text-zinc-400">{r.reason || "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">
              Tier graduation history
            </h2>
            <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead>
                  <tr className="border-b border-zinc-800/80 text-xs uppercase tracking-wider text-zinc-500">
                    <th className="p-3 font-medium">From</th>
                    <th className="p-3 font-medium">To</th>
                    <th className="p-3 font-medium">When</th>
                    <th className="p-3 font-medium">Clean merges @ promo</th>
                    <th className="p-3 font-medium">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {promotions.graduationHistory.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-4 text-zinc-500">
                        No tier promotions recorded yet.
                      </td>
                    </tr>
                  ) : (
                    promotions.graduationHistory.map((g, i) => (
                      <tr key={`${g.from_tier}-${g.to_tier}-${i}`} className="border-b border-zinc-800/40">
                        <td className="p-3 capitalize">{g.from_tier.replace(/-/g, " ")}</td>
                        <td className="p-3 capitalize">{g.to_tier.replace(/-/g, " ")}</td>
                        <td className="p-3 text-xs text-zinc-500">{g.promoted_at}</td>
                        <td className="p-3 tabular-nums">{g.clean_merge_count_at_promotion}</td>
                        <td className="p-3 text-zinc-400">{g.notes || "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      <p className="text-xs text-zinc-600">
        Source: <code className="text-zinc-400">apis/brain/data/self_merge_promotions.json</code>
      </p>
    </div>
  );
}
