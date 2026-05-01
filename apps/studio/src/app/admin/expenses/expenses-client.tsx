"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Plus, Search, FileDown } from "lucide-react";
import { toast } from "sonner";
import type { Expense, ExpenseStatus, ExpenseRoutingRules } from "@/types/expenses";
import { formatCents } from "@/types/expenses";
import { HqErrorState } from "@/components/admin/hq/HqErrorState";
import { TabbedPageShell, type StudioTabDef } from "@/components/layout/TabbedPageShellNext";
import { ExpenseRow } from "./expense-row";
import { SubmitExpenseModal } from "./expense-modal";
import { RollupTab } from "./rollup-tab";
import { SettingsTab } from "./settings-tab";
import { ExpenseDetailDrawer } from "./ExpenseDetailDrawer";

type Tab = "inbox" | "approved" | "reimbursed" | "rejected" | "rollups" | "settings";

type ListTabId = Exclude<Tab, "rollups" | "settings">;

const TABS: { id: Tab; label: string }[] = [
  { id: "inbox", label: "Inbox" },
  { id: "approved", label: "Approved" },
  { id: "reimbursed", label: "Reimbursed" },
  { id: "rejected", label: "Rejected" },
  { id: "rollups", label: "Rollups" },
  { id: "settings", label: "Settings" },
];

const TAB_IDS = new Set<string>(TABS.map((t) => t.id));

const TAB_STATUSES: Partial<Record<Tab, ExpenseStatus[]>> = {
  inbox: ["pending", "flagged"],
  approved: ["approved"],
  reimbursed: ["reimbursed"],
  rejected: ["rejected"],
};

function tabFromSearchParams(raw: string | null): Tab {
  if (raw != null && TAB_IDS.has(raw)) return raw as Tab;
  return "inbox";
}

type ExpensesListPanelProps = {
  tabId: ListTabId;
  expenses: Expense[];
  search: string;
  total: number;
  loading: boolean;
  hasMore: boolean;
  listError: string | null;
  onSearch: (q: string) => void;
  onRetry: () => void;
  onSelectExpense: (e: Expense) => void;
  onLoadMore: () => void;
};

function ExpensesListPanel({
  tabId,
  expenses,
  search,
  total,
  loading,
  hasMore,
  listError,
  onSearch,
  onRetry,
  onSelectExpense,
  onLoadMore,
}: ExpensesListPanelProps) {
  const tabStatuses = TAB_STATUSES[tabId];
  const visibleExpenses =
    tabStatuses && tabStatuses.length > 1
      ? expenses.filter((e) => tabStatuses.includes(e.status))
      : expenses;

  return (
    <div className="space-y-3">
      {listError ? (
        <HqErrorState
          title="Could not load expenses"
          description="Distinct from an empty inbox: Brain or Studio returned an error. Check BRAIN_API_* env and network, then retry."
          error={listError}
          onRetry={onRetry}
        />
      ) : null}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          type="search"
          placeholder="Search vendor or notes…"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 py-2 pl-9 pr-4 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none"
        />
      </div>

      <div className="flex items-center justify-between text-xs text-zinc-500">
        <span>{total === 0 ? "No expenses" : `${total} expense${total !== 1 ? "s" : ""}`}</span>
        <a
          href={`/api/admin/expenses/export.csv${tabStatuses?.length === 1 ? `?status=${tabStatuses[0]}` : ""}`}
          download="expenses.csv"
          className="flex items-center gap-1 hover:text-zinc-300"
        >
          <FileDown className="h-3.5 w-3.5" />
          Export CSV
        </a>
      </div>

      {loading && visibleExpenses.length === 0 && !listError ? (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-8 text-center">
          <p className="text-sm text-zinc-500">Loading…</p>
        </div>
      ) : visibleExpenses.length === 0 && !listError ? (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-10 text-center">
          <p className="text-sm font-medium text-zinc-400">No expenses here</p>
          <p className="mt-1 text-xs text-zinc-600">
            {tabId === "inbox" ? "New submissions appear here." : `No ${tabId} expenses.`}
          </p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {visibleExpenses.map((expense) => (
            <ExpenseRow key={expense.id} expense={expense} onClick={() => onSelectExpense(expense)} />
          ))}
        </div>
      )}

      {hasMore ? (
        <button
          type="button"
          onClick={onLoadMore}
          disabled={loading}
          className="w-full rounded-lg border border-zinc-800 py-2 text-sm text-zinc-500 transition hover:border-zinc-600 hover:text-zinc-300 disabled:opacity-50"
        >
          {loading ? "Loading…" : "Load more"}
        </button>
      ) : null}
    </div>
  );
}

