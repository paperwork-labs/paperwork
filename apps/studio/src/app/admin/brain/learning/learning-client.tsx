"use client";

import { useEffect, useState, type ReactNode } from "react";
import { AlertCircle } from "lucide-react";
import {
  BrainLearningHeader,
  formatLocalDateTime,
  useBrainLearningEpisodes,
  useBrainLearningLessons,
  useBrainLearningSummary,
  useBrainLearningTimeline,
} from "@/lib/api/brain";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

export function LearningObservabilityClient(props: { brainConfigured: boolean }) {
  const { brainConfigured } = props;
  const { data: summary, error: summaryError, isLoading: summaryLoading } = useBrainLearningSummary();
  const { data: timeline, isLoading: timelineLoading } = useBrainLearningTimeline(30);
  const [tab, setTab] = useState<"overview" | "lessons">("overview");
  const [page, setPage] = useState(0);
  const { data: episodesPayload, isLoading: episodesLoading } = useBrainLearningEpisodes(page, null);
  const [lessonSearch, setLessonSearch] = useState("");
  const debouncedLessonSearch = useDebouncedValue(lessonSearch, 300);
  const { data: lessonsPayload, isLoading: lessonsLoading } = useBrainLearningLessons(debouncedLessonSearch);

  const chartData = (timeline?.series ?? []).map((d) => ({ ...d, label: d.date.slice(5).replace("-", "/") }));
  const maxY = Math.max(1, ...chartData.flatMap((d) => [d.episodes, d.lessons, d.agents_involved]));
  const totalPages = episodesPayload ? Math.max(1, Math.ceil(episodesPayload.total / episodesPayload.limit)) : 1;

  return (
    <div className="space-y-8 text-zinc-200">
      <BrainLearningHeader lastUpdatedIso={summary?.as_of ?? null} />
      {!brainConfigured && (
        <div className="flex gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100/90">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p>
            Set <code className="rounded bg-zinc-800 px-1">BRAIN_API_URL</code> and{" "}
            <code className="rounded bg-zinc-800 px-1">BRAIN_API_SECRET</code> in Studio.
          </p>
        </div>
      )}
      {brainConfigured && summaryError && (
        <div className="flex gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100/90">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p>Could not load learning summary from Brain.</p>
        </div>
      )}
      <div className="flex gap-2 text-sm">
        {(["overview", "lessons"] as const).map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setTab(k)}
            className={`rounded-lg px-3 py-1.5 capitalize ${
              tab === k ? "bg-zinc-100 text-zinc-950" : "border border-zinc-800 text-zinc-400 hover:border-zinc-600"
            }`}
          >
            {k}
          </button>
        ))}
      </div>

      {tab === "overview" ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["Episodes (7d)", summaryLoading ? "…" : String(summary?.episodes_7d ?? 0)],
              ["Lessons captured (7d)", summaryLoading ? "…" : String(summary?.lessons_captured_7d ?? 0)],
              ["Distinct agents (7d)", summaryLoading ? "…" : String(summary?.distinct_agents_7d ?? 0)],
              ["Lesson rate", summaryLoading ? "…" : `${summary?.lesson_rate_pct ?? 0}%`],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
                <p className="text-xs uppercase tracking-widest text-zinc-500">{label}</p>
                <p className="mt-2 text-2xl font-semibold text-zinc-50">{value}</p>
                              </div>
            ))}
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">30-day activity</h2>
            <div className="h-40 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-3">
              {timelineLoading && !chartData.length ? (
                <p className="text-sm text-zinc-500">Loading…</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <XAxis dataKey="label" tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis width={28} domain={[0, maxY]} tick={{ fill: "#52525b", fontSize: 10 }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }} />
                    <Line type="monotone" dataKey="episodes" name="Episodes" stroke="#a1a1aa" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="lessons" name="Lessons" stroke="#fbbf24" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="agents_involved" name="Agents" stroke="#4ade80" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <CompactTable
              title="Top topics"
              cols={["Topic", "N"]}
              rows={(summary?.top_topics ?? []).slice(0, 5).map((t) => ({
                k: t.topic,
                cells: [t.topic, String(t.count)],
              }))}
            />
            <CompactTable
              title="Top agents"
              cols={["Agent", "N"]}
              rows={(summary?.top_agents ?? []).slice(0, 5).map((a) => ({
                k: a.agent,
                cells: [a.agent, String(a.count)],
              }))}
            />
          </section>

          <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">Recent episodes</h2>
              <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                <span>
                  {page + 1}/{totalPages}
                </span>
                <button
                  type="button"
                  className="rounded border border-zinc-800 px-2 py-1 text-zinc-300 disabled:opacity-40"
                  disabled={page <= 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  Prev
                </button>
                <button
                  type="button"
                  className="rounded border border-zinc-800 px-2 py-1 text-zinc-300 disabled:opacity-40"
                  disabled={page + 1 >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            </div>
            <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead>
                  <tr className="border-b border-zinc-800/80 text-xs uppercase tracking-wider text-zinc-500">
                    {["When", "Actor", "Event", "Tags", "Summary"].map((h) => (
                      <th key={h} className="p-3 font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {episodesLoading ? (
                    <tr>
                      <td colSpan={5} className="p-4 text-zinc-500">
                        Loading…
                      </td>
                    </tr>
                  ) : (episodesPayload?.episodes ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-4 text-zinc-500">
                        No episodes.
                      </td>
                    </tr>
                  ) : (
                    episodesPayload!.episodes.map((r) => (
                      <tr key={r.id} className="border-b border-zinc-800/40 align-top text-zinc-300">
                        <td className="p-3 font-mono text-xs text-zinc-500">{formatLocalDateTime(r.created_at)}</td>
                        <td className="p-3">{r.actor}</td>
                        <td className="p-3 text-xs text-zinc-400">{r.event_type}</td>
                        <td className="p-3 text-xs text-zinc-500">{(r.tags ?? []).join(", ") || "—"}</td>
                        <td className="p-3 text-zinc-400">{r.summary?.slice(0, 240) || "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : (
        <section className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">Lessons</h2>
            <input
              value={lessonSearch}
              onChange={(e) => setLessonSearch(e.target.value)}
              placeholder="Search…"
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:ring-2 focus:ring-zinc-700 sm:max-w-md"
            />
          </div>
          <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-800/80 text-xs uppercase tracking-wider text-zinc-500">
                  {["Lesson", "First seen", "Last seen", "Last confirmed"].map((h) => (
                    <th key={h} className="p-3 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {lessonsLoading ? (
                  <tr>
                    <td colSpan={4} className="p-4 text-zinc-500">
                      Loading…
                    </td>
                  </tr>
                ) : (lessonsPayload?.lessons ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-4 text-zinc-500">
                      No lesson_extracted episodes yet.
                    </td>
                  </tr>
                ) : (
                  lessonsPayload!.lessons.map((l) => (
                    <tr key={l.lesson_key} className="border-b border-zinc-800/40 align-top text-zinc-300">
                      <td className="p-3 text-zinc-200">{l.lesson.slice(0, 400)}</td>
                      <td className="p-3 font-mono text-xs text-zinc-500">{formatLocalDateTime(l.first_seen_at)}</td>
                      <td className="p-3 font-mono text-xs text-zinc-500">{formatLocalDateTime(l.last_seen_at)}</td>
                      <td className="p-3 font-mono text-xs text-zinc-500">{formatLocalDateTime(l.last_confirmed_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function CompactTable(props: { title: string; cols: string[]; rows: { k: string; cells: ReactNode[] }[] }) {
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-500">{props.title}</h3>
      <div className="overflow-hidden rounded-xl border border-zinc-800/80">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-800/80 bg-zinc-900/50 text-xs uppercase tracking-wider text-zinc-500">
              {props.cols.map((c) => (
                <th key={c} className="p-3 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {props.rows.length === 0 ? (
              <tr>
                <td colSpan={props.cols.length} className="p-3 text-zinc-500">
                  No rows.
                </td>
              </tr>
            ) : (
              props.rows.map((r) => (
                <tr key={r.k} className="border-b border-zinc-800/40">
                  {r.cells.map((cell, idx) => (
                    <td key={`${r.k}-${idx}`} className="p-3">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
