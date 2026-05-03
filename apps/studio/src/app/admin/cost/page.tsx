import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { TShirtSizeBadge, type TShirtSize } from "@/components/agent/TShirtSizeBadge";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

import { CostBarSection, CostLineSection } from "./cost-dashboard-charts";

export const dynamic = "force-dynamic";
export const metadata = { title: "Agent Cost Dashboard — Studio" };

type BySize = {
  t_shirt_size: string;
  count: number;
  estimated_total_cents: number;
  actual_total_cents: number | null;
};

type ByWorkstream = {
  workstream_id: string | null;
  count: number;
  estimated_total_cents: number;
  t_shirt_size_breakdown: Record<string, number>;
};

type DailySpend = {
  date: string;
  estimated_cents: number;
  actual_cents: number | null;
};

type CalibrationDelta = {
  t_shirt_size: string;
  estimated_total_cents: number;
  actual_total_cents: number | null;
  ratio: number | null;
};

type CostSummary = {
  by_size: BySize[];
  by_workstream: ByWorkstream[];
  by_day: DailySpend[];
  calibration_delta: CalibrationDelta[];
};

function formatDollars(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

async function fetchCostSummary(): Promise<CostSummary | null> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return null;
  try {
    const res = await fetch(`${auth.root}/agents/dispatches/cost-summary`, {
      headers: { "X-Brain-Secret": auth.secret },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as CostSummary;
  } catch {
    return null;
  }
}

export default async function CostPage() {
  const data = await fetchCostSummary();

  const barChartRows =
    data?.by_size.map((r) => ({
      size: r.t_shirt_size,
      estimated: r.estimated_total_cents / 100,
      actual: r.actual_total_cents != null ? r.actual_total_cents / 100 : null,
      count: r.count,
    })) ?? [];

  const lineChartRows =
    data?.by_day.map((r) => ({
      date: r.date.slice(5),
      estimated: r.estimated_cents / 100,
      actual: r.actual_cents != null ? r.actual_cents / 100 : null,
    })) ?? [];

  const totalEstimated = data?.by_size.reduce((s, r) => s + r.estimated_total_cents, 0) ?? 0;
  const totalActual = data?.by_size.reduce((s, r) => s + (r.actual_total_cents ?? 0), 0) ?? 0;
  const totalDispatches = data?.by_size.reduce((s, r) => s + r.count, 0) ?? 0;

  return (
    <div className="space-y-8" data-testid="admin-cost-page">
      <HqPageHeader
        title="Agent Cost Dashboard"
        subtitle="T-Shirt sized dispatch spend — last 30 days. Enforced by hook; tracked in DB."
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "Cost" },
        ]}
      />

      {/* Summary stats */}
      <section className="grid grid-cols-3 gap-4">
        <StatCard label="Total Dispatches" value={String(totalDispatches)} />
        <StatCard label="Est. Spend (30d)" value={formatDollars(totalEstimated)} />
        <StatCard
          label="Actual Spend (30d)"
          value={totalActual > 0 ? formatDollars(totalActual) : "—"}
          subtitle="Calibration pending"
        />
      </section>

      {!data && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
          Unable to reach Brain API — configure BRAIN_API_URL and BRAIN_API_SECRET to see live data.
        </div>
      )}

      {/* Section 1: Spend by T-Shirt Size */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Spend by T-Shirt Size (last 30 days)
        </h2>
        {data && data.by_size.length > 0 ? (
          <CostBarSection data={barChartRows} />
        ) : (
          <EmptyChart label="No dispatches recorded yet" />
        )}
        {data && data.by_size.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {data.by_size.map((r) => (
              <span key={r.t_shirt_size} className="flex items-center gap-2 text-xs text-zinc-400">
                <TShirtSizeBadge size={r.t_shirt_size as TShirtSize} />
                <span>{r.count} dispatches · {formatDollars(r.estimated_total_cents)} est.</span>
              </span>
            ))}
          </div>
        )}
      </section>

      {/* Section 2: Spend by Workstream */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Top Workstreams by Spend (top 20)
        </h2>
        {data && data.by_workstream.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                  <th className="pb-2 pr-4">Workstream</th>
                  <th className="pb-2 pr-4">Dispatches</th>
                  <th className="pb-2 pr-4">Est. Cost</th>
                  <th className="pb-2">Sizes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {data.by_workstream.map((row, i) => (
                  <tr key={row.workstream_id ?? `unknown-${i}`} className="text-zinc-300">
                    <td className="py-2 pr-4 font-mono text-xs">
                      {row.workstream_id ?? <span className="text-zinc-600">unknown</span>}
                    </td>
                    <td className="py-2 pr-4 text-zinc-400">{row.count}</td>
                    <td className="py-2 pr-4 text-amber-300">
                      {formatDollars(row.estimated_total_cents)}
                    </td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(row.t_shirt_size_breakdown).map(([size, count]) => (
                          <span key={size} className="flex items-center gap-0.5">
                            <TShirtSizeBadge size={size as TShirtSize} />
                            <span className="text-[10px] text-zinc-500">×{count}</span>
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyChart label="No workstream data yet" />
        )}
      </section>

      {/* Section 3: Daily Spend (last 30 days) */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Daily Spend — Last 30 Days
        </h2>
        {data && data.by_day.length > 0 ? (
          <CostLineSection data={lineChartRows} />
        ) : (
          <EmptyChart label="No daily data yet" />
        )}
      </section>

      {/* Section 4: Calibration Delta */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Calibration Delta (estimated ÷ actual)
        </h2>
        <p className="text-xs text-zinc-500">
          Ratio of estimated to actual cost per size. Green = within 20%, red = off by &gt;50%.
          Null when no actual costs recorded yet.
        </p>
        {data && data.calibration_delta.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                  <th className="pb-2 pr-4">Size</th>
                  <th className="pb-2 pr-4">Est. Total</th>
                  <th className="pb-2 pr-4">Actual Total</th>
                  <th className="pb-2">Ratio</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {data.calibration_delta.map((row) => {
                  const ratioColor =
                    row.ratio == null
                      ? "text-zinc-500"
                      : Math.abs(row.ratio - 1) <= 0.2
                        ? "text-emerald-400"
                        : Math.abs(row.ratio - 1) <= 0.5
                          ? "text-amber-400"
                          : "text-red-400";
                  return (
                    <tr key={row.t_shirt_size} className="text-zinc-300">
                      <td className="py-2 pr-4">
                        <TShirtSizeBadge size={row.t_shirt_size as TShirtSize} />
                      </td>
                      <td className="py-2 pr-4 text-amber-300">
                        {formatDollars(row.estimated_total_cents)}
                      </td>
                      <td className="py-2 pr-4 text-zinc-400">
                        {row.actual_total_cents != null
                          ? formatDollars(row.actual_total_cents)
                          : "—"}
                      </td>
                      <td className={`py-2 font-mono ${ratioColor}`}>
                        {row.ratio != null ? `${row.ratio.toFixed(2)}×` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyChart label="No calibration data yet" />
        )}
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  subtitle,
}: {
  label: string;
  value: string;
  subtitle?: string;
}) {
  return (
    <div className="flex flex-col justify-center rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
      <span className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</span>
      <span className="mt-1 text-2xl font-bold text-zinc-100">{value}</span>
      {subtitle && <span className="mt-0.5 text-[10px] text-zinc-600">{subtitle}</span>}
    </div>
  );
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-zinc-800 text-sm text-zinc-600">
      {label}
    </div>
  );
}
