"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, DollarSign, RefreshCw } from "lucide-react";
import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";

type VendorRow = {
  vendor: string;
  amount_usd: number;
  budget_cap_usd: number | null;
  budget_utilization: number | null;
  categories: Record<string, number>;
};

type Summary = {
  month: string;
  vendors: VendorRow[];
  total_usd: number;
  monthly_budgets: Record<string, number | null>;
};

type BurnRate = {
  window_days: number;
  total_usd: number;
  daily_average_usd: number;
  as_of: string;
};

type AlertItem = {
  vendor: string;
  budget_key: string;
  spent_usd: number;
  budget_usd: number;
  utilization: number;
  status: "approaching" | "exceeded";
};

function currentMonthUtc(): string {
  return new Date().toISOString().slice(0, 7);
}

function titleCaseVendor(name: string): string {
  return name.length ? name[0].toUpperCase() + name.slice(1) : name;
}

export default function CostTab() {
  const [month, setMonth] = useState(currentMonthUtc);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [burn, setBurn] = useState<BurnRate | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sRes, bRes, aRes] = await Promise.all([
        fetch(`/api/admin/costs/summary?month=${encodeURIComponent(month)}`, { cache: "no-store" }),
        fetch("/api/admin/costs/burn-rate", { cache: "no-store" }),
        fetch(`/api/admin/costs/alerts?month=${encodeURIComponent(month)}`, { cache: "no-store" }),
      ]);
      if (!sRes.ok) {
        const j = (await sRes.json().catch(() => ({}))) as { error?: string };
        throw new Error(j.error ?? `Summary request failed (${sRes.status})`);
      }
      if (!bRes.ok) {
        const j = (await bRes.json().catch(() => ({}))) as { error?: string };
        throw new Error(j.error ?? `Burn rate request failed (${bRes.status})`);
      }
      if (!aRes.ok) {
        const j = (await aRes.json().catch(() => ({}))) as { error?: string };
        throw new Error(j.error ?? `Alerts request failed (${aRes.status})`);
      }
      setSummary((await sRes.json()) as Summary);
      setBurn((await bRes.json()) as BurnRate);
      const alertBody = (await aRes.json()) as { alerts: AlertItem[] };
      setAlerts(alertBody.alerts ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load cost data");
      setSummary(null);
      setBurn(null);
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => {
    void load();
  }, [load]);

  const noLedgerData = useMemo(() => {
    if (!summary) return false;
    return summary.vendors.length === 0 && summary.total_usd === 0;
  }, [summary]);

  if (error) {
    return (
      <div className="space-y-6">
        <HqEmptyState
          icon={<DollarSign className="mx-auto h-10 w-10 text-zinc-600" />}
          title="Could not load cost data"
          description={error}
          action={{ label: "Retry", onClick: () => void load() }}
        />
      </div>
    );
  }

  if (loading && !summary) {
    return (
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <RefreshCw className="h-4 w-4 animate-spin" />
        Loading cost ledger…
      </div>
    );
  }

  if (noLedgerData) {
    return (
      <HqEmptyState
        icon={<DollarSign className="mx-auto h-10 w-10 text-zinc-600" />}
        title="No ledger entries for this month"
        description='Add rows to apis/brain/data/cost_ledger.json (or wire vendor billing APIs) to populate this view.'
      />
    );
  }

  if (!summary || !burn) {
    return null;
  }

  return (
    <div className="space-y-8" data-testid="infra-cost-tab">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-zinc-200">Infrastructure spend</h2>
          <p className="mt-1 text-sm text-zinc-500">
            Ledger-backed totals and monthly budgets (Anthropic, OpenAI, Gemini, Render, Vercel, Hetzner).
          </p>
        </div>
        <label className="flex flex-col gap-1 text-xs font-medium text-zinc-500">
          Month (UTC)
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
          />
        </label>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <HqStatCard
          variant="compact"
          label={`${summary.month} total`}
          value={`$${summary.total_usd.toFixed(2)}`}
          helpText="Sum of ledger lines in month"
        />
        <HqStatCard
          variant="compact"
          label="Trailing daily average"
          value={`$${burn.daily_average_usd.toFixed(2)}`}
          helpText={`${burn.window_days}-day window · $${burn.total_usd.toFixed(2)} total`}
        />
        <HqStatCard
          variant="compact"
          label="Budget alerts"
          value={alerts.length}
          status={alerts.some((a) => a.status === "exceeded") ? "danger" : alerts.length ? "warning" : "success"}
          helpText="Vendors over 80% of cap"
        />
      </div>

      {alerts.length > 0 ? (
        <div className="space-y-3">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Budget alerts</p>
          <div className="grid gap-3 md:grid-cols-2">
            {alerts.map((a) => (
              <div
                key={a.budget_key}
                className={`rounded-xl border px-4 py-3 ${
                  a.status === "exceeded"
                    ? "border-[var(--status-danger)]/45 bg-[var(--status-danger-bg)]"
                    : "border-[var(--status-warning)]/45 bg-[var(--status-warning-bg)]"
                }`}
              >
                <div className="flex items-start gap-2">
                  <AlertTriangle
                    className={`mt-0.5 h-4 w-4 shrink-0 ${
                      a.status === "exceeded" ? "text-[var(--status-danger)]" : "text-[var(--status-warning)]"
                    }`}
                  />
                  <div>
                    <p className="text-sm font-medium text-zinc-100">
                      {titleCaseVendor(a.budget_key)}
                      {a.status === "exceeded" ? " — over budget" : " — approaching limit"}
                    </p>
                    <p className="mt-1 text-sm text-zinc-400">
                      ${a.spent_usd.toFixed(2)} of ${a.budget_usd.toFixed(2)} (
                      {(a.utilization * 100).toFixed(1)}%)
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">By vendor</p>
        <div className="grid gap-3 md:grid-cols-2">
          {summary.vendors.map((v) => {
            const cap = v.budget_cap_usd;
            const pct = cap && cap > 0 ? Math.min(100, (v.amount_usd / cap) * 100) : 0;
            return (
              <div
                key={v.vendor}
                className="rounded-xl border border-zinc-800 bg-zinc-950/40 px-4 py-3 shadow-sm shadow-black/20"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-zinc-100">{titleCaseVendor(v.vendor)}</span>
                  <span className="text-sm tabular-nums text-zinc-300">${v.amount_usd.toFixed(2)}</span>
                </div>
                {cap != null && cap > 0 ? (
                  <div className="mt-3">
                    <div className="mb-1 flex justify-between text-xs text-zinc-500">
                      <span>Budget</span>
                      <span className="tabular-nums">
                        ${v.amount_usd.toFixed(2)} / ${cap.toFixed(2)}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-zinc-800">
                      <div
                        className={`h-full rounded-full transition-all ${
                          pct >= 100
                            ? "bg-[var(--status-danger)]"
                            : pct >= 80
                              ? "bg-[var(--status-warning)]"
                              : "bg-[var(--status-success)]"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-zinc-600">No monthly cap configured in ledger</p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
