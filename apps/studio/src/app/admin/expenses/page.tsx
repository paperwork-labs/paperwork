import Link from "next/link";
import { Receipt, Inbox, List, BarChart2, Settings } from "lucide-react";
import { fetchPendingCount, fetchRoutingRules } from "@/lib/expenses";
import { InboxTab } from "./_tabs/inbox-tab";
import { AllTab } from "./_tabs/all-tab";
import { RollupsTab } from "./_tabs/rollups-tab";
import { SettingsTab } from "./_components/settings-tab";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Tab = "inbox" | "all" | "rollups" | "settings";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "inbox", label: "Inbox", icon: Inbox },
  { id: "all", label: "All", icon: List },
  { id: "rollups", label: "Rollups", icon: BarChart2 },
  { id: "settings", label: "Settings", icon: Settings },
];

type Props = {
  searchParams: Promise<{ tab?: string }>;
};

export default async function ExpensesPage({ searchParams }: Props) {
  const { tab: tabParam } = await searchParams;
  const activeTab: Tab =
    tabParam === "all" || tabParam === "rollups" || tabParam === "settings"
      ? tabParam
      : "inbox";

  const [pendingCount, rules] = await Promise.all([
    fetchPendingCount(),
    activeTab === "settings" ? fetchRoutingRules() : Promise.resolve(null),
  ]);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <header className="space-y-1">
        <div className="flex items-center gap-2.5">
          <Receipt className="h-5 w-5 text-zinc-400" aria-hidden />
          <h1 className="text-xl font-semibold text-zinc-100">Expenses</h1>
          {pendingCount > 0 && (
            <span
              className="rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-medium text-amber-200"
              aria-label={`${pendingCount} pending`}
            >
              {pendingCount} pending
            </span>
          )}
        </div>
        <p className="text-sm text-zinc-500">
          Company expense tracker — submit, review, and reimburse. Auto-approve threshold defaults
          to $0; every expense requires founder approval.
        </p>
      </header>

      {/* Tab navigation */}
      <nav className="flex gap-1 border-b border-zinc-800/60" aria-label="Expense tabs">
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = id === activeTab;
          return (
            <Link
              key={id}
              href={id === "inbox" ? "/admin/expenses" : `/admin/expenses?tab=${id}`}
              className={`flex items-center gap-1.5 border-b-2 px-3 pb-2 text-sm transition-colors ${
                isActive
                  ? "border-zinc-300 font-medium text-zinc-100"
                  : "border-transparent text-zinc-500 hover:border-zinc-600 hover:text-zinc-300"
              }`}
              aria-current={isActive ? "page" : undefined}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden />
              {label}
              {id === "inbox" && pendingCount > 0 && (
                <span
                  className="rounded-full bg-amber-500/20 px-1.5 text-[10px] font-medium text-amber-200"
                  aria-label={`${pendingCount} pending`}
                >
                  {pendingCount}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Tab content */}
      <main>
        {activeTab === "inbox" && <InboxTab />}
        {activeTab === "all" && <AllTab />}
        {activeTab === "rollups" && <RollupsTab />}
        {activeTab === "settings" && <SettingsTab rules={rules} />}
      </main>
    </div>
  );
}
