"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Boxes, ListTree, MessageSquare, UsersRound, Zap } from "lucide-react";

import { HqStatCard, type HqStatCardStatus } from "@/components/admin/hq/HqStatCard";
import type { DispatchLogEntry } from "@/lib/brain-client";

import type { OverviewDispatches, OverviewOperatingScore } from "@/app/admin/_lib/overview-founder-data";
import type { BrainAdminAttention, BrainAdminStats } from "@/app/admin/_lib/admin-pulse-types";
import {
  LinkPulseCard,
  NeedsAttentionSection,
  OverviewSectionChrome,
  RecentActivitySection,
  SectionDivider,
  type FounderAttentionItem,
} from "@/app/admin/_components/overview-founder-sections";

function statCardTone(successCond: boolean, warnCond: boolean, dangerCond: boolean): HqStatCardStatus {
  if (dangerCond) return "danger";
  if (warnCond) return "warning";
  if (successCond) return "success";
  return "neutral";
}

function numDelta(
  prev: number | undefined,
  cur: number | undefined,
): { direction: "up" | "down" | "flat"; value: string } | undefined {
  if (prev === undefined || cur === undefined) return undefined;
  const d = cur - prev;
  if (d === 0) return { direction: "flat", value: "0" };
  if (d > 0) return { direction: "up", value: `+${d}` };
  return { direction: "down", value: `${d}` };
}

function attentionFromBrain(data: BrainAdminAttention | null): FounderAttentionItem[] {
  if (!data) return [];
  const out: FounderAttentionItem[] = [];
  data.blocked_epics.forEach((e, idx) => {
    out.push({
      key: `brain-blocked-${e.id}-${idx}`,
      severity: "warning",
      message: (
        <>
          Blocked epic: <span className="text-zinc-100">{e.title}</span>
          {e.goal_objective ? (
            <span className="text-zinc-500"> · {e.goal_objective}</span>
          ) : null}
        </>
      ),
      href: "/admin/workstreams",
    });
  });
  data.stale_sprints.forEach((s, idx) => {
    out.push({
      key: `brain-stale-${s.id}-${idx}`,
      severity: "warning",
      message: (
        <>
          Stale sprint: <span className="text-zinc-100">{s.title}</span>
          <span className="text-zinc-500"> · {s.epic_title}</span>
          {s.last_activity_at ? (
            <span className="text-zinc-600"> · last activity {s.last_activity_at.slice(0, 10)}</span>
          ) : null}
        </>
      ),
      href: "/admin/workstreams",
    });
  });
  data.unreplied_conversations.forEach((c, idx) => {
    out.push({
      key: `brain-conv-${c.id}-${idx}`,
      severity: "danger",
      message: (
        <>
          Conversation needs reply: <span className="text-zinc-100">{c.title}</span>
        </>
      ),
      href: "/admin/brain/conversations",
    });
  });
  data.failed_dispatches.forEach((d, idx) => {
    const pr = d.pr_number != null ? `#${d.pr_number}` : "—";
    const summary =
      d.task_summary != null && String(d.task_summary).trim()
        ? String(d.task_summary).slice(0, 120)
        : null;
    out.push({
      key: `brain-dispatch-fail-${idx}-${String(d.dispatched_at ?? "")}`,
      severity: "danger",
      message: (
        <>
          Failed dispatch <span className="text-zinc-500">({pr})</span>
          {summary ? (
            <>
              : <span className="text-zinc-100">{summary}</span>
            </>
          ) : null}
        </>
      ),
      href: "/admin/autopilot",
    });
  });
  return out;
}

function parseStatsEnvelope(raw: unknown): BrainAdminStats | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as { success?: unknown; data?: unknown };
  if (o.success !== true || !o.data || typeof o.data !== "object") return null;
  return o.data as BrainAdminStats;
}

function parseAttentionEnvelope(raw: unknown): BrainAdminAttention | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as { success?: unknown; data?: unknown };
  if (o.success !== true || !o.data || typeof o.data !== "object") return null;
  return o.data as BrainAdminAttention;
}

