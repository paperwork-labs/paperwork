import { fetchExpenses } from "@/lib/expenses";
import { ExpenseList } from "../_components/expense-list";
import { SubmitExpenseModal } from "../_components/submit-expense-modal";

export async function InboxTab() {
  const pending = await fetchExpenses("pending");
  const flagged = await fetchExpenses("flagged");

  const combined =
    pending && flagged
      ? {
          items: [...flagged.items, ...pending.items],
          next_cursor: pending.next_cursor,
          total: pending.total + flagged.total,
        }
      : pending ?? flagged;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-zinc-200">Inbox — Pending &amp; Flagged</h2>
          <p className="text-xs text-zinc-500">
            Expenses waiting for founder review. Auto-approve threshold is $0 — every expense
            requires manual approval.
          </p>
        </div>
        <SubmitExpenseModal />
      </div>
      <ExpenseList initialData={combined} filter="pending" showActions />
    </div>
  );
}
