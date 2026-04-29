/**
 * Typed Brain API client for expense tracking (WS-69 PR N).
 * Server-side only — uses BRAIN_API_URL + BRAIN_API_SECRET.
 */

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export type ExpenseStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "reimbursed"
  | "flagged";

export type ExpenseCategory =
  | "infra"
  | "ai"
  | "contractors"
  | "tools"
  | "legal"
  | "tax"
  | "domains"
  | "ops"
  | "misc";

export type ExpenseAttachment = {
  kind: "receipt";
  url: string;
  mime: string;
  sha256: string;
  size_bytes: number;
};

export type Expense = {
  id: string;
  amount_cents: number;
  currency: string;
  vendor: string;
  category: ExpenseCategory;
  tags: string[];
  status: ExpenseStatus;
  submitted_at: string;
  approved_at: string | null;
  reimbursed_at: string | null;
  attachments: ExpenseAttachment[];
  notes: string;
  submitted_by: string;
  tax_deductible_pct: number | null;
  tax_category_note: string | null;
  vendor_id: string | null;
  invoice_id: string | null;
  gmail_message_id: string | null;
  conversation_id: string | null;
};

export type ExpenseListResult = {
  items: Expense[];
  next_cursor: string | null;
  total: number;
};

export type ExpenseRollupCategory = {
  category: ExpenseCategory;
  total_cents: number;
  count: number;
};

export type ExpenseRollup = {
  period: string;
  total_cents: number;
  count: number;
  by_category: ExpenseRollupCategory[];
};

export type ExpenseRoutingRules = {
  auto_approve_threshold_cents: number;
  auto_approve_categories: ExpenseCategory[];
  flagged_threshold_cents: number;
  flagged_categories: ExpenseCategory[];
};

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

function authHeaders(secret: string): Record<string, string> {
  return {
    "X-Brain-Secret": secret,
    "Content-Type": "application/json",
  };
}

export async function fetchExpenses(
  filter: string = "pending",
  cursor?: string,
  limit = 50,
): Promise<ExpenseListResult | null> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return null;
  const params = new URLSearchParams({ filter, limit: String(limit) });
  if (cursor) params.set("cursor", cursor);
  try {
    const res = await fetch(
      `${auth.root}/admin/expenses?${params}`,
      { headers: authHeaders(auth.secret), cache: "no-store" },
    );
    if (!res.ok) return null;
    return res.json() as Promise<ExpenseListResult>;
  } catch {
    return null;
  }
}

export async function fetchExpense(id: string): Promise<Expense | null> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return null;
  try {
    const res = await fetch(
      `${auth.root}/admin/expenses/${id}`,
      { headers: authHeaders(auth.secret), cache: "no-store" },
    );
    if (!res.ok) return null;
    return res.json() as Promise<Expense>;
  } catch {
    return null;
  }
}

export async function fetchPendingCount(): Promise<number> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return 0;
  try {
    const res = await fetch(
      `${auth.root}/admin/expenses/pending-count`,
      { headers: authHeaders(auth.secret), cache: "no-store" },
    );
    if (!res.ok) return 0;
    const data = (await res.json()) as { count: number };
    return data.count;
  } catch {
    return 0;
  }
}

export async function fetchRollup(
  period: "month" | "quarter",
  year: number,
  month: number,
): Promise<ExpenseRollup | null> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return null;
  const params = new URLSearchParams({
    period,
    year: String(year),
    month: String(month),
  });
  try {
    const res = await fetch(
      `${auth.root}/admin/expenses/rollup?${params}`,
      { headers: authHeaders(auth.secret), cache: "no-store" },
    );
    if (!res.ok) return null;
    return res.json() as Promise<ExpenseRollup>;
  } catch {
    return null;
  }
}

export async function fetchRoutingRules(): Promise<ExpenseRoutingRules | null> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return null;
  try {
    const res = await fetch(
      `${auth.root}/admin/expense-routing-rules`,
      { headers: authHeaders(auth.secret), cache: "no-store" },
    );
    if (!res.ok) return null;
    return res.json() as Promise<ExpenseRoutingRules>;
  } catch {
    return null;
  }
}

export async function approveExpense(
  id: string,
  actor: string,
): Promise<Expense | null> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return null;
  try {
    const res = await fetch(`${auth.root}/admin/expenses/${id}/approve`, {
      method: "POST",
      headers: authHeaders(auth.secret),
      body: JSON.stringify({ actor }),
    });
    if (!res.ok) return null;
    return res.json() as Promise<Expense>;
  } catch {
    return null;
  }
}

export async function rejectExpense(
  id: string,
  actor: string,
  reason = "",
): Promise<Expense | null> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return null;
  try {
    const res = await fetch(`${auth.root}/admin/expenses/${id}/reject`, {
      method: "POST",
      headers: authHeaders(auth.secret),
      body: JSON.stringify({ actor, reason }),
    });
    if (!res.ok) return null;
    return res.json() as Promise<Expense>;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Format helpers (shared between server and client)
// ---------------------------------------------------------------------------

export function formatCents(cents: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(cents / 100);
}

export const CATEGORY_LABELS: Record<ExpenseCategory, string> = {
  infra: "Infrastructure",
  ai: "AI / ML",
  contractors: "Contractors",
  tools: "Tools",
  legal: "Legal",
  tax: "Tax",
  domains: "Domains",
  ops: "Operations",
  misc: "Misc",
};

export const STATUS_COLORS: Record<ExpenseStatus, string> = {
  pending: "bg-amber-500/20 text-amber-200 border border-amber-500/30",
  approved: "bg-emerald-500/20 text-emerald-200 border border-emerald-500/30",
  rejected: "bg-red-500/20 text-red-200 border border-red-500/30",
  reimbursed: "bg-blue-500/20 text-blue-200 border border-blue-500/30",
  flagged: "bg-orange-500/20 text-orange-200 border border-orange-500/30",
};
