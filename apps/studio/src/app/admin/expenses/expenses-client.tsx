"use client";

import { useState, useCallback, useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Plus, Search, FileDown } from "lucide-react";
import { toast } from "sonner";
import type { Expense, ExpenseStatus, ExpenseRoutingRules } from "@/types/expenses";
import { formatCents } from "@/types/expenses";
import { HqErrorState } from "@/components/admin/hq/HqErrorState";
import { ExpenseRow } from "./expense-row";
import { SubmitExpenseModal } from "./expense-modal";
import { RollupTab } from "./rollup-tab";
import { SettingsTab } from "./settings-tab";
import { ExpenseDetailDrawer } from "./ExpenseDetailDrawer";

type Tab = "inbox" | "approved" | "reimbursed" | "rejected" | "rollups" | "settings";

const TABS: { id: Tab; label: string }[] = [
  { id: "inbox", label: "Inbox" },
  { id: "approved", label: "Approved" },
  { id: "reimbursed", label: "Reimbursed" },
  { id: "rejected", label: "Rejected" },
  { id: "rollups", label: "Rollups" },
  { id: "settings", label: "Settings" },
];

const TAB_STATUSES: Partial<Record<Tab, ExpenseStatus[]>> = {
  inbox: ["pending", "flagged"],
  approved: ["approved"],
  reimbursed: ["reimbursed"],
  rejected: ["rejected"],
};

type Props = {
  initialExpenses: Expense[];
  initialTotal: number;
  rules: ExpenseRoutingRules | null;
};

