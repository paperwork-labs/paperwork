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
  CheckCircle2,
  Clock3,
  ChevronDown,
  ArchiveRestore,
} from "lucide-react";

import { loadTrackerIndex, type Sprint } from "@/lib/tracker";
import { SprintMarkdown } from "@/components/sprint/SprintMarkdown";
import {
  findPreviousShippedSprint,
  getDisplayPillStatus,
  isSprintActiveForUi,
  isSprintShippedForUi,
  orderSprintsChronological,
} from "@/lib/sprint-reconcile";
import { buildTracker, type TrackerItem } from "@/lib/sprint-tracker";

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
  in_progress: {
    icon: Play,
    className: "text-amber-300 bg-amber-500/10 border-amber-500/30",
    label: "in progress",
  },
  active: {
    icon: Play,
    className: "text-amber-300 bg-amber-500/10 border-amber-500/30",
    label: "active",
  },
  planned: {
    icon: Play,
    className: "text-sky-200 bg-sky-500/10 border-sky-500/30",
    label: "planned",
  },
  paused: {
    icon: Pause,
    className: "text-zinc-300 bg-zinc-700/40 border-zinc-700",
    label: "paused",
  },
  deferred: {
    icon: Clock3,
    className: "text-zinc-200 bg-fuchsia-500/10 border-fuchsia-500/30",
    label: "deferred",
  },
  dropped: {
    icon: XCircle,
    className: "text-rose-300 bg-rose-500/10 border-rose-500/30",
    label: "dropped",
  },
  abandoned: {
    icon: XCircle,
    className: "text-rose-300 bg-rose-500/10 border-rose-500/30",
    label: "abandoned",
  },
};

