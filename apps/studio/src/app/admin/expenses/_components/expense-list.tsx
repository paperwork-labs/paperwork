"use client";

import { useState, useCallback } from "react";
import { CheckCircle2, XCircle, Banknote, ChevronRight, ChevronLeft, Paperclip } from "lucide-react";
import { Badge } from "@paperwork-labs/ui";
import type {
  Expense,
  ExpenseListResult,
} from "@/lib/expenses";
import {
  formatCents,
  CATEGORY_LABELS,
  STATUS_COLORS,
} from "@/lib/expenses";

type Props = {
  initialData: ExpenseListResult | null;
  filter: string;
  showActions?: boolean;
};

async function fetchPage(filter: string, cursor?: string): Promise<ExpenseListResult | null> {
  const params = new URLSearchParams({ filter, limit: "50" });
  if (cursor) params.set("cursor", cursor);
  try {
    const res = await fetch(`/api/admin/expenses?${params}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json() as Promise<ExpenseListResult>;
  } catch {
    return null;
  }
}

async function doAction(
  id: string,
  action: "approve" | "reject" | "reimburse",
  actor = "founder",
) {
  await fetch(`/api/admin/expenses/${id}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor }),
  });
}

function StatusBadge({ status }: { status: string }) {
  const classes = STATUS_COLORS[status as keyof typeof STATUS_COLORS] ??
    "bg-zinc-700/50 text-zinc-300 border border-zinc-600";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${classes}`}>
      {status}
    </span>
  );
}

function ExpenseRow({
  expense,
  showActions,
  onAction,
}: {
  expense: Expense;
  showActions: boolean;
  onAction: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);

  const handle = useCallback(
    async (action: "approve" | "reject" | "reimburse") => {
      setLoading(action);
      await doAction(expense.id, action);
      setLoading(null);
      onAction();
    },
    [expense.id, onAction],
  );

  return (
    <>
      <tr
        className="cursor-pointer hover:bg-zinc-900/30 transition-colors"
        onClick={() => setExpanded((p) => !p)}
        aria-expanded={expanded}
      >
        <td className="px-3 py-2.5">
          <span className="font-medium text-zinc-200">{expense.vendor}</span>
        </td>
        <td className="px-3 py-2.5 text-right font-mono text-zinc-100">
          {formatCents(expense.amount_cents, expense.currency)}
        </td>
        <td className="px-3 py-2.5">
          <Badge variant="outline" className="text-[10px] text-zinc-400 border-zinc-700">
            {CATEGORY_LABELS[expense.category] ?? expense.category}
          </Badge>
        </td>
        <td className="px-3 py-2.5">
          <StatusBadge status={expense.status} />
        </td>
        <td className="px-3 py-2.5 text-xs text-zinc-500">
          {new Date(expense.submitted_at).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </td>
        <td className="px-3 py-2.5">
          {expense.attachments.length > 0 && (
            <Paperclip className="h-3 w-3 text-zinc-500" aria-label="Has receipt" />
          )}
        </td>
        <td className="px-3 py-2.5 text-right">
          <ChevronRight
            className={`h-4 w-4 text-zinc-600 transition-transform ${expanded ? "rotate-90" : ""}`}
          />
        </td>
      </tr>
      {expanded && (
        <tr className="bg-zinc-900/20">
          <td colSpan={7} className="px-4 py-3">
            <div className="space-y-2 text-sm">
              {expense.notes && (
                <p className="text-zinc-400">
                  <span className="font-semibold text-zinc-500">Notes: </span>
                  {expense.notes}
                </p>
              )}
              {expense.tags.length > 0 && (
                <p className="text-zinc-500 text-xs">
                  Tags: {expense.tags.join(", ")}
                </p>
              )}
              {expense.tax_deductible_pct !== null && (
                <p className="text-zinc-500 text-xs">
                  Tax deductible: {expense.tax_deductible_pct}%
                  {expense.tax_category_note ? ` — ${expense.tax_category_note}` : ""}
                </p>
              )}
              {expense.attachments.map((a) => (
                <a
                  key={a.sha256}
                  href={`/api/admin/expenses/attachment/${a.sha256}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-sky-400 hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Paperclip className="h-3 w-3" />
                  {a.mime} ({Math.round(a.size_bytes / 1024)} KB)
                </a>
              ))}
              {showActions && (expense.status === "pending" || expense.status === "flagged") && (
                <div className="flex gap-2 pt-1">
                  <button
                    type="button"
                    disabled={loading !== null}
                    onClick={(e) => { e.stopPropagation(); void handle("approve"); }}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/15 px-3 py-1.5 text-xs font-medium text-emerald-200 ring-1 ring-emerald-500/30 transition hover:bg-emerald-500/25 disabled:opacity-50"
                    aria-label="Approve expense"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {loading === "approve" ? "Approving…" : "Approve"}
                  </button>
                  <button
                    type="button"
                    disabled={loading !== null}
                    onClick={(e) => { e.stopPropagation(); void handle("reject"); }}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-red-500/15 px-3 py-1.5 text-xs font-medium text-red-200 ring-1 ring-red-500/30 transition hover:bg-red-500/25 disabled:opacity-50"
                    aria-label="Reject expense"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    {loading === "reject" ? "Rejecting…" : "Reject"}
                  </button>
                </div>
              )}
              {showActions && expense.status === "approved" && (
                <div className="flex gap-2 pt-1">
                  <button
                    type="button"
                    disabled={loading !== null}
                    onClick={(e) => { e.stopPropagation(); void handle("reimburse"); }}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-blue-500/15 px-3 py-1.5 text-xs font-medium text-blue-200 ring-1 ring-blue-500/30 transition hover:bg-blue-500/25 disabled:opacity-50"
                    aria-label="Mark reimbursed"
                  >
                    <Banknote className="h-3.5 w-3.5" />
                    {loading === "reimburse" ? "Marking…" : "Mark reimbursed"}
                  </button>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function ExpenseList({ initialData, filter, showActions = false }: Props) {
  const [data, setData] = useState<ExpenseListResult | null>(initialData);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    const fresh = await fetchPage(filter, cursor ?? undefined);
    setData(fresh);
    setLoading(false);
  }, [filter, cursor]);

  const goNext = useCallback(async () => {
    if (!data?.next_cursor) return;
    const newCursor = data.next_cursor;
    setCursorHistory((h) => [...h, cursor ?? ""]);
    setCursor(newCursor);
    setLoading(true);
    const next = await fetchPage(filter, newCursor);
    setData(next);
    setLoading(false);
  }, [data, cursor, filter]);

  const goPrev = useCallback(async () => {
    const hist = [...cursorHistory];
    const prev = hist.pop();
    setCursorHistory(hist);
    const prevCursor = prev || undefined;
    setCursor(prevCursor ?? null);
    setLoading(true);
    const page = await fetchPage(filter, prevCursor);
    setData(page);
    setLoading(false);
  }, [cursorHistory, filter]);

  if (data === null) {
    return (
      <p className="py-8 text-center text-sm text-zinc-500">
        Brain unavailable — expenses data not loaded.
      </p>
    );
  }

  const items = data.items;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-zinc-500">
          {data.total} expense{data.total !== 1 ? "s" : ""} {filter !== "all" ? `(${filter})` : ""}
        </p>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="text-xs text-zinc-500 hover:text-zinc-300 transition disabled:opacity-50"
          aria-label="Refresh expenses"
        >
          {loading ? "Refreshing…" : "↻ Refresh"}
        </button>
      </div>

      {items.length === 0 ? (
        <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 py-12 text-center">
          <p className="text-sm text-zinc-500">No expenses in this view.</p>
          {filter === "pending" && (
            <p className="mt-1 text-xs text-zinc-600">
              All clear — no pending approvals.
            </p>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
          <table className="w-full min-w-[640px] text-left text-sm" role="table" aria-label="Expense list">
            <thead className="border-b border-zinc-800 bg-zinc-900/50">
              <tr className="text-xs uppercase tracking-wide text-zinc-500">
                <th className="px-3 py-2">Vendor</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2">Category</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Submitted</th>
                <th className="px-3 py-2">Receipt</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/80 text-zinc-300">
              {items.map((expense) => (
                <ExpenseRow
                  key={expense.id}
                  expense={expense}
                  showActions={showActions}
                  onAction={() => void refresh()}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(cursorHistory.length > 0 || data.next_cursor) && (
        <div className="flex items-center justify-end gap-2">
          {cursorHistory.length > 0 && (
            <button
              type="button"
              onClick={() => void goPrev()}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-50"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>
          )}
          {data.next_cursor && (
            <button
              type="button"
              onClick={() => void goNext()}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-50"
              aria-label="Next page"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
