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
        named ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.45)]" : "bg-zinc-600",
      )}
      title={named ? "Named" : "Not yet named"}
      aria-label={named ? "Named" : "Not yet named"}
    />
  );
}

function FounderOrgCard({ employee: e }: { employee: EmployeeListItem }) {
  const title = employeeLabel(e);
  return (
    <Link href={`/admin/people/${encodeURIComponent(e.slug)}`} className="group mx-auto block w-full max-w-lg">
      <Card
        className={cn(
          "relative overflow-hidden border-2 border-amber-500/40 bg-gradient-to-b from-zinc-900/90 to-zinc-950/95 text-zinc-100 shadow-none",
          "ring-2 ring-amber-400/15 ring-offset-2 ring-offset-zinc-950",
          "motion-safe:transition-[border-color,box-shadow] hover:border-amber-400/55 hover:ring-amber-300/25",
        )}
      >
        <CardContent className="relative px-8 pb-8 pt-8 text-center md:px-10 md:pb-10 md:pt-10">
          <EmployeeNamedStatus namedAt={e.named_at} />
          <span className="mb-4 block select-none text-5xl leading-none md:text-6xl" aria-hidden>
            {e.avatar_emoji ?? "◇"}
          </span>
          <p className="text-xl font-semibold tracking-tight text-zinc-50 group-hover:text-white md:text-2xl">
            {title}
          </p>
          <p className="mt-1 text-xs font-medium uppercase tracking-wider text-amber-500/85">
            Founder
          </p>
          {e.role_title ? (
            <p className="mt-2 text-sm text-zinc-400">{e.role_title}</p>
          ) : null}
          {e.tagline ? (
            <p className="mx-auto mt-4 max-w-md text-sm leading-relaxed text-zinc-400">{e.tagline}</p>
          ) : (
            <p className="mt-4 text-sm italic text-zinc-600">—</p>
          )}
          <div className="mt-6 flex justify-center">
            <Badge
              variant="outline"
              className="border-amber-700/40 bg-amber-950/30 text-[11px] font-medium text-amber-200/90"
            >
              {e.team}
            </Badge>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function TeamMemberCard({ employee: e }: { employee: EmployeeListItem }) {
  const primary = employeeLabel(e);
  const showRoleSubtitle = Boolean(e.role_title && e.role_title !== primary);

  return (
    <Link href={`/admin/people/${encodeURIComponent(e.slug)}`} className="group block min-w-0">
      <Card
        className={cn(
          "relative h-full min-h-[124px] border border-zinc-800 bg-zinc-950/60 text-zinc-100 shadow-none",
          "motion-safe:transition-colors hover:border-zinc-600 hover:bg-zinc-900/55",
        )}
      >
        <CardContent className="p-4">
          <EmployeeNamedStatus namedAt={e.named_at} />
          <div className="flex gap-3 pr-5">
            <span className="select-none text-3xl leading-none text-zinc-100" aria-hidden>
              {e.avatar_emoji ?? "◇"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-zinc-100 group-hover:text-white">{primary}</p>
              {showRoleSubtitle ? (
                <p className="truncate text-xs text-zinc-500">{e.role_title}</p>
              ) : null}
              {e.tagline ? (
                <p className="mt-2 line-clamp-2 text-xs leading-snug text-zinc-500">{e.tagline}</p>
              ) : (
                <p className="mt-2 text-xs italic text-zinc-600">—</p>
              )}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Badge
              variant="outline"
              className="border-zinc-700 bg-zinc-950/80 text-[10px] font-medium text-zinc-400"
            >
              {e.team}
            </Badge>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function slugifyTeam(team: string): string {
  return team.replace(/\s+/g, "-").replace(/[^a-zA-Z0-9_-]/g, "");
}

/** Decorative founder → teams connectors (CSS-only). */
function OrgChartConnectors() {
  return (
    <div className="pointer-events-none relative flex w-full max-w-5xl flex-col items-center select-none">
      <div
        className="h-10 w-px shrink-0 bg-gradient-to-b from-amber-600/35 via-zinc-600 to-zinc-700"
        aria-hidden
      />
      <div className="relative flex w-[min(100%,42rem)] items-center">
        <div className="h-px flex-1 bg-zinc-700/85" aria-hidden />
        <div
          className="mx-2 size-2 shrink-0 rounded-full border border-zinc-600 bg-zinc-800 shadow-inner shadow-black/40"
          aria-hidden
        />
        <div className="h-px flex-1 bg-zinc-700/85" aria-hidden />
      </div>
      <div className="h-8 w-px shrink-0 bg-zinc-700/90" aria-hidden />
    </div>
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
  const hasTeamMembers = teamOrder.some((t) => (byTeam.get(t)?.length ?? 0) > 0);

  return (
    <div className="space-y-10">
      <PeopleDirectoryHeader />

      <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-5 shadow-inner shadow-black/20 ring-1 ring-zinc-800/80 md:p-8">
        <div className="flex flex-col items-center">
          {founders.length > 0 ? (
            <section aria-label="Leadership" className="w-full">
              <h2 className="sr-only">Leadership</h2>
              <div className="flex flex-col items-center gap-2">
                {founders.map((e) => (
                  <FounderOrgCard key={e.slug} employee={e} />
                ))}
              </div>
            </section>
          ) : null}

          {founders.length > 0 && hasTeamMembers ? <OrgChartConnectors /> : null}

          {hasTeamMembers ? (
            <div
              className={cn("w-full space-y-12", founders.length > 0 ? "pt-2" : "pt-0")}
            >
              <div className="flex items-center gap-3 px-1">
                <div className="h-px flex-1 bg-zinc-800" aria-hidden />
                <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
                  Teams
                </span>
                <div className="h-px flex-1 bg-zinc-800" aria-hidden />
              </div>

              {teamOrder.map((team) => {
                const members = byTeam.get(team);
                if (!members?.length) return null;
                return (
                  <section key={team} aria-label={team} className="relative">
                    <div className="mb-4 flex flex-wrap items-center gap-3">
                      <span
                        className="rounded-md border border-zinc-700/90 bg-zinc-900/50 px-2.5 py-1 text-xs font-semibold text-zinc-200"
                        id={`team-heading-${slugifyTeam(team)}`}
                      >
                        {team}
                      </span>
                      <span className="text-[11px] text-zinc-600">{members.length} members</span>
                    </div>
                    <div
                      className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3"
                      aria-labelledby={`team-heading-${slugifyTeam(team)}`}
                    >
                      {members.map((e) => (
                        <TeamMemberCard key={e.slug} employee={e} />
                      ))}
                    </div>
                  </section>
                );
              })}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
