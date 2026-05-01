"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ExternalLink, Search, Users } from "lucide-react";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import type { ActivityFeedRow } from "@/lib/personas-types";

export type PeopleEmployeeRow = {
  personaId: string;
  displayName: string;
  description: string | null;
  domainLabel: string;
  autonomyLabel: string;
  routingActive: boolean;
  recentActivity: ActivityFeedRow[];
};

export function PeopleEmployeesClient({
  employees,
  brainApiError,
}: {
  employees: PeopleEmployeeRow[];
  brainApiError: string | null;
}) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return employees;
    return employees.filter(
      (e) =>
        e.personaId.toLowerCase().includes(needle) ||
        e.displayName.toLowerCase().includes(needle) ||
        (e.description?.toLowerCase().includes(needle) ?? false) ||
        e.domainLabel.toLowerCase().includes(needle) ||
        e.autonomyLabel.toLowerCase().includes(needle),
    );
  }, [employees, q]);

  return (
    <div className="space-y-8">
      {brainApiError ? (
        <div className="rounded-lg border border-amber-700/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-300">
          <span className="font-semibold">Brain API error — snapshot data:</span>{" "}
          {brainApiError}
        </div>
      ) : null}

      <HqPageHeader
        title="People"
        subtitle="Brain personas as employees — domains from PersonaSpec YAML (apis/brain/app/personas/specs), autonomy from tools / cadence / compliance, recent dispatch activity."
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "People" },
        ]}
        actions={
          <Link
            href="/admin/brain/personas"
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-600/80 bg-zinc-900/60 px-3 py-1.5 text-xs font-medium text-zinc-200 motion-safe:transition-colors hover:border-zinc-500 hover:bg-zinc-800/80"
          >
            Full workspace
            <ExternalLink className="h-3.5 w-3.5 opacity-70" aria-hidden />
          </Link>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-zinc-400">
          <span className="font-semibold tabular-nums text-zinc-200">
            {filtered.length}
          </span>
          {filtered.length === employees.length
            ? " personas"
            : ` of ${employees.length} personas`}
        </p>
        <label className="relative flex min-w-0 max-w-md flex-1 items-center gap-2 rounded-lg border border-zinc-700/80 bg-zinc-900/50 px-3 py-2">
          <Search className="h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter by name, domain, autonomy…"
            className="min-w-0 flex-1 bg-transparent text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none"
          />
        </label>
      </div>

      {filtered.length === 0 ? (
        <HqEmptyState
          icon={<Users className="h-10 w-10 text-zinc-600" />}
          title="No matches"
          description="Try a different search, or clear the filter."
        />
      ) : (
        <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((e) => (
            <li
              key={e.personaId}
              className="flex flex-col rounded-xl border border-zinc-800/90 bg-zinc-900/40 p-4 motion-safe:transition-colors hover:border-zinc-700/90"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="truncate text-base font-semibold text-zinc-100">
                    {e.displayName}
                  </h2>
                  <p className="mt-0.5 font-mono text-[11px] text-zinc-500">{e.personaId}</p>
                </div>
                {e.routingActive ? (
                  <span className="shrink-0 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300 ring-1 ring-emerald-500/30">
                    Always-on rule
                  </span>
                ) : null}
              </div>

              <p className="mt-3 line-clamp-3 text-sm leading-snug text-zinc-400">
                {e.description ?? "—"}
              </p>

              <div className="mt-4 space-y-2 text-xs">
                <div>
                  <span className="text-zinc-500">Domain</span>
                  <p className="mt-0.5 font-medium capitalize text-zinc-200">{e.domainLabel}</p>
                </div>
                <div>
                  <span className="text-zinc-500">Autonomy</span>
                  <p className="mt-0.5 text-zinc-300">{e.autonomyLabel}</p>
                </div>
              </div>

              <div className="mt-4 border-t border-zinc-800/80 pt-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                  Recent activity
                </p>
                {e.recentActivity.length === 0 ? (
                  <p className="mt-2 text-xs text-zinc-500">No attributed dispatches yet.</p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {e.recentActivity.map((a, i) => (
                      <li
                        key={`${e.personaId}-${a.dispatchedAt}-${i}`}
                        className="rounded-lg bg-zinc-950/50 px-2 py-1.5 text-[11px] text-zinc-400"
                      >
                        <span className="tabular-nums text-zinc-500">
                          {a.dispatchedAt.slice(0, 19).replace("T", " ")}
                        </span>
                        <span className="mx-1.5 text-zinc-600">·</span>
                        <span className="text-zinc-300">{a.successLabel}</span>
                        <span className="mx-1.5 text-zinc-600">·</span>
                        <span>{a.workstreamTag}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
