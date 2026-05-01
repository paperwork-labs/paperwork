import Link from "next/link";
import { Target, Boxes, Rocket, Receipt } from "lucide-react";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import { loadTrackerIndex } from "@/lib/tracker";
import {
  activePlansForUi,
  activeSprintsForUi,
  companyTasksOpenCount,
  shippedSprintsForUi,
} from "@/lib/tracker-reconcile";

type ExpensesRailOverview =
  | { status: "ok"; pendingCount: number; monthCents: number }
  | { status: "unconfigured" }
  | { status: "error"; message: string };

async function fetchExpensesOverview(): Promise<ExpensesRailOverview> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return { status: "unconfigured" };

  try {
    const now = new Date();
    const [pendingRes, rollupRes] = await Promise.all([
      fetch(`${auth.root}/admin/expenses?status=pending&count_only=true`, {
        headers: { "X-Brain-Secret": auth.secret },
        cache: "no-store",
      }),
      fetch(
        `${auth.root}/admin/expenses/rollup?year=${now.getFullYear()}&month=${now.getMonth() + 1}`,
        { headers: { "X-Brain-Secret": auth.secret }, cache: "no-store" },
      ),
    ]);

    if (!pendingRes.ok) {
      return {
        status: "error",
        message: `Pending count request failed (HTTP ${pendingRes.status}).`,
      };
    }
    if (!rollupRes.ok) {
      return {
        status: "error",
        message: `Expense rollup request failed (HTTP ${rollupRes.status}).`,
      };
    }

    const pendingJson = (await pendingRes.json()) as {
      success?: boolean;
      data?: { total?: number };
    };
    const rollupJson = (await rollupRes.json()) as {
      success?: boolean;
      data?: { total_cents?: number };
    };

    if (!pendingJson.success) {
      return {
        status: "error",
        message: "Brain rejected pending expense count response.",
      };
    }
    if (!rollupJson.success) {
      return {
        status: "error",
        message: "Brain rejected expense rollup response.",
      };
    }

    return {
      status: "ok",
      pendingCount: pendingJson.data?.total ?? 0,
      monthCents: rollupJson.data?.total_cents ?? 0,
    };
  } catch (e) {
    return {
      status: "error",
      message: e instanceof Error ? e.message : "Expense overview request failed.",
    };
  }
}

function formatCentsBrief(cents: number): string {
  const dollars = cents / 100;
  if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}k`;
  return `$${dollars.toFixed(0)}`;
}

export async function TrackersRail() {
  const tracker = loadTrackerIndex();
  const allPlans = tracker.products.flatMap((p) => p.plans);
  const activePlans = activePlansForUi(allPlans);
  const openTasks = companyTasksOpenCount(tracker.company?.critical_dates ?? []);
  const activeSprintCount = activeSprintsForUi(tracker.sprints).length;
  const shippedSprintCount = shippedSprintsForUi(tracker.sprints).length;

  const expensesOverview = await fetchExpensesOverview();

  return (
    <section
      aria-label="Trackers"
      className="grid gap-3 md:grid-cols-4"
    >
      <Link
        href="/admin/tasks"
        className="group rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 transition hover:border-zinc-700 hover:bg-zinc-900"
      >
        <div className="flex items-center gap-2 text-zinc-400">
          <Target className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-wide">
            Company
          </span>
        </div>
        <p className="mt-3 text-2xl font-semibold text-zinc-100">
          {openTasks}
        </p>
        <p className="text-xs text-zinc-500">
          Company tasks · {openTasks} open
        </p>
        <p className="mt-3 text-xs text-zinc-400 group-hover:text-zinc-200">
          Tasks →
        </p>
      </Link>

      <Link
        href="/admin/products"
        className="group rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 transition hover:border-zinc-700 hover:bg-zinc-900"
      >
        <div className="flex items-center gap-2 text-zinc-400">
          <Boxes className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-wide">
            Products
          </span>
        </div>
        <p className="mt-3 text-2xl font-semibold text-zinc-100">
          {activePlans.length}
          <span className="text-base font-normal text-zinc-500">
            {" "}/ {tracker.products.length}
          </span>
        </p>
        <p className="text-xs text-zinc-500">
          in-flight product plans · {activePlans.length} of {tracker.products.length}
        </p>
        <p className="mt-3 text-xs text-zinc-400 group-hover:text-zinc-200">
          Plans →
        </p>
      </Link>

      <Link
        href="/admin/sprints"
        className="group rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 transition hover:border-zinc-700 hover:bg-zinc-900"
      >
        <div className="flex items-center gap-2 text-zinc-400">
          <Rocket className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-wide">
            Sprints
          </span>
        </div>
        <p className="mt-3 text-2xl font-semibold text-zinc-100">
          {activeSprintCount}
          <span className="text-base font-normal text-zinc-500">
            {" "}· {shippedSprintCount} shipped
          </span>
        </p>
        <p className="text-xs text-zinc-500">
          Sprints · {activeSprintCount} active · {shippedSprintCount} shipped
        </p>
        <p className="mt-3 text-xs text-zinc-400 group-hover:text-zinc-200">
          Sprints →
        </p>
      </Link>

      <Link
        href="/admin/expenses"
        className="group rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 transition hover:border-zinc-700 hover:bg-zinc-900"
      >
        <div className="flex items-center gap-2 text-zinc-400">
          <Receipt className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-wide">
            Expenses
          </span>
        </div>
        <div className="mt-3 min-h-[3.25rem]">
          {expensesOverview.status === "ok" ? (
            <>
              <p className="text-2xl font-semibold text-zinc-100">
                {expensesOverview.pendingCount}
              </p>
              <p className="text-xs text-zinc-500">
                pending · {formatCentsBrief(expensesOverview.monthCents)} this month
              </p>
            </>
          ) : expensesOverview.status === "unconfigured" ? (
            <>
              <p className="text-2xl font-semibold text-zinc-100">—</p>
              <p className="text-xs text-zinc-500">
                Set BRAIN_API_URL and BRAIN_API_SECRET
              </p>
            </>
          ) : (
            <>
              <p className="text-2xl font-semibold text-zinc-100">—</p>
              <p className="text-xs text-rose-400/90">{expensesOverview.message}</p>
            </>
          )}
        </div>
        <p className="mt-3 text-xs text-zinc-400 group-hover:text-zinc-200">
          Expenses →
        </p>
      </Link>
    </section>
  );
}
