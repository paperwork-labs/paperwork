"use client";

import Link from "next/link";
import { type ReactNode } from "react";

import { MessageSquare, Radio } from "lucide-react";

import { Badge, Card, CardContent, cn } from "@paperwork-labs/ui";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { TabbedPageShell, type StudioTabDef } from "@/components/layout/TabbedPageShellNext";
import { SprintMarkdown } from "@/components/sprint/SprintMarkdown";
import type { EmployeeActivityPayload, EmployeeDetail } from "@/lib/brain-client";

import { EmployeeNamingCeremonyButton } from "./employee-naming-ceremony-button";

export type EmployeeProfileTabId = "overview" | "config" | "ownership" | "activity";

function ruleViewerHref(rule: string): string {
  const t = rule.trim();
  const file = t.endsWith(".mdc") ? t : `${t}.mdc`;
  return `/admin/.cursor/rules/${encodeURIComponent(file)}`;
}

function kindBadgeLabel(kind: string): string {
  if (kind === "ai_persona") return "AI persona";
  if (kind === "human") return "Human";
  if (kind === "system") return "System";
  return kind.replace(/_/g, " ");
}

function formatNamedAt(iso: string | null): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

/** Relative label for timeline rows ("2 hours ago", "yesterday"). */
function formatActivityRelative(iso: string | null): string {
  if (!iso) return "unknown time";
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return iso;
  const diffMs = Date.now() - ts;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) {
    return minutes === 1 ? "1 minute ago" : `${minutes} minutes ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  const d = new Date(ts);
  const today = new Date();
  const y = new Date(today);
  y.setDate(y.getDate() - 1);
  if (
    d.getFullYear() === y.getFullYear() &&
    d.getMonth() === y.getMonth() &&
    d.getDate() === y.getDate()
  ) {
    return "yesterday";
  }
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} days ago`;
  return d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

type TimelineKind = "dispatch" | "conversation" | "transcript";

type TimelineRow = {
  key: string;
  kind: TimelineKind;
  sortMs: number;
  iso: string | null;
  title: string;
  subtitle: string;
  href: string | null;
};

const EPICS_ACTIVITY_HREF = "/admin/workstreams";
const BRAIN_CONVERSATIONS_HREF = "/admin/brain/conversations";

function buildActivityTimelineRows(act: EmployeeActivityPayload): TimelineRow[] {
  const rows: TimelineRow[] = [];

  for (const d of act.dispatches) {
    const iso = d.dispatched_at;
    rows.push({
      key: `d:${d.epic_id}:${iso ?? "na"}`,
      kind: "dispatch",
      sortMs: iso ? Date.parse(iso) || 0 : 0,
      iso,
      title: d.title,
      subtitle: `Dispatch · ${d.epic_id} · ${d.status}`,
      href: EPICS_ACTIVITY_HREF,
    });
  }

  for (const c of act.conversations) {
    const iso = c.last_message_at;
    rows.push({
      key: `c:${c.conversation_id}`,
      kind: "conversation",
      sortMs: iso ? Date.parse(iso) || 0 : 0,
      iso,
      title: c.title,
      subtitle: `Conversation · ${c.message_count} message${c.message_count === 1 ? "" : "s"}`,
      href: BRAIN_CONVERSATIONS_HREF,
    });
  }

  for (const t of act.transcript_episodes) {
    const iso = t.created_at;
    rows.push({
      key: `t:${t.transcript_id}:${iso ?? t.title}`,
      kind: "transcript",
      sortMs: iso ? Date.parse(iso) || 0 : 0,
      iso,
      title: t.title,
      subtitle: `Transcript · ${t.transcript_id}`,
      href: null,
    });
  }

  rows.sort((a, b) => b.sortMs - a.sortMs);
  return rows;
}

function EmployeeActivityTimeline({ activity }: { activity: EmployeeActivityPayload }) {
  const rows = buildActivityTimelineRows(activity);
  if (rows.length === 0) {
    return (
      <HqEmptyState
        icon={<MessageSquare className="h-8 w-8" aria-hidden />}
        title="Activity"
        description="No activity recorded."
      />
    );
  }

  const renderRowBody = (row: TimelineRow) => {
    const kindEmoji =
      row.kind === "dispatch" ? "📤" : row.kind === "conversation" ? "💬" : "📋";
    return (
      <div className="min-w-0 flex-1 space-y-0.5">
        <div className="flex flex-wrap items-baseline gap-2">
          <span aria-hidden className="select-none text-base leading-none">
            {kindEmoji}
          </span>
          {row.href ? (
            <Link
              href={row.href}
              className="text-sm font-medium text-sky-400 hover:text-sky-300"
            >
              {row.title}
            </Link>
          ) : (
            <span className="text-sm font-medium text-zinc-100">{row.title}</span>
          )}
        </div>
        <p className="pl-[1.625rem] text-xs text-zinc-500">{row.subtitle}</p>
        <p className="pl-[1.625rem] text-xs text-zinc-600">{formatActivityRelative(row.iso)}</p>
      </div>
    );
  };

  return (
    <Card className="border-zinc-800/90 bg-zinc-950/40 shadow-none">
      <CardContent className="space-y-0 p-5">
        <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-zinc-500">
          Recent timeline
        </h3>
        <div className="space-y-0" role="list" aria-label="Employee activity timeline">
          {rows.map((row, index) => {
            const isLast = index === rows.length - 1;
            const dotClass =
              row.kind === "dispatch"
                ? "bg-violet-400"
                : row.kind === "conversation"
                  ? "bg-sky-400"
                  : "bg-amber-400";
            return (
              <div key={row.key} className="flex gap-3 pb-10 last:pb-0" role="listitem">
                <div className="flex w-10 shrink-0 flex-col items-center pt-1">
                  <span
                    aria-hidden
                    className={cn(
                      "h-2.5 w-2.5 rounded-full ring-2 ring-zinc-950",
                      dotClass,
                    )}
                  />
                  {!isLast ? (
                    <span
                      aria-hidden
                      className="mt-2 mb-[-0.125rem] w-px shrink-0 grow bg-zinc-800/95"
                      style={{ minHeight: "2.75rem" }}
                    />
                  ) : null}
                </div>
                {renderRowBody(row)}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function ConfigKV({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0 border-b border-zinc-800/80 py-3 last:border-0 md:grid md:grid-cols-[minmax(140px,200px)_1fr] md:gap-6">
      <dt className="pb-1 text-xs font-medium uppercase tracking-wide text-zinc-500 md:pb-0">
        {label}
      </dt>
      <dd className="min-w-0 text-sm text-zinc-100">{value}</dd>
    </div>
  );
}

function OwnershipCard({
  title,
  emptyLabel,
  children,
}: {
  title: string;
  emptyLabel: string;
  children: ReactNode;
}) {
  const isEmpty =
    children == null ||
    children === false ||
    (Array.isArray(children) && children.length === 0);
  return (
    <Card className="border-zinc-800/90 bg-zinc-950/40 shadow-none">
      <CardContent className="space-y-3 p-4">
        <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
        {isEmpty ? (
          <p className="text-xs text-zinc-500">{emptyLabel}</p>
        ) : (
          <ul className="flex flex-wrap gap-2">{children}</ul>
        )}
      </CardContent>
    </Card>
  );
}

export function EmployeeProfileTabsClient({
  employee: e,
  activity,
}: {
  employee: EmployeeDetail;
  activity: EmployeeActivityPayload;
}) {
  const isHuman = e.kind === "human";
  const displayHeadline = e.display_name?.trim() || e.role_title;
  const tagline = e.tagline?.trim() || null;
  const selfNamingDate = e.named_by_self ? formatNamedAt(e.named_at) : null;

  const namingCeremonyPanel =
    !isHuman ? (
      <Card className="border-zinc-800/90 bg-zinc-950/40 shadow-none">
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 space-y-1">
            <h3 className="text-sm font-semibold text-zinc-200">Naming ceremony</h3>
            <p className="text-xs text-zinc-500">
              Re-run persona self-name, tagline, and avatar emoji (calls the persona model).
            </p>
          </div>
          <EmployeeNamingCeremonyButton slug={e.slug} />
        </CardContent>
      </Card>
    ) : null;

  const overviewTab = (
    <div className="space-y-8">
      <section
        className={cn(
          "rounded-2xl bg-gradient-to-br p-6 ring-1 md:p-8",
          e.kind === "human"
            ? "from-sky-500/15 to-zinc-950 ring-sky-500/25"
            : "from-violet-500/12 to-zinc-950 ring-violet-500/25",
        )}
        aria-label="Profile hero"
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:gap-6">
          <span
            className="flex h-[64px] w-[64px] select-none items-center justify-center text-[64px] leading-none"
            aria-hidden
          >
            {e.avatar_emoji ?? "◇"}
          </span>
          <div className="min-w-0 flex-1 space-y-2">
            <h2 className="text-2xl font-semibold tracking-tight text-zinc-100 md:text-3xl">
              {displayHeadline}
            </h2>
            {e.display_name?.trim() ? (
              <p className="text-sm text-zinc-400">{e.role_title}</p>
            ) : null}
            {tagline ? <p className="text-base text-zinc-400">{tagline}</p> : null}
          </div>
          <Badge
            variant="outline"
            className={cn(
              "h-fit shrink-0 border font-medium",
              e.kind === "human"
                ? "border-sky-600/50 bg-sky-950/30 text-sky-100"
                : "border-violet-600/50 bg-violet-950/30 text-violet-100",
            )}
          >
            {kindBadgeLabel(e.kind)}
          </Badge>
        </div>
      </section>

      <section aria-label="Org details">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="border-zinc-800/90 bg-zinc-950/40 shadow-none">
            <CardContent className="space-y-1 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Team</p>
              <p className="text-sm font-medium text-zinc-100">{e.team || "—"}</p>
            </CardContent>
          </Card>
          <Card className="border-zinc-800/90 bg-zinc-950/40 shadow-none">
            <CardContent className="space-y-1 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Role</p>
              <p className="text-sm font-medium text-zinc-100">{e.role_title || "—"}</p>
            </CardContent>
          </Card>
          <Card className="border-zinc-800/90 bg-zinc-950/40 shadow-none">
            <CardContent className="space-y-1 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Reports to</p>
              {e.reports_to ? (
                <Link
                  href={`/admin/people/${encodeURIComponent(e.reports_to)}`}
                  className="text-sm font-medium text-sky-400 hover:text-sky-300"
                >
                  {e.reports_to}
                </Link>
              ) : (
                <p className="text-sm font-medium text-zinc-400">—</p>
              )}
            </CardContent>
          </Card>
          <Card className="border-zinc-800/90 bg-zinc-950/40 shadow-none">
            <CardContent className="space-y-1 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Slug</p>
              <p className="font-mono text-sm text-zinc-300">{e.slug}</p>
            </CardContent>
          </Card>
        </div>
      </section>

      {e.named_by_self ? (
        <div className="rounded-lg border border-emerald-800/40 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-100/95">
          <span className="font-semibold">Named by self</span>
          {selfNamingDate ? <span className="text-emerald-200/80"> — {selfNamingDate}</span> : null}
        </div>
      ) : null}

      <section aria-label="Description">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">
          Description
        </h3>
        {e.description?.trim() ? (
          <div className="rounded-xl border border-zinc-800/90 bg-zinc-950/50 p-5">
            <SprintMarkdown>{e.description}</SprintMarkdown>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">No description from Brain.</p>
        )}
      </section>
    </div>
  );

  const configTab = (
    <div className="space-y-6">
      {namingCeremonyPanel}
      <Card className="border-zinc-800/90 bg-zinc-950/40 shadow-none">
        <CardContent className="p-0 px-4">
          <h3 className="border-b border-zinc-800/80 pb-3 pt-4 text-sm font-semibold text-zinc-200">
            Brain configuration
          </h3>
          <dl className="divide-zinc-800/80">
            <ConfigKV label="Default model" value={e.default_model || "—"} />
            <ConfigKV label="Escalation model" value={e.escalation_model ?? "—"} />
            <ConfigKV
              label="Escalate if"
              value={
                e.escalate_if.length ? (
                  <ul className="list-inside list-disc space-y-1 text-zinc-300">
                    {e.escalate_if.map((rule) => (
                      <li key={rule}>{rule}</li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-zinc-500">—</span>
                )
              }
            />
            <ConfigKV label="Mode" value={e.mode ?? "—"} />
            <ConfigKV
              label="Tone prefix"
              value={
                e.tone_prefix?.trim() ? (
                  <span className="whitespace-pre-wrap text-zinc-300">{e.tone_prefix}</span>
                ) : (
                  <span className="text-zinc-500">—</span>
                )
              }
            />
            <ConfigKV
              label="Requires tools"
              value={e.requires_tools ? <span className="text-emerald-300">Yes</span> : "No"}
            />
          </dl>
        </CardContent>
      </Card>

      <Card className="border-zinc-800/90 bg-zinc-950/40 shadow-none">
        <CardContent className="p-0 px-4">
          <h3 className="border-b border-zinc-800/80 pb-3 pt-4 text-sm font-semibold text-zinc-200">
            Cursor configuration
          </h3>
          <dl className="divide-zinc-800/80">
            <ConfigKV
              label="Rule description"
              value={
                e.cursor_description?.trim() ? (
                  <span className="whitespace-pre-wrap text-zinc-300">{e.cursor_description}</span>
                ) : (
                  <span className="text-zinc-500">—</span>
                )
              }
            />
            <ConfigKV
              label="Globs"
              value={
                e.cursor_globs.length ? (
                  <ul className="space-y-1 font-mono text-xs text-zinc-400">
                    {e.cursor_globs.map((g) => (
                      <li key={g}>{g}</li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-zinc-500">—</span>
                )
              }
            />
            <ConfigKV label="Always apply" value={e.cursor_always_apply ? "Yes" : "No"} />
          </dl>
        </CardContent>
      </Card>

      <Card className="border-zinc-800/90 bg-zinc-950/40 shadow-none">
        <CardContent className="p-0 px-4">
          <h3 className="border-b border-zinc-800/80 pb-3 pt-4 text-sm font-semibold text-zinc-200">
            Runtime limits
          </h3>
          <dl className="divide-zinc-800/80">
            <ConfigKV
              label="Daily cost ceiling (USD)"
              value={
                e.daily_cost_ceiling_usd != null ? `$${String(e.daily_cost_ceiling_usd)}` : "—"
              }
            />
            <ConfigKV
              label="Max output tokens"
              value={e.max_output_tokens != null ? String(e.max_output_tokens) : "—"}
            />
            <ConfigKV
              label="Requests per minute"
              value={e.requests_per_minute != null ? String(e.requests_per_minute) : "—"}
            />
            <ConfigKV label="Owner channel" value={e.owner_channel ?? "—"} />
            <ConfigKV label="Proactive cadence" value={e.proactive_cadence ?? "—"} />
          </dl>
        </CardContent>
      </Card>
    </div>
  );

  const ownershipTab = (
    <div className="grid gap-4 lg:grid-cols-2">
      <OwnershipCard title="Rules owned" emptyLabel="No Cursor rules attributed.">
        {e.owned_rules.map((rule) => (
          <li key={rule}>
            <Link
              href={ruleViewerHref(rule)}
              className="inline-flex rounded-md border border-zinc-700 bg-zinc-900/80 px-2.5 py-1 text-xs text-sky-300 hover:border-zinc-600 hover:text-sky-200"
            >
              {rule.endsWith(".mdc") ? rule : `${rule}.mdc`}
            </Link>
          </li>
        ))}
      </OwnershipCard>
      <OwnershipCard title="Runbooks owned" emptyLabel="No runbooks attributed.">
        {e.owned_runbooks.map((slug) => (
          <li key={slug}>
            <Link
              href={`/admin/docs/${encodeURIComponent(slug)}`}
              className="inline-flex rounded-md border border-zinc-700 bg-zinc-900/80 px-2.5 py-1 text-xs text-sky-300 hover:border-zinc-600 hover:text-sky-200"
            >
              {slug}
            </Link>
          </li>
        ))}
      </OwnershipCard>
      <OwnershipCard title="Workflows owned" emptyLabel="No workflows attributed.">
        {e.owned_workflows.map((id) => (
          <li
            key={id}
            className="inline-flex rounded-md border border-zinc-700/90 bg-zinc-900/50 px-2.5 py-1 font-mono text-xs text-zinc-300"
          >
            {id}
          </li>
        ))}
      </OwnershipCard>
      <OwnershipCard title="Skills owned" emptyLabel="No skills attributed.">
        {e.owned_skills.map((id) => (
          <li
            key={id}
            className="inline-flex rounded-md border border-zinc-700/90 bg-zinc-900/50 px-2.5 py-1 font-mono text-xs text-zinc-300"
          >
            {id}
          </li>
        ))}
      </OwnershipCard>
      <div className="lg:col-span-2">
        <OwnershipCard title="Direct reports" emptyLabel="None listed.">
          {e.manages.map((slug) => (
            <li key={slug}>
              <Link
                href={`/admin/people/${encodeURIComponent(slug)}`}
                className="inline-flex rounded-md border border-zinc-700 bg-zinc-900/80 px-2.5 py-1 text-xs text-sky-300 hover:border-zinc-600 hover:text-sky-200"
              >
                {slug}
              </Link>
            </li>
          ))}
        </OwnershipCard>
      </div>
    </div>
  );

  const activityTab = <EmployeeActivityTimeline activity={activity} />;

  const tabs: StudioTabDef<EmployeeProfileTabId>[] = [];
  tabs.push({ id: "overview", label: "Overview", content: overviewTab });
  if (!isHuman) tabs.push({ id: "config", label: "Config", content: configTab });
  tabs.push(
    { id: "ownership", label: "Ownership", content: ownershipTab },
    { id: "activity", label: "Activity", content: activityTab },
  );

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-3 rounded-lg border border-zinc-800/80 bg-zinc-950/30 px-3 py-2 text-xs text-zinc-500">
        <Radio className="mt-0.5 h-3.5 w-3.5 shrink-0 text-zinc-500" aria-hidden />
        <span>
          Live roster from Brain · updated {formatNamedAt(e.updated_at) ?? e.updated_at}
        </span>
      </div>
      <TabbedPageShell<EmployeeProfileTabId> tabs={tabs} defaultTab="overview" />
    </div>
  );
}
