import Link from "next/link";
import {
  ExternalLink,
  GitMerge,
  Play,
  Pause,
  XCircle,
  FileText,
  Lightbulb,
  ArrowRight,
} from "lucide-react";

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

function prUrl(num: number): string {
  return `https://github.com/paperwork-labs/paperwork/pull/${num}`;
}

function planLabel(plan: string): string {
  const base = plan.split("/").pop() ?? plan;
  return base.replace(/\.md$/i, "");
}

function planUrl(plan: string): string {
  return `https://github.com/paperwork-labs/paperwork/blob/main/${plan}`;
}

export default function SprintsPage() {
  const { sprints } = loadTrackerIndex();

  const active: Sprint[] = sprints.filter((s) => s.status === "active");
  const shipped: Sprint[] = sprints.filter((s) => s.status === "shipped");
  const other: Sprint[] = sprints.filter(
    (s) => s.status !== "active" && s.status !== "shipped"
  );

  const featured: Sprint | undefined = active[0] ?? shipped[0];
  const remaining = sprints.filter((s) => s.slug !== featured?.slug);
  const remainingActive = remaining.filter((s) => s.status === "active");
  const remainingShipped = remaining.filter((s) => s.status === "shipped");
  const remainingOther = remaining.filter(
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
          Each sprint links the plan that was used and the PRs that landed.
          Sourced from{" "}
          <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs">
            docs/sprints/
          </code>
          . Per-product roadmaps live under{" "}
          <Link href="/admin/products" className="underline hover:text-zinc-200">
            Products
          </Link>
          ; the company tracker is{" "}
          <Link href="/admin/tasks" className="underline hover:text-zinc-200">
            Tasks
          </Link>
          .{" "}
          {active.length > 0 ? (
            <span className="text-amber-300">
              {active.length} active · {shipped.length} shipped
            </span>
          ) : (
            <span>{shipped.length} shipped</span>
          )}
        </p>
      </header>

      {featured ? <FeaturedSprint sprint={featured} /> : null}

      {remainingActive.length > 0 ? (
        <SprintRail
          title="Active"
          sprints={remainingActive}
          emptyHint="No other active sprints."
        />
      ) : null}
      {remainingShipped.length > 0 ? (
        <SprintRail
          title="Shipped"
          sprints={remainingShipped}
          emptyHint="Nothing else shipped yet."
        />
      ) : null}
      {remainingOther.length > 0 ? (
        <SprintRail title="Paused / abandoned" sprints={remainingOther} emptyHint="" />
      ) : null}

      {sprints.length === 0 ? (
        <p className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 text-sm text-zinc-500">
          No sprint logs yet. Drop a markdown file in{" "}
          <code>docs/sprints/</code> following the schema in{" "}
          <code>docs/sprints/README.md</code>.
        </p>
      ) : null}
    </div>
  );
}

function FeaturedSprint({ sprint }: { sprint: Sprint }) {
  const t = tone(sprint.status);
  const Icon = t.icon;
  const isActive = sprint.status === "active";
  const headerClass = isActive
    ? "border-amber-500/40 bg-gradient-to-br from-amber-500/10 via-zinc-900/60 to-zinc-900/60"
    : "border-emerald-500/30 bg-gradient-to-br from-emerald-500/10 via-zinc-900/60 to-zinc-900/60";

  return (
    <section className={`rounded-2xl border p-6 ${headerClass}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">
            {isActive ? "Current sprint" : "Latest sprint"}
          </p>
          <h2 className="text-xl font-semibold text-zinc-50">{sprint.title}</h2>
          <p className="text-xs text-zinc-400">
            {sprint.start && sprint.end ? (
              <>
                {sprint.start} → {sprint.end}
                {sprint.duration_weeks ? (
                  <> · {sprint.duration_weeks} week{sprint.duration_weeks === 1 ? "" : "s"}</>
                ) : null}
              </>
            ) : (
              <code>{sprint.path}</code>
            )}
            {sprint.owner ? <> · owner {sprint.owner}</> : null}
          </p>
        </div>
        <span
          className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium ${t.className}`}
        >
          <Icon className="h-3.5 w-3.5" />
          {t.label}
        </span>
      </div>

      {sprint.goal ? (
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-zinc-200">
          {sprint.goal}
        </p>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center gap-2 text-xs">
        {(sprint.ships ?? []).map((ship) => (
          <span
            key={ship}
            className="rounded-full bg-zinc-800 px-2 py-0.5 text-zinc-300"
          >
            {ship}
          </span>
        ))}
        {(sprint.personas ?? []).slice(0, 6).map((p) => (
          <span
            key={p}
            className="rounded-full bg-fuchsia-500/10 px-2 py-0.5 text-fuchsia-300"
          >
            {p}
          </span>
        ))}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        {(sprint.plans ?? []).length > 0 ? (
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
            <p className="mb-2 flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-zinc-500">
              <FileText className="h-3 w-3" /> Plan
            </p>
            <ul className="space-y-1.5 text-sm">
              {(sprint.plans ?? []).map((plan) => (
                <li key={plan}>
                  <a
                    href={planUrl(plan)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-sky-300 hover:text-sky-200"
                  >
                    {planLabel(plan)}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {(sprint.related_prs ?? []).length > 0 ? (
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
            <p className="mb-2 flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-zinc-500">
              <GitMerge className="h-3 w-3" /> PRs that landed
            </p>
            <ul className="space-y-1.5 text-sm">
              {(sprint.related_prs ?? []).map((num) => (
                <li key={num}>
                  <a
                    href={prUrl(num)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-zinc-200 hover:text-zinc-50"
                  >
                    PR #{num}
                    {sprint.pr === num && sprint.pr_state ? (
                      <span className="text-[10px] uppercase text-zinc-500">
                        {sprint.pr_state.toLowerCase()}
                      </span>
                    ) : null}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
          <p className="mb-2 flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-zinc-500">
            <ArrowRight className="h-3 w-3" /> Source
          </p>
          <a
            href={`https://github.com/paperwork-labs/paperwork/blob/main/${sprint.path}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-sm text-sky-300 hover:text-sky-200"
          >
            <code className="text-xs">{sprint.path}</code>
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      {(sprint.outcome_bullets ?? []).length > 0 ? (
        <div className="mt-6">
          <p className="mb-2 text-[10px] uppercase tracking-wide text-zinc-500">
            Outcome
          </p>
          <ul className="space-y-1.5 text-sm leading-relaxed text-zinc-200">
            {(sprint.outcome_bullets ?? []).slice(0, 6).map((line, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-2 inline-block h-1 w-1 shrink-0 rounded-full bg-emerald-400" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {(sprint.lessons ?? []).length > 0 ? (
        <details className="mt-6 rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3">
          <summary className="cursor-pointer text-[11px] font-medium uppercase tracking-wide text-zinc-400 hover:text-zinc-200">
            <Lightbulb className="mr-1 inline-block h-3 w-3" /> Lessons learned ({(sprint.lessons ?? []).length})
          </summary>
          <ul className="mt-3 space-y-1.5 text-sm leading-relaxed text-zinc-300">
            {(sprint.lessons ?? []).map((line, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-2 inline-block h-1 w-1 shrink-0 rounded-full bg-amber-300" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
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
                    {(s.related_prs ?? []).slice(0, 3).map((num) => (
                      <a
                        key={num}
                        href={prUrl(num)}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 transition hover:text-zinc-200"
                      >
                        #{num}
                      </a>
                    ))}
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
