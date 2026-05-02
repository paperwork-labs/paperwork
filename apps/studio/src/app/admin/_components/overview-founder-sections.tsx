import Link from "next/link";
import type { ReactNode } from "react";
import {
  Activity,
  Boxes,
  Brain,
  CheckCircle2,
  Cpu,
  ExternalLink,
  ListTree,
  UsersRound,
} from "lucide-react";

import { formatRelativeActivity } from "@/app/admin/workstreams/display-utils";
import { HqStatCard, type HqStatCardStatus } from "@/components/admin/hq/HqStatCard";
import type { DispatchLogEntry } from "@/lib/brain-client";
import type { InfraStatus } from "@/lib/infra-types";
import type { ProductHealthPulse } from "@/lib/product-health-brain";

import type {
  OverviewBrainFill,
  OverviewEpicPulse,
  OverviewOperatingScore,
  OverviewPeoplePulse,
  OverviewDispatches,
  ProductHealthRollup,
} from "@/app/admin/_lib/overview-founder-data";

const GH_PULL = "https://github.com/paperwork-labs/paperwork/pull";

export function SectionDivider() {
  return <div className="border-t border-zinc-800/90" aria-hidden />;
}

function statCardTone(successCond: boolean, warnCond: boolean, dangerCond: boolean): HqStatCardStatus {
  if (dangerCond) return "danger";
  if (warnCond) return "warning";
  if (successCond) return "success";
  return "neutral";
}

export function LinkPulseCard({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="group block rounded-xl outline-none ring-offset-2 ring-offset-zinc-950 transition hover:brightness-[1.04] focus-visible:ring-2 focus-visible:ring-violet-400/70"
    >
      {children}
    </Link>
  );
}

export type FounderAttentionItem = {
  key: string;
  severity: "danger" | "warning";
  message: ReactNode;
  href: string;
};

export function QuickPulseSection({
  operatingScore,
  productRollup,
  epicPulse,
  peoplePulse,
  infraHealthy,
  infraTotal,
  brainFill,
}: {
  operatingScore: OverviewOperatingScore;
  productRollup: ProductHealthRollup;
  epicPulse: OverviewEpicPulse;
  peoplePulse: OverviewPeoplePulse;
  infraHealthy: number;
  infraTotal: number;
  brainFill: OverviewBrainFill;
}) {
  const prodSubtitleUnknown = productRollup.unknown > 0 ? `${productRollup.unknown} unknown` : null;
  const prodSubtitle =
    productRollup.degraded === 0 && productRollup.down === 0 && productRollup.unknown === 0
      ? `${productRollup.healthy} healthy`
      : [
          `${productRollup.healthy} healthy`,
          productRollup.degraded ? `${productRollup.degraded} degraded` : null,
          productRollup.down ? `${productRollup.down} down` : null,
          prodSubtitleUnknown,
        ]
          .filter(Boolean)
          .join(" · ");

  const epicValue =
    epicPulse.ok === true ? epicPulse.activeEpics : "—";
  const epicHelp =
    epicPulse.ok === true
      ? `${epicPulse.wavePct}% avg · current wave`
      : epicPulse.message;

  const peopleValue = peoplePulse.ok === true ? peoplePulse.total : "—";
  const peopleHelp =
    peoplePulse.ok === true
      ? `${peoplePulse.named} named`
      : peoplePulse.message;

  const infraValue = infraTotal > 0 ? `${infraHealthy}/${infraTotal}` : "—";
  const infraHelp =
    infraTotal > 0
      ? infraHealthy >= infraTotal
        ? "All monitored services healthy"
        : `${infraTotal - infraHealthy} need attention`
      : "No infra probes configured";

  const brainValue =
    brainFill.ok === true ? `${brainFill.utilizationPct}%` : "—";
  const brainHelp = brainFill.ok === true ? "Overall memory utilization" : brainFill.message;

  const scoreLine =
    operatingScore.ok === true
      ? `Operating score ${operatingScore.overall_score}/${operatingScore.max_score}`
      : operatingScore.message;

  return (
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
            value={productRollup.total}
            helpText={prodSubtitle}
            variant="compact"
            icon={<Boxes className="h-3.5 w-3.5 text-zinc-500" />}
            status={statCardTone(
              productRollup.down === 0 && productRollup.degraded === 0,
              productRollup.degraded > 0,
              productRollup.down > 0,
            )}
          />
        </LinkPulseCard>
        <LinkPulseCard href="/admin/workstreams">
          <HqStatCard
            label="Epics"
            value={epicValue}
            helpText={epicHelp}
            variant="compact"
            icon={<ListTree className="h-3.5 w-3.5 text-zinc-500" />}
            status={epicPulse.ok === true ? "neutral" : "warning"}
          />
        </LinkPulseCard>
        <LinkPulseCard href="/admin/people">
          <HqStatCard
            label="People"
            value={peopleValue}
            helpText={peopleHelp}
            variant="compact"
            icon={<UsersRound className="h-3.5 w-3.5 text-zinc-500" />}
            status={peoplePulse.ok === true ? "success" : "warning"}
          />
        </LinkPulseCard>
        <LinkPulseCard href="/admin/infrastructure">
          <HqStatCard
            label="Infrastructure"
            value={infraValue}
            helpText={infraHelp}
            variant="compact"
            icon={<Cpu className="h-3.5 w-3.5 text-zinc-500" />}
            status={statCardTone(
              infraTotal > 0 && infraHealthy >= infraTotal,
              infraTotal > 0 && infraHealthy < infraTotal && infraHealthy > 0,
              infraTotal > 0 && infraHealthy === 0,
            )}
          />
        </LinkPulseCard>
        <LinkPulseCard href="/admin/brain/self-improvement">
          <HqStatCard
            label="Brain memory"
            value={brainValue}
            helpText={brainHelp}
            variant="compact"
            icon={<Brain className="h-3.5 w-3.5 text-zinc-500" />}
            status={
              brainFill.ok === true
                ? brainFill.utilizationPct >= 90
                  ? "danger"
                  : brainFill.utilizationPct >= 75
                    ? "warning"
                    : "success"
                : "warning"
            }
          />
        </LinkPulseCard>
      </div>
    </section>
  );
}

