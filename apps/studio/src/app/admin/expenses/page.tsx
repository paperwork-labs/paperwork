import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import { ExpensesClient } from "./expenses-client";
import type { Expense, ExpensesListPage, ExpenseRoutingRules } from "@/types/expenses";

export const dynamic = "force-dynamic";

async function fetchExpenses(auth: {
  root: string;
  secret: string;
}): Promise<{ expenses: Expense[]; total: number }> {
  try {
    const res = await fetch(
      `${auth.root}/admin/expenses?status=pending&limit=50`,
      {
        headers: { "X-Brain-Secret": auth.secret },
        cache: "no-store",
      }
    );
    if (!res.ok) return { expenses: [], total: 0 };
    const json = await res.json();
    if (!json.success) return { expenses: [], total: 0 };
    const page = json.data as ExpensesListPage;
    return { expenses: page.items, total: page.total };
  } catch {
    return { expenses: [], total: 0 };
  }
}

async function fetchRules(auth: {
  root: string;
  secret: string;
}): Promise<ExpenseRoutingRules | null> {
  try {
    const res = await fetch(`${auth.root}/admin/expenses/rules`, {
      headers: { "X-Brain-Secret": auth.secret },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const json = await res.json();
    return json.success ? (json.data as ExpenseRoutingRules) : null;
  } catch {
    return null;
  }
}

export default async function ExpensesPage() {
  const auth = getBrainAdminFetchOptions();

  if (!auth.ok) {
    return (
      <div className="rounded-xl border border-red-900/40 bg-red-500/5 p-8 text-center">
        <p className="text-sm font-medium text-red-400">Brain API not configured</p>
        <p className="mt-1 text-xs text-red-500/70">
          Set BRAIN_API_URL and BRAIN_API_SECRET to enable Expenses.
        </p>
      </div>
    );
  }

  const [{ expenses, total }, rules] = await Promise.all([
    fetchExpenses(auth),
    fetchRules(auth),
  ]);

  return (
    <ExpensesClient
      initialExpenses={expenses}
      initialTotal={total}
      rules={rules}
    />
  );
}
