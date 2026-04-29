"use client";

import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { usePersonasInitial } from "../personas-client";

export function CostTab() {
  const { cost7d, cost30d, brainConfigured } = usePersonasInitial();

  const data7 = useMemo(
    () =>
      (cost7d?.personas ?? []).map((p) => ({
        persona: p.persona,
        usd: Number.isFinite(p.usd) ? p.usd : 0,
        tokens: (Number.isFinite(p.tokens_in) ? p.tokens_in : 0) + (Number.isFinite(p.tokens_out) ? p.tokens_out : 0),
      })),
    [cost7d],
  );
  const data30 = useMemo(
    () =>
      (cost30d?.personas ?? []).map((p) => ({
        persona: p.persona,
        usd: Number.isFinite(p.usd) ? p.usd : 0,
        tokens: (Number.isFinite(p.tokens_in) ? p.tokens_in : 0) + (Number.isFinite(p.tokens_out) ? p.tokens_out : 0),
      })),
    [cost30d],
  );

  const empty7 = !cost7d?.has_file || data7.length === 0;
  const empty30 = !cost30d?.has_file || data30.length === 0;

  return (
    <div className="space-y-8" data-testid="cost-tab">
      {!brainConfigured && (
        <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100/90">
          Brain API is not configured — cost data unavailable.
        </p>
      )}
      {brainConfigured && empty7 && empty30 && (
        <p className="text-sm text-zinc-400" data-testid="cost-empty-state">
          No cost data yet — Brain ingests from LLM API responses; first data lands at next persona invocation.
        </p>
      )}
      <section className="space-y-3">
        <h2 className="text-lg font-medium text-zinc-100">Last 7 days</h2>
        {!empty7 ? (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data7} margin={{ top: 8, right: 8, left: 8, bottom: 64 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
                <XAxis dataKey="persona" tick={{ fill: "#a1a1aa", fontSize: 11 }} angle={-35} textAnchor="end" height={70} />
                <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }}
                  formatter={(value) => {
                    const n = typeof value === "number" ? value : Number(value);
                    return [`$${Number.isFinite(n) ? n.toFixed(4) : "0"}`, "Spend (USD)"];
                  }}
                />
                <Bar dataKey="usd" fill="#38bdf8" name="usd" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">No 7-day series in `persona_cost.json`.</p>
        )}
      </section>
      <section className="space-y-3">
        <h2 className="text-lg font-medium text-zinc-100">Last 30 days</h2>
        {!empty30 ? (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data30} margin={{ top: 8, right: 8, left: 8, bottom: 64 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
                <XAxis dataKey="persona" tick={{ fill: "#a1a1aa", fontSize: 11 }} angle={-35} textAnchor="end" height={70} />
                <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }}
                  formatter={(value) => {
                    const n = typeof value === "number" ? value : Number(value);
                    return [`$${Number.isFinite(n) ? n.toFixed(4) : "0"}`, "Spend (USD)"];
                  }}
                />
                <Bar dataKey="usd" fill="#a78bfa" name="usd" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">No 30-day series in `persona_cost.json`.</p>
        )}
      </section>
    </div>
  );
}