function SeverityDot({ kind }: { kind: "danger" | "warning" }) {
  return (
    <span
      className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
        kind === "danger" ? "bg-red-500" : "bg-amber-400"
      }`}
      aria-hidden
    />
  );
}

export function NeedsAttentionSection({ items }: { items: FounderAttentionItem[] }) {
  return (
    <section className="space-y-3">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Needs attention
      </h2>
      {items.length === 0 ? (
        <div className="flex items-start gap-3 rounded-xl border border-emerald-900/35 bg-emerald-950/20 px-4 py-3 ring-1 ring-emerald-800/25">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" aria-hidden />
          <div>
            <p className="text-sm font-medium text-emerald-100">All clear</p>
            <p className="mt-1 text-xs text-emerald-200/80">
              No blocked epics, product outages, infra failures, or broken reading paths flagged right now.
            </p>
          </div>
        </div>
      ) : (
        <ul className="space-y-2 rounded-xl border border-zinc-800 bg-zinc-950/80 p-3 ring-1 ring-zinc-800/90">
          {items.map((item) => (
            <li key={item.key}>
              <Link
                href={item.href}
                className="flex gap-3 rounded-lg px-2 py-2 transition hover:bg-zinc-900/80"
              >
                <SeverityDot kind={item.severity} />
                <span className="min-w-0 flex-1 text-sm text-zinc-200">{item.message}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function personaLabel(d: DispatchLogEntry): string {
  return (
    d.persona?.trim() ||
    d.persona_slug?.trim() ||
    d.persona_pin?.trim() ||
    "Persona"
  );
}

export function RecentActivitySection({ dispatches }: { dispatches: OverviewDispatches }) {
  const unavailable =
    dispatches.ok === false ? (
      <div className="rounded-xl border border-dashed border-zinc-700 bg-zinc-950/60 px-4 py-6 text-center">
        <Activity className="mx-auto h-8 w-8 text-zinc-600" aria-hidden />
        <p className="mt-3 text-sm font-medium text-zinc-300">Connect Brain for activity feed</p>
        <p className="mt-1 text-xs text-zinc-500">{dispatches.message}</p>
        <p className="mt-4 text-xs text-zinc-600">
          Set <code className="rounded bg-zinc-900 px-1 font-mono">BRAIN_API_URL</code> and{" "}
          <code className="rounded bg-zinc-900 px-1 font-mono">BRAIN_API_SECRET</code> to load dispatch
          events from Brain.
        </p>
      </div>
    ) : null;

  const list =
    dispatches.ok === true && dispatches.entries.length > 0 ? (
      <ul className="divide-y divide-zinc-800/90 rounded-xl border border-zinc-800 bg-zinc-950/80 ring-1 ring-zinc-800/90">
        {dispatches.entries.map((d, i) => {
          const pr = d.pr_number != null ? (
            <a
              href={`${GH_PULL}/${d.pr_number}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-violet-300 underline-offset-2 hover:text-violet-200 hover:underline"
            >
              #{d.pr_number}
              <ExternalLink className="h-3 w-3 opacity-70" aria-hidden />
            </a>
          ) : (
            <span className="text-zinc-600">—</span>
          );
          const when =
            d.dispatched_at != null ? formatRelativeActivity(d.dispatched_at) : "—";
          const summary = (d.task_summary ?? "").trim() || "Dispatch event";
          return (
            <li key={`${d.dispatched_at}-${i}`} className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  {personaLabel(d)}
                </p>
                <p className="truncate text-sm text-zinc-200">{summary}</p>
              </div>
              <div className="flex shrink-0 items-center gap-4 text-xs text-zinc-400">
                <span>{pr}</span>
                <span className="tabular-nums text-zinc-500">{when}</span>
              </div>
            </li>
          );
        })}
      </ul>
    ) : dispatches.ok === true ? (
      <p className="rounded-xl border border-zinc-800 bg-zinc-950/80 px-4 py-4 text-sm text-zinc-500 ring-1 ring-zinc-800/90">
        No recent dispatch events in Brain yet.
      </p>
    ) : null;

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
          Recent activity
        </h2>
        {dispatches.ok === true && dispatches.entries.length > 0 ? (
          <Link
            href="/admin/autopilot"
            className="text-xs text-zinc-400 underline-offset-2 hover:text-zinc-200 hover:underline"
          >
            Autopilot →
          </Link>
        ) : null}
      </div>
      {unavailable ?? list}
    </section>
  );
}