export function ExpensesClient({ initialExpenses, initialTotal, rules }: Props) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const now = new Date();
  const [activeTab, setActiveTab] = useState<Tab>("inbox");
  const [expenses, setExpenses] = useState<Expense[]>(initialExpenses);
  const [total, setTotal] = useState(initialTotal);
  const [rulesState, setRulesState] = useState<ExpenseRoutingRules | null>(rules);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(initialTotal > initialExpenses.length);
  const [cursor, setCursor] = useState<string | null>(
    initialTotal > initialExpenses.length ? String(initialExpenses.length) : null
  );
  const [showSubmit, setShowSubmit] = useState(false);
  const [selectedExpense, setSelectedExpense] = useState<Expense | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  useEffect(() => {
    setRulesState(rules);
  }, [rules]);

  useEffect(() => {
    if (searchParams.get("log") !== "1") return;
    setShowSubmit(true);
    router.replace(pathname, { scroll: false });
  }, [searchParams, router, pathname]);

  const tabStatuses = TAB_STATUSES[activeTab];

  const fetchExpenses = useCallback(
    async (tab: Tab, q: string, append = false) => {
      const statuses = TAB_STATUSES[tab];
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (statuses && statuses.length === 1) params.set("status", statuses[0]);
        if (q) params.set("search", q);
        if (append && cursor) params.set("cursor", cursor);
        params.set("limit", "50");

        const res = await fetch(`/api/admin/expenses?${params.toString()}`);
        const json = (await res.json().catch(() => ({}))) as {
          success?: boolean;
          error?: string;
          data?: { items: Expense[]; total: number; has_more?: boolean; next_cursor?: string | null };
        };
        if (!res.ok || !json.success || !json.data) {
          const msg =
            json.error ??
            (!res.ok ? `Could not load expenses (${res.status})` : "Brain returned an error for expenses.");
          setListError(msg);
          toast.error("Expenses list failed to load");
          return;
        }
        setListError(null);

        const page = json.data;
        if (append) {
          setExpenses((prev) => [...prev, ...page.items]);
        } else {
          setExpenses(page.items);
        }
        setTotal(page.total);
        setHasMore(Boolean(page.has_more));
        setCursor(page.next_cursor ?? null);
      } finally {
        setLoading(false);
      }
    },
    [cursor]
  );

  function handleTabChange(tab: Tab) {
    setActiveTab(tab);
    setCursor(null);
    void fetchExpenses(tab, search);
  }

  function handleSearch(q: string) {
    setSearch(q);
    setCursor(null);
    void fetchExpenses(activeTab, q);
  }

  function handleExpenseUpdated(updated: Expense) {
    setExpenses((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
    setSelectedExpense(updated);
  }

  // Inbox uses multiple statuses (`pending` + `flagged`). We only send `status` when the tab
  // maps to exactly one status; for inbox we omit it and Brain returns a combined page, then
  // we filter client-side to the tab’s statuses. The API `total` is for that unfiltered page,
  // so with multi-status tabs it can exceed the number of visible rows after filtering — use
  // `total` as a server-reported page total / upper bound, not an exact match for filtered rows.

  const visibleExpenses =
    tabStatuses && tabStatuses.length > 1
      ? expenses.filter((e) => tabStatuses.includes(e.status))
      : expenses;

  const threshold = rulesState?.auto_approve_threshold_cents ?? 0;
  const thresholdLabel =
    threshold === 0
      ? "all manual submissions route for approval"
      : `auto-approve up to ${formatCents(threshold)}`;

  return (
    <>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-zinc-100">Expenses</h1>
            <p className="mt-0.5 text-xs text-zinc-500">
              Current routing: {thresholdLabel}
              {activeTab !== "settings" && (
                <button
                  type="button"
                  onClick={() => setActiveTab("settings")}
                  className="ml-1 text-zinc-400 underline-offset-2 hover:text-zinc-200 hover:underline"
                >
                  Edit in Settings →
                </button>
              )}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowSubmit(true)}
            className="flex items-center gap-1.5 rounded-lg bg-zinc-100 px-3 py-2 text-sm font-medium text-zinc-900 transition hover:bg-white"
          >
            <Plus className="h-4 w-4" />
            Submit expense
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 overflow-x-auto border-b border-zinc-800 pb-0">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => handleTabChange(tab.id)}
              className={`shrink-0 border-b-2 px-4 py-2.5 text-sm font-medium transition ${
                activeTab === tab.id
                  ? "border-zinc-300 text-zinc-100"
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "rollups" ? (
          <RollupTab initialYear={now.getFullYear()} initialMonth={now.getMonth() + 1} />
        ) : activeTab === "settings" ? (
          <SettingsTab rules={rulesState} onRulesSaved={(r) => setRulesState(r)} />
        ) : (
          <div className="space-y-3">
            {listError ? (
              <HqErrorState
                title="Could not load expenses"
                description="Distinct from an empty inbox: Brain or Studio returned an error. Check BRAIN_API_* env and network, then retry."
                error={listError}
                onRetry={() => void fetchExpenses(activeTab, search)}
              />
            ) : null}
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <input
                type="search"
                placeholder="Search vendor or notes…"
                value={search}
                onChange={(e) => handleSearch(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 py-2 pl-9 pr-4 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none"
              />
            </div>

            {/* Stats */}
            <div className="flex items-center justify-between text-xs text-zinc-500">
              <span>
                {total === 0 ? "No expenses" : `${total} expense${total !== 1 ? "s" : ""}`}
              </span>
              <a
                href={`/api/admin/expenses/export.csv${tabStatuses?.length === 1 ? `?status=${tabStatuses[0]}` : ""}`}
                download="expenses.csv"
                className="flex items-center gap-1 hover:text-zinc-300"
              >
                <FileDown className="h-3.5 w-3.5" />
                Export CSV
              </a>
            </div>

            {/* List */}
            {loading && visibleExpenses.length === 0 && !listError ? (
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-8 text-center">
                <p className="text-sm text-zinc-500">Loading…</p>
              </div>
            ) : visibleExpenses.length === 0 && !listError ? (
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-10 text-center">
                <p className="text-sm font-medium text-zinc-400">No expenses here</p>
                <p className="mt-1 text-xs text-zinc-600">
                  {activeTab === "inbox"
                    ? "New submissions appear here."
                    : `No ${activeTab} expenses.`}
                </p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {visibleExpenses.map((expense) => (
                  <ExpenseRow
                    key={expense.id}
                    expense={expense}
                    onClick={() => setSelectedExpense(expense)}
                  />
                ))}
              </div>
            )}

            {hasMore ? (
              <button
                type="button"
                onClick={() => fetchExpenses(activeTab, search, true)}
                disabled={loading}
                className="w-full rounded-lg border border-zinc-800 py-2 text-sm text-zinc-500 transition hover:border-zinc-600 hover:text-zinc-300 disabled:opacity-50"
              >
                {loading ? "Loading…" : "Load more"}
              </button>
            ) : null}
          </div>
        )}
      </div>

      {showSubmit ? (
        <SubmitExpenseModal
          onClose={() => setShowSubmit(false)}
          onSuccess={(expense) => {
            setExpenses((prev) => [expense, ...prev]);
            setTotal((t) => t + 1);
            setShowSubmit(false);
          }}
        />
      ) : null}

      {selectedExpense ? (
        <ExpenseDetailDrawer
          expense={selectedExpense}
          onClose={() => setSelectedExpense(null)}
          onUpdated={handleExpenseUpdated}
        />
      ) : null}
    </>
  );
}
