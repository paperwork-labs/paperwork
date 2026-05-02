"use client";

import Link from "next/link";
import { type ReactNode } from "react";

import { Activity, Radio } from "lucide-react";

import { Badge, Card, CardContent, cn } from "@paperwork-labs/ui";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { TabbedPageShell, type StudioTabDef } from "@/components/layout/TabbedPageShellNext";
import { SprintMarkdown } from "@/components/sprint/SprintMarkdown";
import type { EmployeeDetail } from "@/lib/brain-client";

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
}: {
  employee: EmployeeDetail;
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

  const activityTab = (
    <HqEmptyState
      icon={<Activity className="h-8 w-8" aria-hidden />}
      title="Activity"
      description="Activity feed coming soon — will show dispatch history, conversation participation, and PR contributions."
    />
  );

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
