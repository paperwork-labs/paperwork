import Link from "next/link";
import { ExternalLink, GitMerge, Play, Pause, XCircle } from "lucide-react";

import { loadTrackerIndex, type Sprint } from "@/lib/tracker";

export const dynamic = "force-static";

const STATUS_TONE: Record<
  string,
  { icon: typeof GitMerge; className: string; label: string }
> = {
  shipped: {
    icon: GitMerge,
    className: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
    label: "shipped",
  },
  active: {
    icon: Play,
    className: "text-amber-300 bg-amber-500/10 border-amber-500/30",
    label: "active",
  },
  paused: {
    icon: Pause,
    className: "text-zinc-300 bg-zinc-700/40 border-zinc-700",
    label: "paused",
  },
  abandoned: {
    icon: XCircle,
    className: "text-rose-300 bg-rose-500/10 border-rose-500/30",
    label: "abandoned",
  },
};

function tone(status: string) {
  return STATUS_TONE[status] ?? STATUS_TONE.paused;
}

export default function SprintsPage() {
  const { sprints } = loadTrackerIndex();

  const active: Sprint[] = sprints.filter((s) => s.status === "active");
  const shipped: Sprint[] = sprints.filter((s) => s.status === "shipped");
  const other: Sprint[] = sprints.filter(
    (s) => s.status !== "active" && s.status !== "shipped"
  );

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Sprints</h1>
          <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
            cross-cutting work logs
          </span>
        </div>
        <p className="text-sm text-zinc-400">
          Time-boxed work that touches multiple products / personas / infra layers.
          Sourced from <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs">docs/sprints/</code>{" "}
          and merged with PR data. Per-product roadmaps live under{" "}
          <Link href="/admin/products" className="underline hover:text-zinc-200">
            Products
          </Link>
          ; the company tracker is{" "}
          <Link href="/admin/tasks" className="underline hover:text-zinc-200">
            Tasks
          </Link>
          .
        </p>
      </header>

      <SprintRail title="Active" sprints={active} emptyHint="No active sprints — open one in docs/sprints/." />
      <SprintRail title="Shipped" sprints={shipped} emptyHint="Nothing shipped yet." />
      {other.length > 0 ? (
        <SprintRail title="Paused / abandoned" sprints={other} emptyHint="" />
      ) : null}
    </div>
  );
}

function SprintRail({
  title,
  sprints,
  emptyHint,
}: {
  title: string;
  sprints: Sprint[];
  emptyHint: string;
}) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-100">{title}</h2>
        <span className="text-[10px] uppercase tracking-wide text-zinc-500">
          {sprints.length} sprint{sprints.length === 1 ? "" : "s"}
        </span>
      </div>
      {sprints.length === 0 ? (
        <p className="text-sm text-zinc-500">{emptyHint}</p>
      ) : (
        <ol className="space-y-3">
          {sprints.map((s) => {
            const t = tone(s.status);
            const Icon = t.icon;
            return (
              <li
                key={s.slug}
                className={`rounded-lg border bg-zinc-950/40 p-4 ${t.className.split(" ").filter((c) => c.startsWith("border-")).join(" ")}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-base font-medium text-zinc-100">
                      {s.title}
                    </p>
                    <p className="mt-1 text-xs text-zinc-500">
                      {s.start && s.end ? (
                        <>
                          {s.start} → {s.end}
                          {s.duration_weeks ? <> · {s.duration_weeks} weeks</> : null}
                        </>
                      ) : (
                        <code>{s.path}</code>
                      )}
                    </p>
                  </div>
                  <span
                    className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${t.className}`}
                  >
                    <Icon className="h-3 w-3" />
                    {t.label}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                  {s.owner ? (
                    <span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-sky-300">
                      {s.owner}
                    </span>
                  ) : null}
                  {(s.ships ?? []).map((ship) => (
                    <span
                      key={ship}
                      className="rounded-full bg-zinc-800 px-2 py-0.5 text-zinc-300"
                    >
                      {ship}
                    </span>
                  ))}
                  {(s.personas ?? []).slice(0, 4).map((p) => (
                    <span
                      key={p}
                      className="rounded-full bg-fuchsia-500/10 px-2 py-0.5 text-fuchsia-300"
                    >
                      {p}
                    </span>
                  ))}
                  <span className="ml-auto inline-flex items-center gap-3">
                    {s.pr ? (
                      <a
                        href={s.pr_url ?? "#"}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 transition hover:text-zinc-200"
                      >
                        PR #{s.pr}
                        {s.pr_state ? (
                          <span className="text-[10px] uppercase text-zinc-500">
                            {s.pr_state.toLowerCase()}
                          </span>
                        ) : null}
                      </a>
                    ) : null}
                    <a
                      href={`https://github.com/paperwork-labs/paperwork/blob/main/${s.path}`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 transition hover:text-zinc-200"
                    >
                      Source <ExternalLink className="h-3 w-3" />
                    </a>
                  </span>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