export function OverviewSectionChrome({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="space-y-8 rounded-2xl border border-zinc-800/90 bg-zinc-950 p-4 shadow-inner shadow-black/20 ring-1 ring-zinc-800/70 md:p-6">
      {children}
    </div>
  );
}

export function buildAttentionItems(params: {
  productBad: { slug: string; pulse: ProductHealthPulse }[];
  infraFailing: InfraStatus[];
  readingPaths: {
    pathCount: number;
    samples: { id: string; title: string; unresolvedCount: number }[];
  };
}): FounderAttentionItem[] {
  const items: FounderAttentionItem[] = [];

  for (const p of params.productBad.slice(0, 8)) {
    items.push({
      key: `product-${p.slug}`,
      severity: p.pulse === "down" ? "danger" : "warning",
      message: (
        <>
          Product <span className="font-medium text-zinc-100">{p.slug}</span> is{" "}
          <span className="uppercase">{p.pulse}</span>
        </>
      ),
      href: `/admin/products/${encodeURIComponent(p.slug)}?tab=health`,
    });
  }

  for (const row of params.infraFailing.slice(0, 8)) {
    const hash = row.anchorId ? `#${row.anchorId}` : "";
    items.push({
      key: `infra-${row.service}`,
      severity: "danger",
      message: (
        <>
          Infra: <span className="text-zinc-100">{row.service}</span>
          {row.detail ? <span className="text-zinc-500"> — {row.detail}</span> : null}
        </>
      ),
      href: `/admin/infrastructure${hash}`,
    });
  }

  if (params.readingPaths.pathCount > 0) {
    const sample = params.readingPaths.samples[0];
    items.push({
      key: "reading-paths",
      severity: "warning",
      message: (
        <>
          {params.readingPaths.pathCount} reading path
          {params.readingPaths.pathCount === 1 ? "" : "s"} with unresolved docs
          {sample ? (
            <span className="text-zinc-500">
              {" "}
              (e.g. {sample.title}: {sample.unresolvedCount} doc
              {sample.unresolvedCount === 1 ? "" : "s"})
            </span>
          ) : null}
        </>
      ),
      href: "/admin/docs",
    });
  }

  return items;
}
