"use client";

import { useState } from "react";
import { Download, BarChart2 } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { MonthlyRollup } from "@/types/expenses";
import { CATEGORY_LABELS, formatCents } from "@/types/expenses";

const CHART_COLORS = [
  "#818cf8",
  "#34d399",
  "#f472b6",
  "#fb923c",
  "#38bdf8",
  "#a78bfa",
  "#4ade80",
  "#fbbf24",
  "#f87171",
];

type Props = {
  initialYear: number;
  initialMonth: number;
};

export function RollupTab({ initialYear, initialMonth }: Props) {
  const [year, setYear] = useState(initialYear);
  const [month, setMonth] = useState(initialMonth);
  const [rollup, setRollup] = useState<MonthlyRollup | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchRollup(y: number, m: number) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/expenses/rollup?year=${y}&month=${m}`);
      const json = await res.json();
      if (!res.ok || !json.success) throw new Error(json.error || "Failed to load rollup");
      setRollup(json.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setRollup(null);
    } finally {
      setLoading(false);
    }
  }

  function handleChange(newYear: number, newMonth: number) {
    setYear(newYear);
    setMonth(newMonth);
    void fetchRollup(newYear, newMonth);
  }

  const csvHref = `/api/admin/expenses/export.csv?year=${year}&month=${month}`;
  const chartData = (rollup?.category_breakdown ?? []).map((c, i) => ({
    name: CATEGORY_LABELS[c.category] ?? c.category,
    amount: c.amount_cents / 100,
    color: CHART_COLORS[i % CHART_COLORS.length],
  }));

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label htmlFor="rollup-year" className="text-xs font-medium text-zinc-400">
            Year
          </label>
          <select
            id="rollup-year"
            value={year}
            onChange={(e) => handleChange(Number(e.target.value), month)}
            className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 focus:outline-none"
          >
            {[2025, 2026, 2027].map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="rollup-month" className="text-xs font-medium text-zinc-400">
            Month
          </label>
          <select
            id="rollup-month"
            value={month}
            onChange={(e) => handleChange(year, Number(e.target.value))}
            className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 focus:outline-none"
          >
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>
                {new Date(2000, m - 1).toLocaleString("en-US", { month: "long" })}
              </option>
            ))}
          </select>
        </div>
        <a
          href={csvHref}
          download={`expenses-${year}-${String(month).padStart(2, "0")}.csv`}
          className="ml-auto flex items-center gap-1.5 rounded-lg border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100"
        >
          <Download className="h-3.5 w-3.5" />
          Export CSV
        </a>
      </div>

      {loading ? (
        <div className="flex h-32 items-center justify-center">
          <p className="text-sm text-zinc-500">Loading rollup…</p>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-900/40 bg-red-500/5 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      ) : rollup === null ? (
        <div className="flex h-32 flex-col items-center justify-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/40 text-center">
          <BarChart2 className="h-5 w-5 text-zinc-600" />
          <p className="text-sm text-zinc-500">Select a month above to load the rollup</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid gap-3 sm:grid-cols-3">
            <MetricCard
              label="Total spend"
              value={formatCents(rollup.total_cents)}
            />
            <MetricCard
              label="Approved"
              value={formatCents(rollup.approved_cents)}
            />
            <MetricCard
              label="Pending / flagged"
              value={formatCents(rollup.pending_cents + rollup.flagged_cents)}
            />
          </div>

          {rollup.pct_vs_prior_avg !== null ? (
            <p className="text-xs text-zinc-500">
              {rollup.pct_vs_prior_avg >= 0 ? "+" : ""}
              {rollup.pct_vs_prior_avg}% vs prior 3-month avg (
              {formatCents(rollup.prior_3mo_avg_cents)}/mo)
            </p>
          ) : (
            <p className="text-xs text-zinc-600">
              No prior months in store — prior-avg comparison unavailable.
            </p>
          )}

          {/* Chart */}
          {chartData.length > 0 ? (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
              <p className="mb-4 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Spend by category
              </p>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 10, fill: "#71717a" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#71717a" }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v: number) => `$${v}`}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#18181b",
                      border: "1px solid #3f3f46",
                      borderRadius: 8,
                      color: "#e4e4e7",
                      fontSize: 12,
                    }}
                    formatter={(value) =>
                      typeof value === "number" ? [`$${value.toFixed(2)}`, "Amount"] : [String(value), "Amount"]
                    }
                  />
                  <Bar dataKey="amount" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 text-center text-sm text-zinc-500">
              No expenses for this month.
            </div>
          )}

          {/* Vendor breakdown */}
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
              By category
            </p>
            {rollup.category_breakdown.length === 0 ? (
              <p className="text-sm text-zinc-600">No data.</p>
            ) : (
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 divide-y divide-zinc-800">
                {rollup.category_breakdown.map((cat) => (
                  <div
                    key={cat.category}
                    className="flex items-center justify-between px-4 py-2.5"
                  >
                    <span className="text-sm text-zinc-300">
                      {CATEGORY_LABELS[cat.category] ?? cat.category}
                    </span>
                    <div className="flex items-center gap-4">
                      <span className="text-xs text-zinc-500">{cat.count} expense{cat.count !== 1 ? "s" : ""}</span>
                      <span className="text-sm font-medium tabular-nums text-zinc-100">
                        {formatCents(cat.amount_cents)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <p className="text-xs font-medium text-zinc-500">{label}</p>
      <p className="mt-1.5 text-xl font-semibold tabular-nums text-zinc-100">{value}</p>
    </div>
  );
}
