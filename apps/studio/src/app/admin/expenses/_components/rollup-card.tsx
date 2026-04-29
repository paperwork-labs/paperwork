import { Download } from "lucide-react";
import type { ExpenseRollup } from "@/lib/expenses";
import { formatCents, CATEGORY_LABELS } from "@/lib/expenses";

type Props = {
  rollup: ExpenseRollup;
  exportUrl: string;
};

export function RollupCard({ rollup, exportUrl }: Props) {
  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Period
          </p>
          <p className="mt-0.5 text-lg font-semibold text-zinc-100">{rollup.period}</p>
        </div>
        <div className="text-right">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Total</p>
          <p className="mt-0.5 text-2xl font-bold text-zinc-100">
            {formatCents(rollup.total_cents)}
          </p>
          <p className="text-xs text-zinc-600">{rollup.count} expense{rollup.count !== 1 ? "s" : ""}</p>
        </div>
      </div>

      {rollup.by_category.length > 0 ? (
        <div className="space-y-2">
          {rollup.by_category.map((cat) => {
            const pct = rollup.total_cents > 0
              ? Math.round((cat.total_cents / rollup.total_cents) * 100)
              : 0;
            return (
              <div key={cat.category}>
                <div className="mb-0.5 flex items-center justify-between text-xs">
                  <span className="text-zinc-400">
                    {CATEGORY_LABELS[cat.category] ?? cat.category}
                  </span>
                  <span className="font-mono text-zinc-300">
                    {formatCents(cat.total_cents)} ({pct}%)
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800" aria-hidden>
                  <div
                    className="h-full rounded-full bg-zinc-400"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="py-4 text-center text-xs text-zinc-600">No expenses in this period.</p>
      )}

      <div className="mt-4 flex justify-end">
        <a
          href={exportUrl}
          download
          className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-800/80 px-3 py-1.5 text-xs font-medium text-zinc-300 ring-1 ring-zinc-700 transition hover:bg-zinc-700"
          aria-label={`Export ${rollup.period} expenses as CSV`}
        >
          <Download className="h-3.5 w-3.5" />
          Export CSV
        </a>
      </div>
    </div>
  );
}
