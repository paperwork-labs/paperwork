import Link from "next/link";
import { CheckCircle2, AlertTriangle, Circle, ExternalLink } from "lucide-react";

import { loadTrackerIndex } from "@/lib/tracker";
import { companyTasksOpenCount } from "@/lib/tracker-reconcile";

export const dynamic = "force-static";

function statusTone(status: string): {
  icon: typeof CheckCircle2;
  className: string;
} {
  const lower = status.toLowerCase();
  if (lower.includes("done") || lower.includes("complete") || lower.includes("shipped")) {
    return { icon: CheckCircle2, className: "text-emerald-300 bg-emerald-500/10" };
  }
  if (lower.includes("not started") || lower.includes("blocked")) {
    return { icon: AlertTriangle, className: "text-rose-300 bg-rose-500/10" };
  }
  if (lower.includes("progress") || lower.includes("active") || lower.includes("review")) {
    return { icon: Circle, className: "text-amber-300 bg-amber-500/10" };
  }
  return { icon: Circle, className: "text-zinc-300 bg-zinc-700/40" };
}

export default function TasksPage() {
  const { company } = loadTrackerIndex();
  const openDates = companyTasksOpenCount(company.critical_dates);

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Company Tasks</h1>
          <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
            source of truth
          </span>
        </div>
        <p className="text-sm text-zinc-400">
          Top-level Paperwork Labs tracker rendered from{" "}
          <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs">{company.path}</code>.
          {company.version ? <> Version {company.version}.</> : null}
          {company.updated ? <> Updated {company.updated}.</> : null}
        </p>
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          <Link
            href="/admin/sprints"
            className="rounded-md border border-zinc-800 px-2 py-1 transition hover:border-zinc-700 hover:text-zinc-300"
          >
            Sprints →
          </Link>
          <Link
            href="/admin/products/axiomfolio/plan"
            className="rounded-md border border-zinc-800 px-2 py-1 transition hover:border-zinc-700 hover:text-zinc-300"
          >
            Per-product plans →
          </Link>
          <a
            href={`https://github.com/paperwork-labs/paperwork/blob/main/${company.path}`}
            target="_blank"
            rel="noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-zinc-500 transition hover:text-zinc-300"
          >
            Edit on GitHub <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </header>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-100">Critical Dates</h2>
          <span className="text-[10px] uppercase tracking-wide text-zinc-500">
            {openDates} open · {company.critical_dates.length} milestones
          </span>
        </div>
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-900/80 text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-3 py-2">Milestone</th>
                <th className="px-3 py-2">Deadline</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {company.critical_dates.map((row) => {
                const tone = statusTone(row.status);
                const Icon = tone.icon;
                return (
                  <tr key={`${row.milestone}-${row.deadline}`} className="align-top">
                    <td className="px-3 py-2 font-medium text-zinc-100">
                      {row.milestone}
                    </td>
                    <td className="px-3 py-2 text-zinc-300">{row.deadline}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${tone.className}`}
                      >
                        <Icon className="h-3 w-3" />
                        {row.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-zinc-400">{row.notes}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <h2 className="mb-2 text-sm font-semibold text-zinc-100">How this works</h2>
        <p className="text-sm text-zinc-400">
          This page renders <code className="rounded bg-zinc-800 px-1 text-xs">apps/studio/src/data/tracker-index.json</code>,
          which is generated from the markdown trackers in the repo by{" "}
          <code className="rounded bg-zinc-800 px-1 text-xs">scripts/generate_tracker_index.py</code>.
          CI fails if the JSON drifts from the markdown source. Edit the markdown,
          re-run the script (or push — the generator runs in CI), and this page
          updates on next deploy.
        </p>
      </section>
    </div>
  );
}
