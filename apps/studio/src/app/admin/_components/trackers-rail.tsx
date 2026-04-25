import Link from "next/link";
import { Target, Boxes, Rocket } from "lucide-react";

import { loadTrackerIndex } from "@/lib/tracker";

export function TrackersRail() {
  let summary: {
    openCriticalDates: number;
    productCount: number;
    activePlanCount: number;
    activeSprintCount: number;
    shippedSprintCount: number;
  };
  try {
    const tracker = loadTrackerIndex();
    const openCriticalDates = (tracker.company?.critical_dates ?? []).filter(
      (d) => !/done|complete/i.test(d.status)
    ).length;
    const productCount = tracker.products.length;
    const activePlanCount = tracker.products.reduce(
      (acc, p) => acc + p.plans.filter((pl) => pl.status === "active").length,
      0
    );
    const activeSprintCount = tracker.sprints.filter((s) => s.status === "active").length;
    const shippedSprintCount = tracker.sprints.filter((s) => s.status === "shipped").length;
    summary = {
      openCriticalDates,
      productCount,
      activePlanCount,
      activeSprintCount,
      shippedSprintCount,
    };
  } catch {
    return null;
  }

  return (
    <section
      aria-label="Trackers"
      className="grid gap-3 md:grid-cols-3"
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
          {summary.openCriticalDates}
        </p>
        <p className="text-xs text-zinc-500">
          critical dates open in <code>docs/TASKS.md</code>
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
          {summary.activePlanCount}
          <span className="text-base font-normal text-zinc-500">
            {" "}/ {summary.productCount}
          </span>
        </p>
        <p className="text-xs text-zinc-500">
          active plans across products
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
          {summary.activeSprintCount}
          <span className="text-base font-normal text-zinc-500">
            {" "}+ {summary.shippedSprintCount} shipped
          </span>
        </p>
        <p className="text-xs text-zinc-500">cross-cutting work logs</p>
        <p className="mt-3 text-xs text-zinc-400 group-hover:text-zinc-200">
          Sprints →
        </p>
      </Link>
    </section>
  );
}
