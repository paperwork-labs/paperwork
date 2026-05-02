import Link from "next/link";
import type { CSSProperties } from "react";

import { Badge, Card, CardContent, cn } from "@paperwork-labs/ui";

import { HqMissingCredCard } from "@/components/admin/hq/HqMissingCredCard";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";
import { BrainClient, BrainClientError, type EmployeeListItem } from "@/lib/brain-client";

export const dynamic = "force-dynamic";

export const metadata = { title: "Circles — Studio" };

/** Preferred org chart ordering; remaining teams sort after this list. */
const KNOWN_TEAM_ORDER = [
  "Executive Council",
  "Engineering",
  "Finance",
  "Legal & Compliance",
  "Growth",
  "Trading",
  "Product",
] as const;

function normalizeTeamName(team: string | null | undefined): string {
  const t = typeof team === "string" ? team.trim() : "";
  return t.length > 0 ? t : "Unassigned";
}

function sortTeamKeys(teams: string[]): string[] {
  const set = new Set(teams);
  const ordered: string[] = [];
  for (const k of KNOWN_TEAM_ORDER) {
    if (set.has(k)) ordered.push(k);
  }
  const known = new Set<string>(KNOWN_TEAM_ORDER);
  const rest = teams.filter((t) => !known.has(t));
  rest.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  return [...ordered, ...rest];
}

function hashTeamHue(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i += 1) {
    h = (h * 31 + name.charCodeAt(i)) >>> 0;
  }
  return h % 360;
}

function teamAccentStyle(teamName: string): CSSProperties {
  const hue = hashTeamHue(teamName);
  return {
    ["--team-accent" as string]: `hsl(${hue} 72% 56%)`,
    ["--team-accent-glow" as string]: `hsl(${hue} 65% 45% / 0.35)`,
  };
}

function memberLabel(e: EmployeeListItem): string {
  const d = e.display_name?.trim();
  if (d) return d;
  return e.role_title?.trim() || e.slug;
}

function buildDirectReportSet(employees: EmployeeListItem[]): Set<string> {
  const hasDirects = new Set<string>();
  for (const e of employees) {
    const mgr = e.reports_to?.trim();
    if (mgr) hasDirects.add(mgr);
  }
  return hasDirects;
}

function isLeadInTeam(member: EmployeeListItem, hasDirectReports: Set<string>): boolean {
  return hasDirectReports.has(member.slug);
}

function slugifyTeamId(teamName: string): string {
  return teamName
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");
}

function groupByTeam(employees: EmployeeListItem[]): Map<string, EmployeeListItem[]> {
  const map = new Map<string, EmployeeListItem[]>();
  for (const e of employees) {
    const team = normalizeTeamName(e.team);
    const list = map.get(team);
    if (list) list.push(e);
    else map.set(team, [e]);
  }
  for (const [, members] of map) {
    members.sort((a, b) => memberLabel(a).localeCompare(memberLabel(b), undefined, { sensitivity: "base" }));
  }
  return map;
}

function computeOrgStats(employees: EmployeeListItem[], byTeam: Map<string, EmployeeListItem[]>) {
  const human = employees.filter((e) => e.kind === "human").length;
  const aiAutomated = employees.length - human;
  let largestTeam = "";
  let largestCount = 0;
  for (const [team, members] of byTeam) {
    if (members.length > largestCount) {
      largestCount = members.length;
      largestTeam = team;
    }
  }
  return {
    teamCount: byTeam.size,
    totalEmployees: employees.length,
    human,
    aiAutomated,
    largestTeam: largestCount > 0 ? `${largestTeam} (${largestCount})` : "—",
  };
}

