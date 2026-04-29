import { Receipt } from "lucide-react";

export const dynamic = "force-dynamic";

// PR N populates this page with full expense tracking, budget vs. actuals,
// and vendor cost breakdown.

export default function ExpensesPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Expenses
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Company expense tracking, budget vs. actuals, and vendor cost breakdown.
        </p>
      </header>
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-700 bg-zinc-900/40 py-20 text-center">
        <Receipt className="mb-4 h-10 w-10 text-zinc-600" />
        <h2 className="text-base font-semibold text-zinc-300">Expenses — coming soon</h2>
        <p className="mt-2 max-w-md text-sm text-zinc-500">
          Full expense ledger with budget vs. actuals, vendor breakdown, and monthly trend
          charts. PR N wires the data pipeline and renders the expense dashboard.
        </p>
        <span className="mt-4 rounded-full border border-zinc-700 bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-400">
          PR N populates
        </span>
      </div>
    </div>
  );
}
