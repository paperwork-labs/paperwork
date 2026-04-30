"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Flag, Loader2, XCircle } from "lucide-react";
import type { Conversation } from "@/types/conversations";
import type { Expense, ExpenseCategory } from "@/types/expenses";
import { CATEGORY_LABELS, formatCents } from "@/types/expenses";

export type ExpenseConversationAction =
  | "approve"
  | "approve-change-category"
  | "flag"
  | "reject";

type Props = {
  conversationId: string;
  expenseId: string;
  conversation: Conversation;
  onResolved: (data: { expense: Expense; conversation: Conversation }) => void;
};

export function ExpenseConversationCard({
  conversationId,
  expenseId,
  conversation,
  onResolved,
}: Props) {
  const [expense, setExpense] = useState<Expense | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<ExpenseConversationAction | null>(null);
  const [showCategory, setShowCategory] = useState(false);
  const [newCategory, setNewCategory] = useState<ExpenseCategory>("misc");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/expenses/${expenseId}`);
      const json = await res.json();
      if (!res.ok || !json.success) throw new Error(json.error ?? "Failed to load expense");
      setExpense(json.data as Expense);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, [expenseId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function resolve(
    action: ExpenseConversationAction,
    extra?: { new_category?: ExpenseCategory },
  ) {
    setActing(action);
    setError(null);
    try {
      const body: Record<string, unknown> = { expense_action: action };
      if (action === "approve-change-category" && extra?.new_category) {
        body.new_category = extra.new_category;
      }
      const res = await fetch(`/api/admin/conversations/${conversationId}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const json = await res.json();
      if (!res.ok || !json.success) throw new Error(json.error ?? "Action failed");
      onResolved({
        expense: json.data.expense as Expense,
        conversation: json.data.conversation as Conversation,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setActing(null);
      setShowCategory(false);
    }
  }

  if (loading) {
    return (
      <div className="mb-4 flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-950/50 p-4 text-sm text-zinc-500">
        <Loader2 className="h-4 w-4 motion-safe:animate-spin" />
        Loading expense…
      </div>
    );
  }

  if (error && !expense) {
    return (
      <div className="mb-4 rounded-xl border border-red-900/40 bg-red-950/30 p-4 text-sm text-red-300">
        {error}
      </div>
    );
  }

  if (!expense) return null;

  const resolved = conversation.status === "resolved";

  return (
    <div
      data-testid="expense-conversation-card"
      className="mb-4 rounded-xl border border-zinc-700/80 bg-zinc-950/60 p-4"
    >
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Linked expense</p>
      <div className="mt-2 flex gap-4">
        <div className="flex h-16 w-16 items-center justify-center rounded bg-zinc-800 text-[10px] text-zinc-500">
          {expense.receipt ? expense.receipt.filename : "No receipt"}
        </div>
        <div className="min-w-0 flex-1 text-sm">
          <p className="font-semibold text-zinc-100">{expense.vendor}</p>
          <p className="text-zinc-300">{formatCents(expense.amount_cents, expense.currency)}</p>
          <p className="text-xs text-zinc-500">
            Category: <span className="text-zinc-300">{CATEGORY_LABELS[expense.category]}</span> ·
            Classified by {expense.classified_by}
          </p>
        </div>
      </div>

      {error ? <p className="mt-2 text-xs text-red-400">{error}</p> : null}

      {showCategory ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value as ExpenseCategory)}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-200"
          >
            {(Object.keys(CATEGORY_LABELS) as ExpenseCategory[]).map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABELS[c]}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!!acting}
            onClick={() => void resolve("approve-change-category", { new_category: newCategory })}
            className="rounded bg-emerald-500/20 px-3 py-1 text-xs text-emerald-200"
          >
            Confirm category
          </button>
          <button type="button" onClick={() => setShowCategory(false)} className="text-xs text-zinc-500">
            Cancel
          </button>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={resolved || !!acting}
          data-testid="expense-action-approve"
          onClick={() => void resolve("approve")}
          className="inline-flex items-center gap-1 rounded-lg bg-emerald-500/15 px-3 py-1.5 text-xs font-medium text-emerald-200 ring-1 ring-emerald-500/30 disabled:opacity-40"
        >
          {acting === "approve" ? <Loader2 className="h-3 w-3 motion-safe:animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
          Approve
        </button>
        <button
          type="button"
          disabled={resolved || !!acting}
          data-testid="expense-action-approve-change"
          onClick={() => {
            setNewCategory(expense.category);
            setShowCategory(true);
          }}
          className="rounded-lg bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-200 ring-1 ring-sky-500/30 disabled:opacity-40"
        >
          Approve & change category
        </button>
        <button
          type="button"
          disabled={resolved || !!acting}
          data-testid="expense-action-flag"
          onClick={() => void resolve("flag")}
          className="inline-flex items-center gap-1 rounded-lg bg-amber-500/15 px-3 py-1.5 text-xs font-medium text-amber-200 ring-1 ring-amber-500/30 disabled:opacity-40"
        >
          {acting === "flag" ? <Loader2 className="h-3 w-3 motion-safe:animate-spin" /> : <Flag className="h-3 w-3" />}
          Flag
        </button>
        <button
          type="button"
          disabled={resolved || !!acting}
          data-testid="expense-action-reject"
          onClick={() => void resolve("reject")}
          className="inline-flex items-center gap-1 rounded-lg bg-red-500/15 px-3 py-1.5 text-xs font-medium text-red-200 ring-1 ring-red-500/30 disabled:opacity-40"
        >
          {acting === "reject" ? <Loader2 className="h-3 w-3 motion-safe:animate-spin" /> : <XCircle className="h-3 w-3" />}
          Reject
        </button>
      </div>
    </div>
  );
}