type Props = {
  initialExpenses: Expense[];
  initialTotal: number;
  rules: ExpenseRoutingRules | null;
};

export function ExpensesClient({ initialExpenses, initialTotal, rules }: Props) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const resolvedTab = tabFromSearchParams(searchParams.get("tab"));

  const rollupYear = useMemo(() => new Date().getFullYear(), []);
  const rollupMonth = useMemo(() => new Date().getMonth() + 1, []);

  const [expenses, setExpenses] = useState<Expense[]>(initialExpenses);
  const [total, setTotal] = useState(initialTotal);
  const [rulesState, setRulesState] = useState<ExpenseRoutingRules | null>(rules);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(initialTotal > initialExpenses.length);
  const [cursor, setCursor] = useState<string | null>(
    initialTotal > initialExpenses.length ? String(initialExpenses.length) : null,
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
    const next = new URLSearchParams(searchParams.toString());
    next.delete("log");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [searchParams, router, pathname]);

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
    [cursor],
  );

  useEffect(() => {
    if (resolvedTab === "rollups" || resolvedTab === "settings") return;
    setCursor(null);
    void fetchExpenses(resolvedTab, search);
    // Refetch when list tab changes only; search/filter uses `handleSearch`.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- see above
  }, [resolvedTab]);

  const handleSearch = useCallback(
    (q: string) => {
      setSearch(q);
      setCursor(null);
      void fetchExpenses(resolvedTab, q);
    },
    [resolvedTab, fetchExpenses],
  );

  function handleExpenseUpdated(updated: Expense) {
    setExpenses((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
    setSelectedExpense(updated);
  }

  function goToSettingsTab() {
    const next = new URLSearchParams(searchParams.toString());
    next.set("tab", "settings");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  const listPanelProps = useMemo(
    (): Omit<ExpensesListPanelProps, "tabId"> => ({
      expenses,
      search,
      total,
      loading,
      hasMore,
      listError,
      onSearch: handleSearch,
      onRetry: () => void fetchExpenses(resolvedTab, search),
      onSelectExpense: setSelectedExpense,
      onLoadMore: () => void fetchExpenses(resolvedTab, search, true),
    }),
    [expenses, search, total, loading, hasMore, listError, resolvedTab, fetchExpenses, handleSearch],
  );

  const threshold = rulesState?.auto_approve_threshold_cents ?? 0;
  const thresholdLabel =
    threshold === 0
      ? "all manual submissions route for approval"
      : `auto-approve up to ${formatCents(threshold)}`;

  const tabs: readonly StudioTabDef<Tab>[] = useMemo(
    () => [
      { id: "inbox", label: "Inbox", content: <ExpensesListPanel tabId="inbox" {...listPanelProps} /> },
      { id: "approved", label: "Approved", content: <ExpensesListPanel tabId="approved" {...listPanelProps} /> },
      { id: "reimbursed", label: "Reimbursed", content: <ExpensesListPanel tabId="reimbursed" {...listPanelProps} /> },
      { id: "rejected", label: "Rejected", content: <ExpensesListPanel tabId="rejected" {...listPanelProps} /> },
      {
        id: "rollups",
        label: "Rollups",
        content: <RollupTab initialYear={rollupYear} initialMonth={rollupMonth} />,
      },
      {
        id: "settings",
        label: "Settings",
        content: <SettingsTab rules={rulesState} onRulesSaved={(r) => setRulesState(r)} />,
      },
    ],
    [listPanelProps, rollupYear, rollupMonth, rulesState],
  );

  return (
    <>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-zinc-100">Expenses</h1>
            <p className="mt-0.5 text-xs text-zinc-500">
              Current routing: {thresholdLabel}
              {resolvedTab !== "settings" && (
                <button
                  type="button"
                  onClick={goToSettingsTab}
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

        <TabbedPageShell<Tab> tabs={tabs} defaultTab="inbox" />
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
