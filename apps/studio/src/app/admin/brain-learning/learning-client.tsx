"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { RefreshCw, Sparkles, AlertCircle } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type {
  BrainLearningDecision,
  BrainLearningEpisode,
  BrainLearningSummary,
} from "@/lib/command-center";

type BrainLearningClientProps = {
  brainConfigured: boolean;
  fetchFailed: boolean;
  summary: BrainLearningSummary | null;
  episodes: BrainLearningEpisode[] | null;
  decisions: BrainLearningDecision[] | null;
  filterPersona: string | null;
  filterProduct: string | null;
  fetchedAt: string;
};

function formatShort(iso: string | null | undefined) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
      timeZoneName: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

const EMPTY_HINT =
  "Brain is listening. Start a conversation in #ask-brain to populate.";

export function BrainLearningClient({
  brainConfigured,
  fetchFailed,
  summary,
  episodes,
  decisions,
  filterPersona,
  filterProduct,
  fetchedAt,
}: BrainLearningClientProps) {
  const router = useRouter();
  const epList = episodes ?? [];
  const decList = decisions ?? [];
  const noActivity =
    !fetchFailed &&
    (summary?.totals.episodes ?? 0) === 0 &&
    (summary?.totals.routing_decisions ?? 0) === 0 &&
    epList.length === 0 &&
    decList.length === 0;

  const chartData =
    summary?.spark.map((d) => ({
      ...d,
      label: d.date.slice(5).replace(/-/, "/"),
    })) ?? [];

  const maxSpark = Math.max(
    1,
    ...chartData.flatMap((d) => [d.episode_count, d.decision_count]),
  );

  return (
    <div className="space-y-8 text-zinc-200">
      <div className="flex flex-col gap-3 border-b border-zinc-800/80 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-zinc-50">
            <Sparkles className="h-7 w-7 text-amber-400/90" />
            Brain learning
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-500">
            Ambient learning observability: today&apos;s memory episodes, routing decisions, and
            importance-weighted takeaways (UTC day boundary).
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          <span>Refreshed {formatShort(fetchedAt)}</span>
          <button
            type="button"
            onClick={() => router.refresh()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-1.5 text-sm text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {!brainConfigured && (
        <div className="flex gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100/90">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p>
            Set <code className="rounded bg-zinc-800 px-1">BRAIN_API_URL</code> and{" "}
            <code className="rounded bg-zinc-800 px-1">BRAIN_API_SECRET</code> in Vercel (Studio) to
            load this view.
          </p>
        </div>
      )}

      {fetchFailed && brainConfigured && (
        <div className="flex gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100/90">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p>
            Could not load learning data from Brain. Confirm{" "}
            <code className="rounded bg-zinc-800 px-1">BRAIN_LEARNING_DASHBOARD_ENABLED</code> on
            brain-api, secret alignment, and network reachability.
          </p>
        </div>
      )}

      {noActivity && !fetchFailed && brainConfigured && (
        <p className="rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 py-4 text-sm text-zinc-400">
          {EMPTY_HINT}
        </p>
      )}

      {summary && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">Learning trend</h2>
          <div className="grid gap-4 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4 sm:grid-cols-2">
            <div className="h-32 w-full min-w-0 sm:col-span-2">
              <p className="mb-1 text-xs text-zinc-500">14-day episode + routing decision counts (UTC days)</p>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <XAxis
                      dataKey="label"
                      tick={{ fill: "#71717a", fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="episode_count"
                      name="Episodes"
                      stroke="#a1a1aa"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="decision_count"
                      name="Decisions"
                      stroke="#4ade80"
                      strokeWidth={2}
                      dot={false}
                    />
                    <YAxis
                      width={32}
                      domain={[0, maxSpark]}
                      tick={{ fill: "#52525b", fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : null}
            </div>
            <div>
              <p className="text-xs text-zinc-500">Today (UTC) — episodes</p>
              <p className="text-2xl font-semibold text-zinc-100">{summary.totals.episodes}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500">Today (UTC) — routing decisions</p>
              <p className="text-2xl font-semibold text-zinc-100">{summary.totals.routing_decisions}</p>
            </div>
          </div>
        </section>
      )}

      {summary && summary.totals && (summary.totals.tokens_in > 0 || summary.totals.tokens_out > 0) && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">Token totals (UTC day)</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {summary.model_token_totals
              .filter((r) => (r.tokens_in ?? 0) + (r.tokens_out ?? 0) > 0)
              .map((row) => (
                <div
                  key={row.model ?? "unknown"}
                  className="flex items-center justify-between rounded-lg border border-zinc-800/80 bg-zinc-900/30 px-3 py-2 text-sm"
                >
                  <span className="truncate text-zinc-400">{row.model ?? "unknown model"}</span>
                  <span className="shrink-0 font-mono text-xs text-zinc-300">
                    in {row.tokens_in} / out {row.tokens_out}
                  </span>
                </div>
              ))}
          </div>
        </section>
      )}

      {summary && summary.top_by_importance.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">
            What did Brain learn today?
          </h2>
          <p className="text-xs text-zinc-600">
            Top {summary.top_by_importance.length} by importance (UTC {summary.anchor_date})
          </p>
          <ul className="space-y-2">
            {summary.top_by_importance.map((ep) => (
              <li
                key={ep.id}
                className="rounded-lg border border-zinc-800/80 bg-zinc-900/50 px-4 py-3"
              >
                <div className="flex flex-wrap items-baseline gap-2 text-sm">
                  <span className="text-amber-300/90">{(ep.importance ?? 0).toFixed(2)}</span>
                  <span className="text-zinc-500">{ep.persona ?? "—"}</span>
                  {ep.product ? <span className="text-zinc-600">· {ep.product}</span> : null}
                </div>
                <p className="mt-1 text-sm text-zinc-300">{ep.summary?.slice(0, 500) || "—"}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {summary && summary.counts_by_persona_product.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">
            Today by persona + product
          </h2>
          <p className="text-xs text-zinc-600">Filter the episode table (below)</p>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/admin/brain-learning"
              className={`rounded-full border px-2.5 py-1 text-xs ${
                !filterPersona && !filterProduct
                  ? "border-zinc-400 bg-zinc-800 text-zinc-100"
                  : "border-zinc-800 text-zinc-500 hover:border-zinc-500"
              }`}
            >
              All
            </Link>
            {summary.counts_by_persona_product.map((row) => {
              const active =
                filterPersona == row.persona && filterProduct == row.product; // null-safe
              const href = (() => {
                const p = new URLSearchParams();
                if (row.persona) p.set("persona", row.persona);
                if (row.product) p.set("product", row.product);
                return p.toString() ? `/admin/brain-learning?${p}` : "/admin/brain-learning";
              })();
              return (
                <Link
                  key={`${row.persona ?? "∅"}-${row.product ?? "∅"}`}
                  href={href}
                  className={`rounded-full border px-2.5 py-1 text-xs ${
                    active
                      ? "border-zinc-400 bg-zinc-800 text-zinc-100"
                      : "border-zinc-800 text-zinc-500 hover:border-zinc-500"
                  }`}
                >
                  {row.persona ?? "—"}+{row.product ?? "—"} ({row.episode_count})
                </Link>
              );
            })}
          </div>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">
          Today&apos;s episodes
        </h2>
        <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-800/80 text-xs uppercase tracking-wider text-zinc-500">
                <th className="p-3 font-medium">When (UTC)</th>
                <th className="p-3 font-medium">Persona</th>
                <th className="p-3 font-medium">Product</th>
                <th className="p-3 font-medium">Importance</th>
                <th className="p-3 font-medium">Model</th>
                <th className="p-3 font-medium">Tokens in/out</th>
                <th className="p-3 font-medium">Summary</th>
              </tr>
            </thead>
            <tbody>
              {epList.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-4 text-zinc-500">
                    {brainConfigured ? "No episodes in the selected window." : "—"}
                  </td>
                </tr>
              ) : (
                epList.map((r) => (
                  <tr key={r.id} className="border-b border-zinc-800/40 align-top text-zinc-300">
                    <td className="p-3 font-mono text-xs text-zinc-500">{formatShort(r.created_at)}</td>
                    <td className="p-3">{r.persona ?? "—"}</td>
                    <td className="p-3 text-zinc-500">{r.product ?? "—"}</td>
                    <td className="p-3 text-amber-200/80">{(r.importance ?? 0).toFixed(2)}</td>
                    <td className="p-3 text-xs text-zinc-500">{r.model_used ?? "—"}</td>
                    <td className="p-3 font-mono text-xs text-zinc-500">
                      {r.tokens_in ?? "—"} / {r.tokens_out ?? "—"}
                    </td>
                    <td className="p-3 text-zinc-400">{r.summary?.slice(0, 200) || "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">
          Decision quality (24h, routing)
        </h2>
        <ul className="space-y-2">
          {decList.length === 0 ? (
            <li className="text-sm text-zinc-500">No routing decisions in the last 24h.</li>
          ) : (
            decList.map((d) => (
              <li
                key={d.id}
                className="rounded-lg border border-zinc-800/80 bg-zinc-900/40 px-3 py-2 text-sm"
              >
                <div className="flex flex-wrap items-baseline gap-2 text-xs text-zinc-500">
                  <span className="font-mono">{formatShort(d.created_at)}</span>
                  <span className="text-zinc-400">{d.persona ?? "router"}</span>
                  {d.model_used ? <span>· {d.model_used}</span> : null}
                </div>
                <p className="mt-0.5 text-zinc-300">{d.summary?.slice(0, 300) || "—"}</p>
                {d.outcome != null && String(d.outcome) !== "" && (
                  <p className="mt-1 text-xs text-zinc-500">Outcome: {String(d.outcome)}</p>
                )}
              </li>
            ))
          )}
        </ul>
      </section>
    </div>
  );
}
