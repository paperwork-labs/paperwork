import Link from "next/link";

import { Badge, Card, CardContent, cn } from "@paperwork-labs/ui";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import type { EmployeeListItem } from "@/lib/brain-client";

function peopleDirectorySubtitle(): string {
  return "Live roster from Brain (unified employees API), grouped by team. Use Workspace for persona specs, dispatch context, and tooling.";
}

export function PeopleDirectoryHeader() {
  return (
    <HqPageHeader
      title="People"
      subtitle={peopleDirectorySubtitle()}
      breadcrumbs={[
        { label: "Admin", href: "/admin" },
        { label: "People" },
      ]}
    />
  );
}

export function PeopleDirectoryBrainError({ message }: { message: string }) {
  return (
    <div className="space-y-8">
      <PeopleDirectoryHeader />
      <div
        className="rounded-lg border border-red-700/50 bg-red-950/25 px-4 py-3 text-sm text-red-200"
        role="alert"
      >
        <span className="font-semibold">Unable to load org directory —</span>{" "}
        <span className="text-red-100/90">{message}</span>
        <p className="mt-2 text-xs text-red-300/80">
          No roster is shown until Brain returns employee data. Check{" "}
          <span className="font-mono">BRAIN_API_URL</span> /{" "}
          <span className="font-mono">BRAIN_API_SECRET</span> and the{" "}
          <span className="font-mono">/admin/employees</span> route.
        </p>
      </div>
    </div>
  );
}

function isFounderHighlight(e: EmployeeListItem): boolean {
  if (e.slug.toLowerCase() === "founder") return true;
  return e.kind === "human" && e.reports_to === null;
}

function employeeLabel(e: EmployeeListItem): string {
  return e.display_name ?? e.role_title;
}

function sortByLabel(a: EmployeeListItem, b: EmployeeListItem): number {
  return employeeLabel(a).localeCompare(employeeLabel(b), undefined, {
    sensitivity: "base",
  });
}

function sortTeamNames(teams: Set<string>): string[] {
  const list = [...teams];
  const exec = "Executive Council";
  const hasExec = list.includes(exec);
  const rest = list.filter((t) => t !== exec).sort((a, b) => a.localeCompare(b));
  return hasExec ? [exec, ...rest] : rest;
}

function EmployeeNamedStatus({ namedAt }: { namedAt: string | null }) {
  const named = namedAt !== null && namedAt !== "";
  return (
    <span
      className={cn(
        "absolute right-3 top-3 h-2 w-2 shrink-0 rounded-full ring-2 ring-zinc-950",
        named ? "bg-emerald-400" : "bg-zinc-600",
      )}
      title={named ? "Named" : "Not yet named"}
      aria-label={named ? "Named" : "Not yet named"}
    />
  );
}

function EmployeeCard({
  employee: e,
  founder = false,
}: {
  employee: EmployeeListItem;
  founder?: boolean;
}) {
  const title = employeeLabel(e);
  return (
    <Link
      href={`/admin/people/${encodeURIComponent(e.slug)}`}
      className={cn("group block min-w-[200px] max-w-md")}
    >
      <Card
        className={cn(
          "relative h-full min-h-[120px] border-zinc-800/90 bg-zinc-900/40 text-zinc-100 shadow-none motion-safe:transition-colors",
          "hover:border-zinc-600/80 hover:bg-zinc-900/70",
          founder &&
            "min-h-[140px] border-amber-600/35 bg-zinc-900/60 ring-1 ring-amber-500/25",
        )}
      >
        <CardContent className={cn("p-3", founder && "pb-4 pt-4")}>
          <EmployeeNamedStatus namedAt={e.named_at} />
          <div className="flex gap-3 pr-4">
            <span
              className={cn(
                "select-none leading-none text-zinc-100",
                founder ? "text-4xl" : "text-2xl",
              )}
              aria-hidden
            >
              {e.avatar_emoji ?? "◇"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-zinc-100 group-hover:text-white">
                {title}
              </p>
              <p className="truncate text-xs text-zinc-500">{e.role_title}</p>
              {e.tagline ? (
                <p className="mt-1 line-clamp-2 text-xs italic text-zinc-500">{e.tagline}</p>
              ) : (
                <p className="mt-1 text-xs italic text-zinc-600">—</p>
              )}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Badge
              variant="outline"
              className="border-zinc-700 bg-zinc-950/40 text-[10px] font-medium text-zinc-400"
            >
              {e.team}
            </Badge>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

export function EmployeeOrgGrid({ employees }: { employees: EmployeeListItem[] }) {
  const founders = employees.filter(isFounderHighlight).sort(sortByLabel);
  const founderSlugs = new Set(founders.map((f) => f.slug));
  const rest = employees.filter((e) => !founderSlugs.has(e.slug));

  const byTeam = new Map<string, EmployeeListItem[]>();
  for (const e of rest) {
    const team = e.team.trim() || "Ungrouped";
    const bucket = byTeam.get(team);
    if (bucket) bucket.push(e);
    else byTeam.set(team, [e]);
  }
  for (const [, list] of byTeam) {
    list.sort(sortByLabel);
  }

  const teamOrder = sortTeamNames(new Set(byTeam.keys()));

  return (
    <div className="space-y-10">
      <PeopleDirectoryHeader />

      {founders.length > 0 ? (
        <section aria-label="Leadership">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">
            Founder
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {founders.map((e) => (
              <EmployeeCard key={e.slug} employee={e} founder />
            ))}
          </div>
        </section>
      ) : null}

      <div className="grid gap-10 lg:grid-cols-2 xl:grid-cols-3">
        {teamOrder.map((team) => {
          const members = byTeam.get(team);
          if (!members?.length) return null;
          return (
            <section key={team} aria-label={team}>
              <h2 className="mb-3 border-b border-zinc-800/80 pb-2 text-sm font-semibold text-zinc-200">
                {team}
              </h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {members.map((e) => (
                  <EmployeeCard key={e.slug} employee={e} />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