export default async function AdminCirclesPage() {
  const client = BrainClient.fromEnv();

  const header = (
    <HqPageHeader
      title="Circles"
      subtitle="Company structure — teams from Brain (/admin/employees), with leads inferred from reporting lines."
      breadcrumbs={[
        { label: "Admin", href: "/admin" },
        { label: "Circles" },
      ]}
    />
  );

  if (!client) {
    return (
      <div className="space-y-8" data-testid="admin-circles-page">
        {header}
        <HqMissingCredCard
          service="Brain admin API"
          envVar="BRAIN_API_SECRET"
          description="Set BRAIN_API_URL and BRAIN_API_SECRET in Vercel / Render, redeploy, then reload. Circles aggregates GET /admin/employees."
          reconnectAction={{
            label: "Open environment docs",
            href: "https://vercel.com/docs/projects/environment-variables",
          }}
        />
      </div>
    );
  }

  let employees: EmployeeListItem[];
  try {
    employees = await client.getEmployees();
  } catch (err) {
    const message =
      err instanceof BrainClientError
        ? err.message
        : err instanceof Error
          ? err.message
          : "Unknown error talking to Brain";

    return (
      <div className="space-y-8" data-testid="admin-circles-page">
        {header}
        <HqMissingCredCard
          service="Brain admin API"
          envVar="BRAIN_API_URL"
          description={`Brain did not return employees (${message}). Check Brain health and credentials; then redeploy or refresh.`}
        />
      </div>
    );
  }

  const hasDirectReports = buildDirectReportSet(employees);
  const byTeam = groupByTeam(employees);
  const teamKeys = sortTeamKeys([...byTeam.keys()]);
  const stats = computeOrgStats(employees, byTeam);

  return (
    <div className="space-y-8" data-testid="admin-circles-page">
      {header}

      <section
        className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"
        aria-label="Organization summary"
        data-testid="circles-org-stats"
      >
        <HqStatCard variant="compact" label="Teams" value={stats.teamCount} />
        <HqStatCard variant="compact" label="Employees" value={stats.totalEmployees} />
        <HqStatCard variant="compact" label="Humans" value={stats.human} status="info" />
        <HqStatCard variant="compact" label="AI & system" value={stats.aiAutomated} />
        <HqStatCard variant="compact" label="Largest team" value={stats.largestTeam} />
      </section>

      <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {teamKeys.map((teamName) => {
          const members = byTeam.get(teamName) ?? [];
          const accent = teamAccentStyle(teamName);
          const tid = slugifyTeamId(teamName);

          return (
            <li key={teamName}>
              <Card
                data-testid={`team-circle-${tid}`}
                className={cn(
                  "h-full overflow-hidden border-zinc-800/90 bg-zinc-950 shadow-sm",
                  "border-l-[3px] border-l-[var(--team-accent)]",
                )}
                style={{
                  ...accent,
                  boxShadow: "0 0 0 1px rgb(24 24 27 / 0.55), 0 12px 40px -20px var(--team-accent-glow)",
                }}
              >
                <CardContent className="space-y-4 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-2 border-b border-zinc-800/80 pb-4">
                    <div className="min-w-0">
                      <h2 className="truncate text-lg font-semibold tracking-tight text-zinc-100">{teamName}</h2>
                    </div>
                    <Badge variant="secondary" className="shrink-0 border-zinc-700 bg-zinc-900/90 text-zinc-300">
                      {members.length} {members.length === 1 ? "member" : "members"}
                    </Badge>
                  </div>

                  <ul className="space-y-1.5">
                    {members.map((member) => {
                      const lead = isLeadInTeam(member, hasDirectReports);
                      const emoji = member.avatar_emoji?.trim() || "◯";
                      return (
                        <li key={member.slug}>
                          <Link
                            href={`/admin/people/${encodeURIComponent(member.slug)}`}
                            className={cn(
                              "flex items-center gap-2 rounded-lg px-2 py-2 text-sm transition-colors",
                              "bg-zinc-950/65 hover:bg-zinc-900/95",
                              lead &&
                                "ring-1 ring-amber-400/35 bg-amber-950/[0.22] hover:bg-amber-950/35",
                            )}
                          >
                            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-zinc-900 text-base leading-none ring-1 ring-zinc-800">
                              <span aria-hidden>{emoji}</span>
                            </span>
                            <span className="min-w-0 flex-1 truncate text-zinc-200">{memberLabel(member)}</span>
                            {lead ? (
                              <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wide text-amber-200/90">
                                Lead
                              </span>
                            ) : null}
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </CardContent>
              </Card>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
