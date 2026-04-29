import { fetchExpenses } from "@/lib/expenses";
import { ExpenseList } from "../_components/expense-list";
import { SubmitExpenseModal } from "../_components/submit-expense-modal";

export async function AllTab() {
  const data = await fetchExpenses("all");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-zinc-200">All Expenses</h2>
          <p className="text-xs text-zinc-500">Complete expense ledger across all statuses.</p>
        </div>
        <SubmitExpenseModal />
      </div>
      <ExpenseList initialData={data} filter="all" showActions />
    </div>
  );
}
