import Link from "next/link";
import { ArrowLeft, MessageSquare } from "lucide-react";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import type { Expense } from "@/types/expenses";
import {
  CATEGORY_LABELS,
  STATUS_LABELS,
  formatCents,
} from "@/types/expenses";

export const dynamic = "force-dynamic";

async function fetchExpense(
  auth: { root: string; secret: string },
  id: string
): Promise<Expense | null> {
  try {
    const res = await fetch(`${auth.root}/admin/expenses/${id}`, {
      headers: { "X-Brain-Secret": auth.secret },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const json = await res.json();
    return json.success ? (json.data as Expense) : null;
  } catch {
    return null;
  }
}

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  approved: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  reimbursed: "bg-blue-500/15 text-blue-300 ring-blue-500/30",
  flagged: "bg-red-500/15 text-red-300 ring-red-500/30",
  rejected: "bg-zinc-500/15 text-zinc-400 ring-zinc-500/30",
};

type Props = {
  params: Promise<{ id: string }>;
};

export default async function ExpenseDetailPage({ params }: Props) {
  const { id } = await params;
  const auth = getBrainAdminFetchOptions();

  if (!auth.ok) {
    return (
      <div className="rounded-xl border border-red-900/40 bg-red-500/5 p-8 text-center">
        <p className="text-sm text-red-400">Brain API not configured.</p>
      </div>
    );
  }

  const expense = await fetchExpense(auth, id);

  if (!expense) {
    return (
      <div className="space-y-4">
        <BackLink />
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-10 text-center">
          <p className="text-sm font-medium text-zinc-400">Expense not found</p>
          <p className="mt-1 text-xs text-zinc-600">
            ID <code className="text-zinc-500">{id}</code> does not exist in the store.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <BackLink />

      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-3xl font-bold tabular-nums text-zinc-100">
              {formatCents(expense.amount_cents, expense.currency)}
            </p>
            <p className="mt-1 text-lg text-zinc-300">{expense.vendor}</p>
          </div>
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ring-1 ${STATUS_BADGE[expense.status] ?? ""}`}
          >
            {STATUS_LABELS[expense.status] ?? expense.status}
          </span>
        </div>

        <dl className="mt-6 divide-y divide-zinc-800 border-t border-zinc-800 text-sm">
          <Row label="Category" value={CATEGORY_LABELS[expense.category] ?? expense.category} />
          <Row label="Date" value={expense.occurred_at} />
          <Row label="Source" value={expense.source} />
          <Row label="Classified by" value={expense.classified_by} />
          {expense.notes ? <Row label="Notes" value={expense.notes} /> : null}
          {expense.approved_at ? (
            <Row label="Approved at" value={expense.approved_at.slice(0, 10)} />
          ) : null}
          {expense.reimbursed_at ? (
            <Row label="Reimbursed at" value={expense.reimbursed_at.slice(0, 10)} />
          ) : null}
          <Row label="Submitted at" value={expense.submitted_at.slice(0, 10)} />
          <Row label="ID" value={expense.id} />
        </dl>

        {expense.receipt ? (
          <div className="mt-4 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3">
            <p className="text-xs font-medium text-zinc-500">Receipt</p>
            <p className="mt-1 text-sm text-zinc-300">{expense.receipt.filename}</p>
            <p className="text-xs text-zinc-600">
              {(expense.receipt.size_bytes / 1024).toFixed(1)} KB · {expense.receipt.mime_type}
            </p>
          </div>
        ) : null}

        {/* Conversation stub — PR O wires this */}
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/20 px-4 py-3">
          <MessageSquare className="h-4 w-4 shrink-0 text-zinc-600" />
          <div>
            <p className="text-xs font-medium text-zinc-500">Approval conversation</p>
            {expense.conversation_id ? (
              <p className="text-xs text-zinc-400">
                Conversation: <code>{expense.conversation_id}</code>
              </p>
            ) : (
              <p className="text-xs text-zinc-600">
                No conversation linked — PR O wires Expenses ↔ Conversations.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/admin/expenses"
      className="inline-flex items-center gap-1.5 text-sm text-zinc-500 transition hover:text-zinc-300"
    >
      <ArrowLeft className="h-4 w-4" />
      Back to expenses
    </Link>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 py-2.5">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="text-right text-zinc-300">{value}</dd>
    </div>
  );
}
