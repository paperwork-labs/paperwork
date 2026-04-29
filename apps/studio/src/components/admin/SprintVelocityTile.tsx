import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import type { SprintVelocityEntry, SprintVelocityResponse } from "@/types/sprint-velocity";

function relativeAge(iso?: string): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const diff = Date.now() - t;
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function BarSegment({
  value,
  total,
  color,
  label,
}: {
  value: number;
  total: number;
  color: string;
  label: string;
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  if (pct === 0) return null;
  return (
    <div
      className={`flex h-full items-center justify-center text-[10px] font-semibold text-white ${color}`}
      style={{ width: `${pct}%` }}
      title={`${label}: ${value} (${pct}%)`}
    >
      {pct >= 12 ? `${pct}%` : ""}
    </div>
  );
}

function AuthorBar({ entry }: { entry: SprintVelocityEntry }) {
  const total = entry.prs_merged;
  const founder = entry.by_author.founder;
  const brain = entry.by_author["brain-self-dispatch"];
  const cheap = entry.by_author["cheap-agent"];

  if (total === 0) {
    return (
      <div className="mt-2 h-4 w-full rounded-full bg-zinc-800 text-center text-[10px] leading-4 text-zinc-500">
        no PRs
      </div>
    );
  }

  return (
    <div className="mt-2 flex h-4 w-full overflow-hidden rounded-full">
      <BarSegment value={founder} total={total} color="bg-amber-500" label="Founder" />
      <BarSegment value={brain} total={total} color="bg-blue-500" label="Brain" />
      <BarSegment value={cheap} total={total} color="bg-violet-500" label="Agents" />
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className={`inline-block h-2 w-2 rounded-full ${color}`} />
      <span>{label}</span>
    </span>
  );
}

function VelocityBody({
  data,
  brainConfigured,
}: {
  data: SprintVelocityResponse;
  brainConfigured: boolean;
}) {
  const entry = data.current;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">
            Sprint Velocity
          </p>
          {entry && (
            <p className="mt-0.5 text-[11px] text-zinc-500">
              {entry.week_start} – {entry.week_end}
            </p>
          )}
        </div>
        {!brainConfigured && (
          <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-500">
            Brain offline
          </span>
        )}
        {entry && !entry.measured && (
          <span className="rounded bg-amber-900/40 px-1.5 py-0.5 text-[10px] text-amber-400">
            bootstrap
          </span>
        )}
      </div>

      {!entry ? (
        <p className="mt-3 text-sm text-zinc-500">No velocity data yet.</p>
      ) : (
        <>
          {/* Primary metrics row */}
          <div className="mt-4 grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-zinc-800/60 p-3 text-center">
              <p className="text-2xl font-bold tabular-nums text-white">{entry.prs_merged}</p>
              <p className="mt-0.5 text-[10px] uppercase tracking-wide text-zinc-500">PRs merged</p>
            </div>
            <div className="rounded-lg bg-zinc-800/60 p-3 text-center">
              <p className="text-2xl font-bold tabular-nums text-white">
                {entry.story_points_burned}
              </p>
              <p className="mt-0.5 text-[10px] uppercase tracking-wide text-zinc-500">
                Story pts
              </p>
            </div>
            <div className="rounded-lg bg-zinc-800/60 p-3 text-center">
              <p className="text-2xl font-bold tabular-nums text-white">
                {entry.workstreams_completed}
              </p>
              <p className="mt-0.5 text-[10px] uppercase tracking-wide text-zinc-500">WS done</p>
            </div>
          </div>

          {/* Throughput */}
          <p className="mt-3 text-[11px] text-zinc-500">
            {entry.throughput_per_day.toFixed(2)} PRs/day
          </p>

          {/* Author bar */}
          <AuthorBar entry={entry} />
          <div className="mt-1.5 flex gap-3 text-[10px] text-zinc-500">
            <LegendDot color="bg-amber-500" label={`Founder ×${entry.by_author.founder}`} />
            <LegendDot
              color="bg-blue-500"
              label={`Brain ×${entry.by_author["brain-self-dispatch"]}`}
            />
            <LegendDot
              color="bg-violet-500"
              label={`Agents ×${entry.by_author["cheap-agent"]}`}
            />
          </div>

          {/* Footer */}
          <p className="mt-3 text-[10px] text-zinc-600">
            Computed {relativeAge(entry.computed_at)}
          </p>
        </>
      )}
    </div>
  );
}

function emptyResponse(): SprintVelocityResponse {
  return { current: null, history_last_12: [] };
}

export async function SprintVelocityTile() {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return <VelocityBody data={emptyResponse()} brainConfigured={false} />;
  }

  let data: SprintVelocityResponse = emptyResponse();
  try {
    const res = await fetch(`${auth.root}/admin/sprint-velocity`, {
      headers: { "X-Brain-Secret": auth.secret },
      cache: "no-store",
    });
    if (res.ok) {
      const json = (await res.json()) as { success?: boolean; data?: SprintVelocityResponse };
      if (json.success !== false && json.data != null) {
        data = json.data;
      }
    }
  } catch {
    // Brain unreachable — render empty state
  }

  return <VelocityBody data={data} brainConfigured />;
}
