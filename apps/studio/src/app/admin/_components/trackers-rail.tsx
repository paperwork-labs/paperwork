import Link from "next/link";
import { Target, Boxes, Rocket } from "lucide-react";

import { loadTrackerIndex } from "@/lib/tracker";
import {
  activePlansForUi,
  activeSprintsForUi,
  companyTasksOpenCount,
  shippedSprintsForUi,
} from "@/lib/tracker-reconcile";

export function TrackersRail() {
  const tracker = loadTrackerIndex();
  const allPlans = tracker.products.flatMap((p) => p.plans);
  const activePlans = activePlansForUi(allPlans);
  const openTasks = companyTasksOpenCount(tracker.company?.critical_dates ?? []);
  const activeSprintCount = activeSprintsForUi(tracker.sprints).length;
  const shippedSprintCount = shippedSprintsForUi(tracker.sprints).length;

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
    </section>
  );
}
