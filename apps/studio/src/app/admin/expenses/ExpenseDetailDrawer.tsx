"use client";

import { useState } from "react";
import { X, CheckCircle, XCircle, DollarSign, Flag, Loader2, AlertCircle } from "lucide-react";
import type { Expense, ExpenseStatus } from "@/types/expenses";
import {
  CATEGORY_LABELS,
  STATUS_LABELS,
  formatCents,
} from "@/types/expenses";

type Props = {
  expense: Expense;
  onClose: () => void;
  onUpdated: (updated: Expense) => void;
};

const STATUS_BADGE: Record<ExpenseStatus, string> = {
  pending: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  approved: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  reimbursed: "bg-blue-500/15 text-blue-300 ring-blue-500/30",
  flagged: "bg-red-500/15 text-red-300 ring-red-500/30",
  rejected: "bg-zinc-500/15 text-zinc-400 ring-zinc-500/30",
};

const TERMINAL: ExpenseStatus[] = ["reimbursed", "rejected"];

export function ExpenseDetailDrawer({ expense, onClose, onUpdated }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isTerminal = TERMINAL.includes(expense.status);

  async function transition(status: ExpenseStatus) {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/expenses/${expense.id}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, notes: "" }),
      });
      const json = await res.json();
      if (!res.ok || !json.success) throw new Error(json.error || "Failed");
      onUpdated(json.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end"
      aria-modal="true"
      role="dialog"
      aria-labelledby="drawer-title"
    >
      {/* Backdrop */}
      <button
        type="button"
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-label="Close drawer"
      />

      {/* Drawer */}
      <div className="relative z-50 flex h-full w-full max-w-md flex-col bg-zinc-950 shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <h2 id="drawer-title" className="text-base font-semibold text-zinc-100">
            Expense detail
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {error ? (
            <div className="flex items-center gap-2 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          ) : null}

          {/* Amount + vendor */}
          <div>
            <p className="text-3xl font-bold tabular-nums text-zinc-100">
              {formatCents(expense.amount_cents, expense.currency)}
            </p>
            <p className="mt-1 text-base text-zinc-300">{expense.vendor}</p>
          </div>

          {/* Status badge */}
          <div>
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${STATUS_BADGE[expense.status]}`}
            >
              {STATUS_LABELS[expense.status]}
            </span>
          </div>

          {/* Metadata */}
          <dl className="divide-y divide-zinc-800 rounded-xl border border-zinc-800 text-sm">
            <DetailRow label="Category" value={CATEGORY_LABELS[expense.category]} />
            <DetailRow label="Date" value={expense.occurred_at} />
            <DetailRow label="Source" value={expense.source} />
            <DetailRow label="Classified by" value={expense.classified_by} />
            {expense.notes ? <DetailRow label="Notes" value={expense.notes} /> : null}
            {expense.approved_at ? (
              <DetailRow label="Approved at" value={expense.approved_at.slice(0, 10)} />
            ) : null}
            {expense.reimbursed_at ? (
              <DetailRow label="Reimbursed at" value={expense.reimbursed_at.slice(0, 10)} />
            ) : null}
          </dl>

          {/* Receipt */}
          {expense.receipt ? (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-3">
              <p className="text-xs font-medium text-zinc-500">Receipt</p>
              <p className="mt-1 text-sm text-zinc-300">{expense.receipt.filename}</p>
              <p className="text-xs text-zinc-600">
                {(expense.receipt.size_bytes / 1024).toFixed(1)} KB · {expense.receipt.mime_type}
              </p>
            </div>
          ) : null}

          {/* Conversation stub (PR O wires) */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/20 px-4 py-3">
            <p className="text-xs font-medium text-zinc-500">Approval conversation</p>
            <p className="mt-1 text-xs text-zinc-600">
              {expense.conversation_id
                ? `Conversation ID: ${expense.conversation_id}`
                : "No conversation linked yet — PR O wires Expenses ↔ Conversations."}
            </p>
          </div>
        </div>

        {/* Actions */}
        {!isTerminal && (
          <div className="border-t border-zinc-800 p-5">
            <div className="grid grid-cols-2 gap-2">
              {expense.status !== "approved" && expense.status !== "reimbursed" ? (
                <ActionButton
                  label="Approve"
                  icon={<CheckCircle className="h-4 w-4" />}
                  onClick={() => transition("approved")}
                  loading={loading}
                  variant="success"
                />
              ) : null}
              {expense.status === "approved" ? (
                <ActionButton
                  label="Reimburse"
                  icon={<DollarSign className="h-4 w-4" />}
                  onClick={() => transition("reimbursed")}
                  loading={loading}
                  variant="success"
                />
              ) : null}
              {expense.status !== "flagged" ? (
                <ActionButton
                  label="Flag"
                  icon={<Flag className="h-4 w-4" />}
                  onClick={() => transition("flagged")}
                  loading={loading}
                  variant="warning"
                />
              ) : null}
              <ActionButton
                label="Reject"
                icon={<XCircle className="h-4 w-4" />}
                onClick={() => transition("rejected")}
                loading={loading}
                variant="danger"
              />
            </div>
          </div>
        )}
        {isTerminal ? (
          <div className="border-t border-zinc-800 p-5">
            <p className="text-center text-xs text-zinc-600">
              This expense is in a terminal state ({expense.status}) and cannot be changed.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 px-4 py-2.5">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="text-right text-zinc-300">{value}</dd>
    </div>
  );
}

function ActionButton({
  label,
  icon,
  onClick,
  loading,
  variant,
}: {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  loading: boolean;
  variant: "success" | "warning" | "danger" | "default";
}) {
  const styles: Record<string, string> = {
    success: "bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 ring-emerald-500/20",
    warning: "bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 ring-amber-500/20",
    danger: "bg-red-500/10 text-red-300 hover:bg-red-500/20 ring-red-500/20",
    default: "bg-zinc-800 text-zinc-300 hover:bg-zinc-700 ring-zinc-700",
  };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className={`flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium ring-1 transition disabled:opacity-50 ${styles[variant]}`}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : icon}
      {label}
    </button>
  );
}