export function OverviewPulseAttentionClient({
  operatingScore,
  staticAttentionItems,
  initialDispatches,
}: {
  operatingScore: OverviewOperatingScore;
  staticAttentionItems: FounderAttentionItem[];
  initialDispatches: OverviewDispatches;
}) {
  const [stats, setStats] = useState<BrainAdminStats | null>(null);
  const prevStatsRef = useRef<BrainAdminStats | null>(null);
  const [brainAttention, setBrainAttention] = useState<BrainAdminAttention | null>(null);
  const [dispatches, setDispatches] = useState<OverviewDispatches>(initialDispatches);

  const refresh = useCallback(async () => {
    const [statsRes, attRes, dispRes] = await Promise.all([
      fetch("/api/admin/stats"),
      fetch("/api/admin/attention"),
      fetch("/api/admin/agent-dispatch-log?limit=5"),
    ]);

    if (statsRes.ok) {
      try {
        const j: unknown = await statsRes.json();
        const next = parseStatsEnvelope(j);
        if (next) {
          setStats((cur) => {
            prevStatsRef.current = cur;
            return next;
          });
        }
      } catch {
        /* keep prior stats */
      }
    }

    if (attRes.ok) {
      try {
        const j: unknown = await attRes.json();
        const next = parseAttentionEnvelope(j);
        if (next) setBrainAttention(next);
      } catch {
        /* ignore */
      }
    }

    if (dispRes.ok) {
      try {
        const j: unknown = await dispRes.json();
        const data =
          j && typeof j === "object" ? (j as { data?: { dispatches?: unknown } }).data : null;
        const rows = data?.dispatches;
        if (Array.isArray(rows)) {
          setDispatches({ ok: true, entries: rows as DispatchLogEntry[] });
        }
      } catch {
        /* ignore */
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const t = setInterval(() => void refresh(), 60_000);
    return () => clearInterval(t);
  }, [refresh]);

  const mergedAttention = useMemo(() => {
    const fromBrain = attentionFromBrain(brainAttention);
    return [...fromBrain, ...staticAttentionItems];
  }, [brainAttention, staticAttentionItems]);

  const scoreLine =
    operatingScore.ok === true
      ? `Operating score ${operatingScore.overall_score}/${operatingScore.max_score}`
      : operatingScore.message;

  const s = stats;
  const prev = prevStatsRef.current;
  const dash = "—";

  const prodOther =
    s && Number.isFinite(s.products.total) && Number.isFinite(s.products.active)
      ? Math.max(0, s.products.total - s.products.active)
      : null;

  return (
    <OverviewSectionChrome>
      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Quick pulse
          </h2>
          <p className="text-xs text-zinc-500">{scoreLine}</p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <LinkPulseCard href="/admin/products">
            <HqStatCard
              label="Products"
              value={s ? s.products.total : dash}
              delta={numDelta(prev?.products.total, s?.products.total)}
              helpText={s ? `${s.products.active} active · ${prodOther ?? 0} other` : "—"}
              variant="compact"
              icon={<Boxes className="h-3.5 w-3.5 text-zinc-500" />}
              status={statCardTone(
                Boolean(s && s.products.active > 0),
                Boolean(s && prodOther !== null && prodOther > 0),
                false,
              )}
            />
          </LinkPulseCard>
          <LinkPulseCard href="/admin/workstreams">
            <HqStatCard
              label="Epics"
              value={s ? s.epics.in_progress : dash}
              delta={numDelta(prev?.epics.in_progress, s?.epics.in_progress)}
              helpText={
                s
                  ? `${s.epics.total} total · ${s.epics.blocked} blocked · ${s.epics.completed} done`
                  : "—"
              }
              variant="compact"
              icon={<ListTree className="h-3.5 w-3.5 text-zinc-500" />}
              status={statCardTone(
                Boolean(s && s.epics.blocked === 0),
                Boolean(s && s.epics.blocked > 0),
                Boolean(s && s.epics.blocked > 3),
              )}
            />
          </LinkPulseCard>
          <LinkPulseCard href="/admin/people">
            <HqStatCard
              label="People"
              value={s ? s.employees.total : dash}
              delta={numDelta(prev?.employees.total, s?.employees.total)}
              helpText={s ? `${s.employees.ai} AI · ${s.employees.human} human` : "—"}
              variant="compact"
              icon={<UsersRound className="h-3.5 w-3.5 text-zinc-500" />}
              status="success"
            />
          </LinkPulseCard>
          <LinkPulseCard href="/admin/workstreams">
            <HqStatCard
              label="Sprints"
              value={s ? s.sprints.active : dash}
              delta={numDelta(prev?.sprints.active, s?.sprints.active)}
              helpText={s ? `${s.sprints.total} total · active batches` : "—"}
              variant="compact"
              icon={<Zap className="h-3.5 w-3.5 text-zinc-500" />}
              status="neutral"
            />
          </LinkPulseCard>
          <LinkPulseCard href="/admin/brain/conversations">
            <HqStatCard
              label="Conversations"
              value={s ? s.conversations.total : dash}
              delta={numDelta(prev?.conversations.total, s?.conversations.total)}
              helpText={
                s
                  ? `${s.conversations.today} touched today · ${s.dispatches_today} dispatches today`
                  : "—"
              }
              variant="compact"
              icon={<MessageSquare className="h-3.5 w-3.5 text-zinc-500" />}
              status="neutral"
            />
          </LinkPulseCard>
        </div>
      </section>
      <SectionDivider />
      <NeedsAttentionSection items={mergedAttention} />
      <SectionDivider />
      <RecentActivitySection dispatches={dispatches} />
    </OverviewSectionChrome>
  );
}
