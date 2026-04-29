export default function AdminExpensesPlaceholderPage() {
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold text-zinc-100">Expenses</h1>
      <p className="text-sm text-zinc-500">
        Expense reporting v1 lands in WS-69 PR N — until then see{" "}
        <code className="rounded bg-zinc-800 px-1 text-xs">docs/FINANCIALS.md</code>.
      </p>
    </div>
  );
}

export const dynamic = "force-static";
