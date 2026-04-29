/** TypeScript mirror of apis/brain/app/schemas/expenses.py — WS-69 PR N */

export type ExpenseCategory =
  | "infra"
  | "ai"
  | "contractors"
  | "tools"
  | "legal"
  | "tax"
  | "misc"
  | "domains"
  | "ops";

export type ExpenseStatus =
  | "pending"
  | "approved"
  | "reimbursed"
  | "flagged"
  | "rejected";

export type ExpenseSource =
  | "manual"
  | "gmail"
  | "stripe"
  | "plaid"
  | "subscription"
  | "imported";

export interface ReceiptAttachment {
  filename: string;
  mime_type: string;
  size_bytes: number;
  stored_path: string;
}

export interface Expense {
  id: string;
  vendor: string;
  amount_cents: number;
  currency: string;
  category: ExpenseCategory;
  status: ExpenseStatus;
  source: ExpenseSource;
  classified_by: string;
  occurred_at: string; // YYYY-MM-DD
  submitted_at: string; // ISO datetime
  approved_at: string | null;
  reimbursed_at: string | null;
  notes: string;
  receipt: ReceiptAttachment | null;
  tags: string[];
  conversation_id: string | null;
}

export interface ExpensesListPage {
  items: Expense[];
  total: number;
  next_cursor: string | null;
  has_more: boolean;
}

export interface CategoryTotal {
  category: ExpenseCategory;
  amount_cents: number;
  count: number;
}

export interface MonthlyRollup {
  year: number;
  month: number;
  total_cents: number;
  approved_cents: number;
  pending_cents: number;
  flagged_cents: number;
  category_breakdown: CategoryTotal[];
  vendor_count: number;
  expense_count: number;
  prior_3mo_avg_cents: number;
  pct_vs_prior_avg: number | null;
}

export interface QuarterlyRollup {
  year: number;
  quarter: number;
  total_cents: number;
  approved_cents: number;
  category_breakdown: CategoryTotal[];
  expense_count: number;
  months: MonthlyRollup[];
}

export interface ExpenseRoutingRules {
  auto_approve_threshold_cents: number;
  auto_approve_categories: ExpenseCategory[];
  always_review_categories: ExpenseCategory[];
  flag_amount_cents_above: number;
  founder_card_default_source: string;
  subscription_skip_approval: boolean;
  updated_at: string;
  updated_by: string;
  history: Record<string, unknown>[];
}

// Helpers
export const CATEGORY_LABELS: Record<ExpenseCategory, string> = {
  infra: "Infrastructure",
  ai: "AI / ML",
  contractors: "Contractors",
  tools: "Tools",
  legal: "Legal",
  tax: "Tax",
  misc: "Misc",
  domains: "Domains",
  ops: "Operations",
};

export const STATUS_LABELS: Record<ExpenseStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  reimbursed: "Reimbursed",
  flagged: "Flagged",
  rejected: "Rejected",
};

export function formatCents(cents: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(cents / 100);
}