function tone(pill: string) {
  const p = (pill || "paused").toLowerCase();
  if (STATUS_TONE[p]) return STATUS_TONE[p]!;
  if (p === "in progress" || p === "in_progress" || p === "active" || p === "planned")
    return STATUS_TONE.in_progress;
  if (p === "on_hold" || p === "on-hold") return STATUS_TONE.paused;
  return STATUS_TONE.paused;
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
  const ordered = orderSprintsChronological(sprints);

  const active: Sprint[] = sprints.filter((s) => isSprintActiveForUi(s));
  const shipped: Sprint[] = sprints.filter((s) => isSprintShippedForUi(s));

  const featured: Sprint | undefined = active[0] ?? shipped[0];
  const remaining = sprints.filter((s) => s.slug !== featured?.slug);
  const remainingActive = remaining.filter((s) => isSprintActiveForUi(s));
  const remainingShipped = remaining.filter((s) => isSprintShippedForUi(s));
  const remainingOther = remaining.filter(
    (s) => !isSprintActiveForUi(s) && !isSprintShippedForUi(s)
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
          <span className="ml-2 text-zinc-500">· click any sprint to expand its full brief</span>
        </p>
      </header>

      {featured ? <FeaturedSprint sprint={featured} allSprints={ordered} /> : null}

      {remainingActive.length > 0 ? (
        <SprintRail
          title="Active"
          sprints={remainingActive}
          allSprints={ordered}
          emptyHint="No other active sprints."
        />
      ) : null}
      {remainingShipped.length > 0 ? (
        <SprintRail
          title="Shipped"
          sprints={remainingShipped}
          allSprints={ordered}
          emptyHint="Nothing else shipped yet."
        />
      ) : null}
      {remainingOther.length > 0 ? (
        <SprintRail
          title="Paused / dropped / other"
          sprints={remainingOther}
          allSprints={ordered}
          emptyHint=""
        />
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

function DeferredFromPreviousSprint({
  sprint,
  allSprints,
}: {
  sprint: Sprint;
  allSprints: Sprint[];
}) {
  const prev = findPreviousShippedSprint(sprint, allSprints);
  if (!prev) return null;
  const carried = buildTracker(prev).filter((i) => i.status === "deferred");
  if (carried.length === 0) return null;
  if (isSprintShippedForUi(sprint)) return null;
  return (
    <div
      className="mt-4 rounded-lg border border-fuchsia-500/30 bg-fuchsia-500/5 p-3 text-sm"
      data-testid="deferred-from-previous"
    >
      <p className="text-[10px] font-medium uppercase tracking-wide text-fuchsia-200/90">
        Deferred from previous sprint
      </p>
      <p className="mt-1 text-xs text-fuchsia-100/80">
        <span className="text-zinc-400">{carried.length} item(s) from </span>
        <span className="font-medium text-fuchsia-100">{prev.title}</span>
        <span className="text-zinc-500"> (see that sprint&rsquo;s follow-ups) · </span>
        <a
          className="text-sky-300 hover:text-sky-200"
          target="_blank"
          rel="noreferrer"
          href={`https://github.com/paperwork-labs/paperwork/blob/main/${encodeURI(prev.path)}`}
        >
          {planLabel(prev.path)}
        </a>
      </p>
    </div>
  );
}

function FeaturedSprint({
  sprint,
  allSprints,
}: {
  sprint: Sprint;
  allSprints: Sprint[];
}) {
  const pill = getDisplayPillStatus(sprint);
  const t = tone(pill);
  const Icon = t.icon;
  const isActive = isSprintActiveForUi(sprint);
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

      <DeferredFromPreviousSprint sprint={sprint} allSprints={allSprints} />

      {sprint.goal ? <SprintMarkdown className="mt-4 max-w-3xl">{sprint.goal}</SprintMarkdown> : null}

      <SprintTagRow sprint={sprint} />
      <SprintBriefBlocks sprint={sprint} />
      <LivingTracker sprint={sprint} />
      <LessonsBlock sprint={sprint} startOpen={isActive} />
    </section>
  );
}

function SprintTagRow({ sprint }: { sprint: Sprint }) {
  if ((sprint.ships ?? []).length === 0 && (sprint.personas ?? []).length === 0) return null;
  return (
    <div className="mt-5 flex flex-wrap items-center gap-2 text-xs">
      {(sprint.ships ?? []).map((ship) => (
        <span key={ship} className="rounded-full bg-zinc-800 px-2 py-0.5 text-zinc-300">
          {ship}
        </span>
      ))}
      {(sprint.personas ?? []).slice(0, 6).map((p) => (
        <span key={p} className="rounded-full bg-fuchsia-500/10 px-2 py-0.5 text-fuchsia-300">
          {p}
        </span>
      ))}
    </div>
  );
}

function SprintBriefBlocks({ sprint }: { sprint: Sprint }) {
  const hasPlans = (sprint.plans ?? []).length > 0;
  const hasPrs = (sprint.related_prs ?? []).length > 0;

  return (
    <div className="mt-6 grid gap-4 lg:grid-cols-3">
      {hasPlans ? (
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

      {hasPrs ? (
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
          title={sprint.path}
          className="group flex min-w-0 items-center gap-1 text-sky-300 hover:text-sky-200"
        >
          <code className="block min-w-0 flex-1 truncate rounded bg-zinc-900/60 px-1.5 py-0.5 text-xs text-sky-300/90 group-hover:text-sky-200">
            {sprint.path}
          </code>
          <ExternalLink className="h-3 w-3 shrink-0" />
        </a>
      </div>
    </div>
  );
}

function LessonsBlock({ sprint, startOpen }: { sprint: Sprint; startOpen?: boolean }) {
  const lessons = sprint.lessons ?? [];
  if (lessons.length === 0) return null;
  return (
    <details
      className="mt-6 rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3"
      {...(startOpen ? { open: true } : {})}
    >
      <summary className="cursor-pointer text-[11px] font-medium uppercase tracking-wide text-zinc-400 hover:text-zinc-200">
        <Lightbulb className="mr-1 inline-block h-3 w-3" /> Lessons learned ({lessons.length})
      </summary>
      <ul className="mt-3 space-y-1.5 text-sm leading-relaxed text-zinc-300">
        {lessons.map((line, i) => (
          <li key={i} className="flex gap-2">
            <span className="mt-2 inline-block h-1 w-1 shrink-0 rounded-full bg-amber-300" />
            <span>{line}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[10px] text-zinc-600">
        Brain ingests these as memory episodes via{" "}
        <code className="rounded bg-zinc-900/60 px-1.5 py-0.5 text-zinc-400">
          scripts/ingest_sprint_lessons.py
        </code>{" "}
        — searchable in chat with the same retrieval that runs on docs.
      </p>
    </details>
  );
}

function LivingTracker({ sprint }: { sprint: Sprint }) {
  const items = buildTracker(sprint);
  if (items.length === 0) return null;

  const shipped = items.filter((i) => i.status === "shipped");
  const pending = items.filter((i) => i.status === "pending");
  const deferred = items.filter((i) => i.status === "deferred");
  const dropped = items.filter((i) => i.status === "dropped");

  return (
    <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-950/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-zinc-400">
          <ArrowRight className="h-3 w-3" /> Living tracker
        </p>
        <p className="text-[10px] uppercase tracking-wide text-zinc-500">
          <span className="text-emerald-300">{shipped.length} shipped</span>
          {pending.length > 0 ? (
            <>
              <span className="mx-1.5 text-zinc-600">·</span>
              <span className="text-amber-300">{pending.length} pending</span>
            </>
          ) : null}
          {deferred.length > 0 ? (
            <>
              <span className="mx-1.5 text-zinc-600">·</span>
              <span className="text-zinc-400">{deferred.length} deferred</span>
            </>
          ) : null}
        </p>
      </div>
      <ol className="space-y-2 text-sm leading-relaxed text-zinc-200">
        {items.map((item, i) => (
          <TrackerRow key={`${item.status}-${i}`} item={item} />
        ))}
      </ol>
      {isSprintShippedForUi(sprint) && deferred.length > 0 ? (
        <p className="mt-3 text-[10px] text-zinc-600">
          {deferred.length} item{deferred.length === 1 ? "" : "s"} did not land in this sprint and were
          deferred to a successor — not actionable here.
        </p>
      ) : (
        <p className="mt-3 text-[10px] text-zinc-600">
          Promote a follow-up:{" "}
          <code className="rounded bg-zinc-900/60 px-1.5 py-0.5 text-zinc-400">
            scripts/sprint_promote_followup.py {sprint.path} &lt;match&gt; --pr &lt;n&gt;
          </code>
        </p>
      )}
    </div>
  );
}

const TRACKER_ROW_TONE: Record<
  TrackerItem["status"],
  { icon: typeof CheckCircle2; iconColor: string; pillClass: string; textColor: string }
> = {
  shipped: {
    icon: CheckCircle2,
    iconColor: "text-emerald-400",
    pillClass: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
    textColor: "text-zinc-200",
  },
  pending: {
    icon: Clock3,
    iconColor: "text-amber-300",
    pillClass: "bg-amber-500/10 text-amber-300 border-amber-500/30",
    textColor: "text-zinc-200",
  },
  deferred: {
    icon: ArchiveRestore,
    iconColor: "text-zinc-500",
    pillClass: "bg-zinc-700/40 text-zinc-400 border-zinc-700",
    textColor: "text-zinc-400",
  },
  dropped: {
    icon: XCircle,
    iconColor: "text-rose-300",
    pillClass: "bg-rose-500/10 text-rose-300 border-rose-500/30",
    textColor: "text-rose-200/80",
  },
};

function TrackerRow({ item }: { item: TrackerItem }) {
  const { icon: Icon, iconColor, pillClass, textColor } = TRACKER_ROW_TONE[item.status];

  return (
    <li className="flex items-start gap-2.5">
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${iconColor}`} />
      <div className="min-w-0 flex-1">
        <p className={textColor}>{item.text}</p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wide">
          <span className={`rounded-full border px-1.5 py-0.5 ${pillClass}`}>
            {item.status === "deferred"
              ? "deferred to follow-up"
              : item.status === "dropped"
                ? "dropped"
                : item.status}
          </span>
          {item.date ? <span className="text-zinc-500">{item.date}</span> : null}
          {item.pr ? (
            <a
              href={prUrl(item.pr)}
              target="_blank"
              rel="noreferrer"
              className="text-sky-300 hover:text-sky-200"
            >
              PR #{item.pr}
            </a>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function SprintRail({
  title,
  sprints,
  allSprints,
  emptyHint,
}: {
  title: string;
  sprints: Sprint[];
  allSprints: Sprint[];
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
          {sprints.map((s) => (
            <ExpandableSprintCard key={s.slug} sprint={s} allSprints={allSprints} />
          ))}
        </ol>
      )}
    </section>
  );
}

function ExpandableSprintCard({
  sprint,
  allSprints,
}: {
  sprint: Sprint;
  allSprints: Sprint[];
}) {
  const pill = getDisplayPillStatus(sprint);
  const t = tone(pill);
  const Icon = t.icon;
  const tracker = buildTracker(sprint);
  const shippedCount = tracker.filter((i) => i.status === "shipped").length;
  const pendingCount = tracker.filter((i) => i.status === "pending").length;
  const deferredCount = tracker.filter((i) => i.status === "deferred").length;
  const droppedCount = tracker.filter((i) => i.status === "dropped").length;
  const lessonsCount = (sprint.lessons ?? []).length;
  const borderTone = t.className.split(" ").filter((c) => c.startsWith("border-")).join(" ");

  return (
    <li className={`rounded-lg border bg-zinc-950/40 ${borderTone}`}>
      <details className="group overflow-hidden">
        <summary className="flex cursor-pointer list-none items-start justify-between gap-3 p-4 transition hover:bg-zinc-900/40">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <ChevronDown className="h-4 w-4 shrink-0 -rotate-90 text-zinc-500 transition-transform group-open:rotate-0" />
              <p className="truncate text-base font-medium text-zinc-100">{sprint.title}</p>
            </div>
            <p className="mt-1 ml-6 text-xs text-zinc-500">
              {sprint.start && sprint.end ? (
                <>
                  {sprint.start} → {sprint.end}
                  {sprint.duration_weeks ? <> · {sprint.duration_weeks} weeks</> : null}
                </>
              ) : (
                <code>{sprint.path}</code>
              )}
              {tracker.length > 0 ? (
                <span className="ml-2 text-zinc-600">
                  ·{" "}
                  <span className="text-emerald-300">{shippedCount} shipped</span>
                  {pendingCount > 0 ? (
                    <>
                      <span className="mx-1 text-zinc-600">/</span>
                      <span className="text-amber-300">{pendingCount} pending</span>
                    </>
                  ) : null}
                  {deferredCount > 0 ? (
                    <>
                      <span className="mx-1 text-zinc-600">/</span>
                      <span className="text-zinc-400">{deferredCount} deferred</span>
                    </>
                  ) : null}
                  {droppedCount > 0 ? (
                    <>
                      <span className="mx-1 text-zinc-600">/</span>
                      <span className="text-rose-200/80">{droppedCount} dropped</span>
                    </>
                  ) : null}
                </span>
              ) : null}
              {lessonsCount > 0 ? (
                <span className="ml-2 text-amber-300/80">
                  · {lessonsCount} lesson{lessonsCount === 1 ? "" : "s"}
                </span>
              ) : null}
            </p>
            {sprint.goal ? (
              <p className="mt-2 ml-6 line-clamp-2 max-w-3xl text-xs leading-relaxed text-zinc-400 group-open:line-clamp-none group-open:text-zinc-300">
                {sprint.goal}
              </p>
            ) : null}
            <div className="mt-2 ml-6 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
              {(sprint.ships ?? []).map((ship) => (
                <span key={ship} className="rounded-full bg-zinc-800 px-2 py-0.5 text-zinc-300">
                  {ship}
                </span>
              ))}
              {(sprint.personas ?? []).slice(0, 4).map((p) => (
                <span
                  key={p}
                  className="rounded-full bg-fuchsia-500/10 px-2 py-0.5 text-fuchsia-300"
                >
                  {p}
                </span>
              ))}
            </div>
          </div>
          <span
            className={`inline-flex shrink-0 items-center gap-1 self-start rounded-full px-2 py-0.5 text-[10px] font-medium ${t.className}`}
          >
            <Icon className="h-3 w-3" />
            {t.label}
          </span>
        </summary>

        <div className="border-t border-zinc-800/60 bg-zinc-950/30 px-4 pb-4 pt-2">
          <DeferredFromPreviousSprint sprint={sprint} allSprints={allSprints} />
          <SprintBriefBlocks sprint={sprint} />
          <LivingTracker sprint={sprint} />
          <LessonsBlock sprint={sprint} />
        </div>
      </details>
    </li>
  );
}
