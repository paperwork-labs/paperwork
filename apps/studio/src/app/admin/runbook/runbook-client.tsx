"use client";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";
import type { RunbookData } from "@/lib/day0-runbook";
import { CheckCircle2, Circle, Clock, ListChecks } from "lucide-react";

function formatTime(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

export function RunbookClient({ data }: { data: RunbookData }) {
  const pctDone = data.total > 0 ? Math.round((data.completed / data.total) * 100) : 0;

  return (
    <div className="space-y-8">
      {data.sourceError && (
        <div className="rounded-lg border border-amber-700/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-300">
          <span className="font-semibold">Brain API error — showing snapshot data:</span>{" "}
          {data.sourceError}
        </div>
      )}

      <HqPageHeader
        title="Runbook"
        subtitle="Day-0 setup checklist and operational tasks"
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "Runbook" },
        ]}
      />

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <HqStatCard
          label="Total Items"
          value={data.total}
          icon={<ListChecks className="h-3.5 w-3.5 text-zinc-500" />}
        />
        <HqStatCard
          label="Completed"
          value={data.completed}
          status={data.completed === data.total ? "success" : "neutral"}
          helpText={`${pctDone}% done`}
          icon={<CheckCircle2 className="h-3.5 w-3.5 text-zinc-500" />}
        />
        <HqStatCard
          label="Remaining"
          value={data.remaining}
          status={data.remaining > 0 ? "warning" : "success"}
          icon={<Circle className="h-3.5 w-3.5 text-zinc-500" />}
        />
        <HqStatCard
          label="Est. Time Left"
          value={formatTime(data.estTimeLeftMin)}
          icon={<Clock className="h-3.5 w-3.5 text-zinc-500" />}
        />
      </div>

      {/* Section tables */}
      {data.sections.map((section) => (
        <section key={section.title} className="space-y-3">
          <h2 className="text-sm font-semibold text-zinc-300">{section.title}</h2>
          <div className="overflow-x-auto rounded-lg border border-zinc-800/80">
            <table className="w-full text-sm" data-testid="runbook-table">
              <thead>
                <tr className="border-b border-zinc-800/60 text-left text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                  <th className="w-12 px-4 py-2.5 text-center">#</th>
                  <th className="w-10 px-2 py-2.5 text-center">Status</th>
                  <th className="px-4 py-2.5">Task</th>
                  <th className="w-24 px-4 py-2.5">Time</th>
                  <th className="px-4 py-2.5">Unblocks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40">
                {section.items.map((item) => (
                  <tr
                    key={item.id}
                    className={`transition-colors hover:bg-zinc-800/30 ${
                      item.done ? "opacity-60" : ""
                    }`}
                    data-testid="runbook-item"
                  >
                    <td className="px-4 py-2.5 text-center tabular-nums text-zinc-500">
                      {item.id}
                    </td>
                    <td className="px-2 py-2.5 text-center">
                      {item.done ? (
                        <CheckCircle2 className="mx-auto h-4 w-4 text-emerald-400" />
                      ) : (
                        <Circle className="mx-auto h-4 w-4 text-zinc-600" />
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-zinc-200">{item.task}</td>
                    <td className="px-4 py-2.5 tabular-nums text-zinc-400">{item.time}</td>
                    <td className="px-4 py-2.5 text-zinc-400">{item.unblocks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
