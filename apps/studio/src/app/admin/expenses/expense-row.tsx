"use client";

import { Receipt, ChevronRight } from "lucide-react";
import type { Expense } from "@/types/expenses";
import { CATEGORY_LABELS, STATUS_LABELS, formatCents } from "@/types/expenses";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  approved: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  reimbursed: "bg-blue-500/15 text-blue-300 ring-blue-500/30",
  flagged: "bg-red-500/15 text-red-300 ring-red-500/30",
  rejected: "bg-zinc-500/15 text-zinc-400 ring-zinc-500/30",
};

const CATEGORY_STYLES: Record<string, string> = {
  infra: "bg-sky-500/10 text-sky-300",
  ai: "bg-violet-500/10 text-violet-300",
  contractors: "bg-orange-500/10 text-orange-300",
  tools: "bg-teal-500/10 text-teal-300",
  legal: "bg-rose-500/10 text-rose-300",
  tax: "bg-rose-500/10 text-rose-300",
  misc: "bg-zinc-500/10 text-zinc-400",
  domains: "bg-cyan-500/10 text-cyan-300",
  ops: "bg-indigo-500/10 text-indigo-300",
};

type Props = {
  expense: Expense;
  onClick: () => void;
};

export function ExpenseRow({ expense, onClick }: Props) {
  const date = expense.occurred_at;
  const statusStyle = STATUS_STYLES[expense.status] ?? STATUS_STYLES.pending;
  const catStyle = CATEGORY_STYLES[expense.category] ?? CATEGORY_STYLES.misc;

  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full items-center gap-4 rounded-lg border border-zinc-800/60 bg-zinc-900/40 px-4 py-3 text-left transition hover:border-zinc-700 hover:bg-zinc-900"
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="hidden w-24 shrink-0 text-xs text-zinc-500 sm:block">{date}</div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-zinc-100">{expense.vendor}</p>
          {expense.notes ? (
            <p className="truncate text-xs text-zinc-500">{expense.notes}</p>
          ) : null}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <span
          className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${catStyle}`}
        >
          {CATEGORY_LABELS[expense.category]}
        </span>
        <span
          className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ring-1 ${statusStyle}`}
        >
          {STATUS_LABELS[expense.status]}
        </span>
        {expense.receipt ? (
          <Receipt className="h-3.5 w-3.5 text-zinc-500" aria-label="Has receipt" />
        ) : null}
        <span className="w-20 text-right text-sm font-semibold tabular-nums text-zinc-100">
          {formatCents(expense.amount_cents, expense.currency)}
        </span>
        <ChevronRight className="h-4 w-4 shrink-0 text-zinc-600 group-hover:text-zinc-400" />
      </div>
    </button>
  );
}
