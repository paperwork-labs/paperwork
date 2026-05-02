"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  RefreshCw,
  ExternalLink,
  Server,
  Globe,
  Database,
  HardDrive,
  Cpu,
  Radio,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Layers,
} from "lucide-react";
import type { InfraStatus, PlatformHealthSummary } from "@/lib/infra-types";
import QuotaGitHubActionsPanel from "./quota-github-actions-panel";
import QuotaRenderPanel from "./quota-render-panel";
import QuotaVercelPanel from "./quota-vercel-panel";
import { Card, CardContent } from "@paperwork-labs/ui";
import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { HqMissingCredCard } from "@/components/admin/hq/HqMissingCredCard";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";
import { SUGGESTED_VERCEL_MONOREPO_PROJECT_NAMES_CSV } from "@/lib/infra-probes";
import { HETZNER_BOXES } from "@/lib/hetzner-boxes";
import LogsTab from "./tabs/logs-tab";

type InfraService = InfraStatus;

const RENDER_APIS_WEB = new Set([
  "brain-api",
  "filefree-api",
  "axiomfolio-api",
  "launchfree-api",
]);
const RENDER_WORKERS = new Set(["axiomfolio-worker", "axiomfolio-worker-heavy"]);
const RENDER_DATA = new Set(["axiomfolio-db", "axiomfolio-redis"]);

const CORE_HEALTH_PROBE_NAMES = new Set([
  "Brain API (HTTP /health)",
  "FileFree API (HTTP /health)",
  "AxiomFolio API (HTTP /health)",
  "LaunchFree API",
]);

const API_PROVIDER_CARDS: { name: string; consoleHref: string }[] = [
  { name: "Anthropic", consoleHref: "https://console.anthropic.com/" },
  { name: "OpenAI", consoleHref: "https://platform.openai.com/" },
  { name: "Google Gemini", consoleHref: "https://aistudio.google.com/" },
  { name: "Mistral", consoleHref: "https://console.mistral.ai/" },
  { name: "Perplexity", consoleHref: "https://www.perplexity.ai/settings/api" },
];

const categoryMeta: Record<string, { label: string; icon: typeof Server }> = {
  core: { label: "Core APIs", icon: Server },
  frontend: { label: "Frontends", icon: Globe },
  ops: { label: "Operations", icon: Cpu },
  hosting: { label: "Hosting & Deploys", icon: Globe },
  data: { label: "Data", icon: Database },
  cache: { label: "Cache", icon: HardDrive },
};

const DAY0_VERCEL_MONOREPO_DOCS_HREF =
  "https://github.com/paperwork-labs/paperwork/blob/main/docs/strategy/DAY_0_FOUNDER_ACTIONS.md#item-19--set-vercel_monorepo_project_names";

function formatTimePT(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
      timeZone: "America/Los_Angeles",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function latencyColor(ms: number | null): string {
  if (ms === null) return "text-zinc-500";
  if (ms < 300) return "text-[var(--status-success)]";
  if (ms < 1000) return "text-[var(--status-warning)]";
  return "text-[var(--status-danger)]";
}

function StatusIcon({ healthy, configured }: { healthy: boolean; configured: boolean }) {
  if (!configured)
    return <AlertTriangle className="h-4 w-4 text-[var(--status-warning)]" />;
  if (healthy) return <CheckCircle2 className="h-4 w-4 text-[var(--status-success)]" />;
  return <XCircle className="h-4 w-4 text-[var(--status-danger)]" />;
}

function StatusDot({ healthy, configured }: { healthy: boolean; configured: boolean }) {
  if (!configured)
    return (
      <span className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--status-warning)]" />
    );
  if (healthy)
    return (
      <span className="relative inline-block h-2.5 w-2.5">
        <span className="absolute inset-0 motion-safe:animate-ping rounded-full bg-[var(--status-success)] opacity-50" />
        <span className="relative inline-block h-2.5 w-2.5 rounded-full bg-[var(--status-success)]" />
      </span>
    );
  return <span className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--status-danger)]" />;
}

function platformStateBadgeClass(st?: string): string {
  if (st === "live" || st === "ready")
    return "border-[var(--status-success)]/50 bg-[var(--status-success-bg)] text-[var(--status-success)]";
  if (st === "building")
    return "border-[var(--status-warning)]/50 bg-[var(--status-warning-bg)] text-[var(--status-warning)]";
  if (st === "failed" || st === "suspended")
    return "border-[var(--status-danger)]/50 bg-[var(--status-danger-bg)] text-[var(--status-danger)]";
  return "border-zinc-700 bg-zinc-900/80 text-zinc-300";
}

function platformProbeBadgeLabel(svc: InfraService): string {
  const raw = (svc.deployState ?? "").trim();
  if (raw && raw !== "?") return raw.replace(/_/g, " ");
  return svc.stateLabel ?? "?";
}

function platformProbeBadgeTone(svc: InfraService): string {
  const d = (svc.deployState ?? "").toLowerCase();
  if (d === "live" || d === "ready") return "live";
  if (
    d.includes("progress") ||
    d === "building" ||
    d === "queued" ||
    d === "initializing" ||
    d === "deploying" ||
    d === "analyzing"
  )
    return "building";
  if (d === "missing") return "failed";
  if (svc.stateLabel === "suspended") return "suspended";
  if (svc.stateLabel === "failed") return "failed";
  return svc.stateLabel ?? "";
}

function deriveSummary(services: InfraService[], fallback?: PlatformHealthSummary): PlatformHealthSummary {
  if (fallback) return fallback;
  const render = { live: 0, building: 0, failed: 0, suspended: 0, total: 0 };
  const vercel = { live: 0, building: 0, failed: 0, suspended: 0, total: 0 };
  for (const s of services) {
    if (s.probeKind === "render") {
      render.total++;
      const st = s.stateLabel ?? "failed";
      if (st === "live") render.live++;
      else if (st === "building") render.building++;
      else if (st === "failed") render.failed++;
      else render.suspended++;
    } else if (s.probeKind === "vercel") {
      vercel.total++;
      const st = s.stateLabel ?? "failed";
      if (st === "live") vercel.live++;
      else if (st === "building") vercel.building++;
      else if (st === "failed") vercel.failed++;
      else vercel.suspended++;
    }
  }
  return { render, vercel };
}

const AUTO_REFRESH_MS = 30_000;

/** Inner Services workspace views — must not use `tab`; that param is owned by the page shell. */
const INFRA_VIEW_PARAM = "infraView";
type InfraInnerView = "dashboard" | "logs";

function InfraClientSuspenseFallback() {
  return (
    <div
      className="space-y-4 rounded-xl border border-zinc-800 p-6 motion-safe:animate-pulse"
      aria-busy="true"
      aria-label="Loading infrastructure"
    >
      <div className="h-9 max-w-md rounded-md bg-zinc-800" />
      <div className="h-40 rounded-lg bg-zinc-900" />
    </div>
  );
}

function renderRollupPill(rows: InfraService[]): string {
  const active = rows.filter((r) => !r.deprecated);
  const depBad = rows.filter((r) => r.deprecated && !r.healthy);
  const healthyN = active.filter((r) => r.healthy).length;
  const totalN = active.length;
  if (totalN === 0) return "No Render rows";
  let s = `${healthyN} of ${totalN} healthy`;
  if (depBad.length) s += ` · ${depBad.length} deprecated (non-blocking)`;
  return s;
}

function vercelRollupPill(v: PlatformHealthSummary["vercel"], hasNames: boolean): string {
  if (!hasNames) return "Set env to list projects";
  if (v.total === 0) return "No Vercel rows";
  return `${v.live} of ${v.total} live`;
}

function ServiceCard({ svc }: { svc: InfraService }) {
  const isVercel = svc.probeKind === "vercel";
  const badgeTone = platformProbeBadgeTone(svc);
  const borderCls = !svc.configured
    ? "border-zinc-800"
    : svc.healthy
      ? "border-[var(--status-success)]/20"
      : "border-[var(--status-danger)]/30";
  return (
    <Card className={borderCls} id={svc.anchorId}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-medium text-zinc-100">{svc.service}</p>
            <p className="mt-0.5 text-xs text-zinc-500">
              {isVercel ? "Vercel" : "Render"} · {svc.platformType ?? "—"}
              {svc.deprecated ? (
                <span className="ml-2 text-[var(--status-warning)]/90">
                  · Scheduled for retirement (WS-02 Vercel cutover)
                </span>
              ) : null}
            </p>
          </div>
          <span
            className={`shrink-0 rounded border px-2 py-0.5 text-xs font-medium uppercase ${platformStateBadgeClass(
              badgeTone,
            )}`}
            data-testid="infra-probe-state"
          >
            {svc.deprecated && (svc.deployState ?? "").toLowerCase().includes("fail")
              ? "BUILD FAILED"
              : platformProbeBadgeLabel(svc)}
          </span>
        </div>
        <p className="mt-2 text-sm text-zinc-400">{svc.detail}</p>
        {svc.commitSha ? <p className="mt-1 font-mono text-xs text-zinc-500">SHA {svc.commitSha}</p> : null}
        {svc.lastDeployedAt ? (
          <p className="text-xs text-zinc-500">Deployed {formatTimePT(svc.lastDeployedAt)} PT</p>
        ) : null}
        <div className="mt-2 flex flex-wrap items-center gap-3">
          {svc.dashboardUrl ? (
            <a
              href={svc.dashboardUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-zinc-500 transition hover:text-zinc-300"
            >
              Open dashboard <ExternalLink className="h-3 w-3" />
            </a>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function SupplementaryCard({ svc }: { svc: InfraService }) {
  return (
    <Card
      className={
        !svc.configured ? "border-zinc-800" : svc.healthy ? "border-[var(--status-success)]/30" : "border-[var(--status-danger)]/30"
      }
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <StatusDot healthy={svc.healthy} configured={svc.configured} />
            <p className="font-medium text-zinc-100">{svc.service}</p>
          </div>
          <div className="flex items-center gap-2">
            {svc.latencyMs !== null ? (
              <span className={`font-mono text-xs tabular-nums ${latencyColor(svc.latencyMs)}`}>
                {svc.latencyMs}ms
              </span>
            ) : null}
            <StatusIcon healthy={svc.healthy} configured={svc.configured} />
          </div>
        </div>
        <p className="mt-2 text-sm text-zinc-400">{svc.detail}</p>
        {svc.service === "LaunchFree API" && !svc.healthy && /404/i.test(svc.detail) ? (
          <p className="mt-2 text-xs text-[var(--status-danger)]">
            error:{" "}
            {svc.detail.includes("→ HTTP") ? svc.detail : `GET /health → ${svc.detail}`}
          </p>
        ) : null}
        <div className="mt-2 flex flex-wrap items-center gap-3">
          {svc.dashboardUrl ? (
            <a
              href={svc.dashboardUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-zinc-500 transition hover:text-zinc-300"
            >
              Dashboard <ExternalLink className="h-3 w-3" />
            </a>
          ) : null}
          {svc.consoleUrl ? (
            <a
              href={svc.consoleUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-zinc-500 transition hover:text-zinc-300"
            >
              Console <ExternalLink className="h-3 w-3" />
            </a>
          ) : null}
          {svc.service === "LaunchFree API" && !svc.healthy && /404/i.test(svc.detail) ? (
            <a
              href="https://github.com/paperwork-labs/paperwork/blob/main/docs/runbooks/launchfree-api-health.md"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-[var(--status-danger)] hover:text-[color-mix(in_srgb,var(--status-danger)_80%,white)]"
            >
              Reconnect / fix endpoint <ExternalLink className="h-3 w-3" />
            </a>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function SectionHeader({
  title,
  pill,
  icon: Icon,
}: {
  title: string;
  pill: string;
  icon: typeof Globe | typeof Server;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-zinc-500" aria-hidden />
        <h2 className="text-sm font-semibold tracking-tight text-zinc-200">{title}</h2>
      </div>
      <span className="rounded-full border border-zinc-700 px-2.5 py-0.5 text-xs text-zinc-400">{pill}</span>
    </div>
  );
}

export default function InfraClient(props: {
  initialServices: InfraService[];
  initialPlatformSummary?: PlatformHealthSummary;
  initialPlatformPartial?: string[];
  initialCheckedAt: string;
  vercelMonorepoNamesConfigured: boolean;
}) {
  return (
    <Suspense fallback={<InfraClientSuspenseFallback />}>
      <InfraClientImpl {...props} />
    </Suspense>
  );
}

function InfraClientImpl({
  initialServices,
  initialPlatformSummary,
  initialPlatformPartial = [],
  initialCheckedAt,
  vercelMonorepoNamesConfigured,
}: {
  initialServices: InfraService[];
  initialPlatformSummary?: PlatformHealthSummary;
  initialPlatformPartial?: string[];
  initialCheckedAt: string;
  vercelMonorepoNamesConfigured: boolean;
}) {
  const [services, setServices] = useState(initialServices);
  const [platformSummary, setPlatformSummary] = useState<PlatformHealthSummary | undefined>(
    initialPlatformSummary,
  );
  const [platformPartial, setPlatformPartial] = useState<string[]>(initialPlatformPartial);
  const [checkedAt, setCheckedAt] = useState(initialCheckedAt);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [quotaRefresh, setQuotaRefresh] = useState(0);

  const { platformRows, otherRows } = useMemo(() => {
    const platformRowsInner = services.filter(
      (s) => s.probeKind === "render" || s.probeKind === "vercel",
    );
    const otherRowsInner = services.filter(
      (s) => s.probeKind !== "render" && s.probeKind !== "vercel",
    );
    return { platformRows: platformRowsInner, otherRows: otherRowsInner };
  }, [services]);

  const summary = useMemo(
    () => deriveSummary(services, platformSummary),
    [services, platformSummary],
  );

  const vercelRows = useMemo(
    () => platformRows.filter((s) => s.probeKind === "vercel"),
    [platformRows],
  );
  const renderRows = useMemo(
    () => platformRows.filter((s) => s.probeKind === "render"),
    [platformRows],
  );

  const renderBySubgroup = useMemo(() => {
    const apis: InfraService[] = [];
    const workers: InfraService[] = [];
    const data: InfraService[] = [];
    const other: InfraService[] = [];
    for (const r of renderRows) {
      if (RENDER_APIS_WEB.has(r.service)) apis.push(r);
      else if (RENDER_WORKERS.has(r.service)) workers.push(r);
      else if (RENDER_DATA.has(r.service)) data.push(r);
      else other.push(r);
    }
    return { apis, workers, data, other };
  }, [renderRows]);

  const coreHealthRows = useMemo(
    () => otherRows.filter((s) => CORE_HEALTH_PROBE_NAMES.has(s.service)),
    [otherRows],
  );
  const supplementaryRows = useMemo(
    () => otherRows.filter((s) => !CORE_HEALTH_PROBE_NAMES.has(s.service)),
    [otherRows],
  );

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await fetch("/api/admin/infrastructure");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as {
        services: InfraService[];
        platformSummary?: PlatformHealthSummary;
        platformPartial?: string[];
        checkedAt: string;
      };
      setServices(data.services);
      if (data.platformSummary) setPlatformSummary(data.platformSummary);
      if (data.platformPartial) setPlatformPartial(data.platformPartial);
      setCheckedAt(data.checkedAt);
      setRefreshError(null);
      setQuotaRefresh((q) => q + 1);
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(refresh, AUTO_REFRESH_MS);
    return () => clearInterval(interval);
  }, [autoRefresh, refresh]);

  const healthyCount = supplementaryRows.filter((s) => s.healthy).length;
  const configuredCount = supplementaryRows.filter((s) => s.configured).length;
  const degradedCount = supplementaryRows.filter((s) => s.configured && !s.healthy).length;

  const r = summary.render;
  const v = summary.vercel;
  const hasRender = r.total > 0;
  const hasVercel = v.total > 0;
  const renderLine = hasRender
    ? `Render: ${r.live}/${r.total} live${
        r.building > 0 ? `, ${r.building} building` : ""
      }${r.failed > 0 ? `, ${r.failed} failed` : ""}${r.suspended > 0 ? `, ${r.suspended} suspended` : ""}`
    : "Render: (no API data — set RENDER_API_KEY)";

  const vercelLine = hasVercel
    ? `Vercel: ${v.live}/${v.total} live${v.building > 0 ? `, ${v.building} building` : ""}${
        v.failed > 0 ? `, ${v.failed} failed` : ""
      }`
    : vercelMonorepoNamesConfigured
      ? "Vercel: (no API data — set VERCEL_API_TOKEN + team)"
      : "Vercel: set VERCEL_MONOREPO_PROJECT_NAMES to enable project cards";

  const allHealthy = degradedCount === 0 && supplementaryRows.length > 0 && healthyCount === supplementaryRows.length;
  const hasDegraded = degradedCount > 0;

  const grouped = new Map<string, InfraService[]>();
  const supplementaryForCategories = supplementaryRows.filter((s) => !CORE_HEALTH_PROBE_NAMES.has(s.service));
  for (const s of supplementaryForCategories) {
    const list = grouped.get(s.category) ?? [];
    list.push(s);
    grouped.set(s.category, list);
  }

  const categoryOrder = ["core", "frontend", "ops", "hosting", "data", "cache"];

  const quickJump = platformRows.filter((p) => p.stateLabel && p.stateLabel !== "live" && p.anchorId && !p.deprecated);

  const showVercelMissingCred = !vercelMonorepoNamesConfigured;
  const vercelCardsToShow = showVercelMissingCred ? [] : vercelRows;

  const router = useRouter();
  const pathname = usePathname() ?? "/admin/infrastructure";
  const searchParams = useSearchParams();
  const infraView: InfraInnerView =
    searchParams.get(INFRA_VIEW_PARAM) === "logs" ? "logs" : "dashboard";

  const setInfraView = useCallback(
    (next: InfraInnerView) => {
      const p = new URLSearchParams(searchParams.toString());
      if (next === "dashboard") p.delete(INFRA_VIEW_PARAM);
      else p.set(INFRA_VIEW_PARAM, next);
      const qs = p.toString();
      const href = qs ? `${pathname}?${qs}` : pathname;
      router.replace(href, { scroll: false });
    },
    [router, pathname, searchParams],
  );

  return (
    <div className="space-y-10" suppressHydrationWarning>
      <div
        className="flex flex-wrap gap-2 rounded-xl border border-zinc-800 bg-zinc-950/40 p-2"
        role="toolbar"
        aria-label="Services workspace"
      >
        <button
          type="button"
          data-testid="infra-inner-view-dashboard"
          aria-pressed={infraView === "dashboard"}
          onClick={() => setInfraView("dashboard")}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
            infraView === "dashboard"
              ? "bg-zinc-700 text-zinc-100"
              : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          }`}
        >
          Dashboard
        </button>
        <button
          type="button"
          data-testid="infra-inner-view-logs"
          aria-pressed={infraView === "logs"}
          onClick={() => setInfraView("logs")}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
            infraView === "logs"
              ? "bg-zinc-700 text-zinc-100"
              : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          }`}
        >
          Logs
        </button>
      </div>
      {infraView === "logs" ? (
        <LogsTab />
      ) : (
        <>
          <section
            className="rounded-xl border border-zinc-800 p-4"
            data-testid="infra-health-summary"
            aria-label="Platform health summary"
          >
        <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
          <Layers className="h-3.5 w-3.5" />
          Deploy platform (source of truth)
        </div>
        <p className="text-sm text-zinc-200" data-testid="infra-summary-render">
          {renderLine}
        </p>
        <p className="mt-1 text-sm text-zinc-200" data-testid="infra-summary-vercel">
          {vercelLine}
        </p>
        {quickJump.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
            <span className="w-full">Quick jump to issues:</span>
            {quickJump.map((p) => (
              <a
                key={p.anchorId}
                href={`#${p.anchorId}`}
                className="rounded border border-[var(--status-danger)]/50 bg-[var(--status-danger-bg)] px-2 py-0.5 text-[var(--status-danger)] hover:bg-[color-mix(in_srgb,var(--status-danger-bg)_150%,transparent)]"
              >
                {p.service}
              </a>
            ))}
          </div>
        )}
        {platformPartial.length > 0 && (
          <p className="mt-2 text-xs text-[var(--status-warning)]/90">
            Partial API notes: {platformPartial.join(" · ")}
          </p>
        )}
      </section>

      {/* Vercel */}
      <section className="space-y-4" aria-label="Vercel frontends">
        <SectionHeader
          title="Vercel"
          icon={Globe}
          pill={vercelRollupPill(v, vercelMonorepoNamesConfigured)}
        />
        {showVercelMissingCred ? (
          <HqMissingCredCard
            service="Vercel"
            envVar="VERCEL_MONOREPO_PROJECT_NAMES"
            description={`Set this env var on the Studio Vercel project so we can surface real projects (replaces per-project MISSING placeholders). Suggested value: ${SUGGESTED_VERCEL_MONOREPO_PROJECT_NAMES_CSV}.`}
            reconnectAction={{
              label: "Set env var (Vercel dashboard)",
              href: "https://vercel.com/paperwork-labs/studio/settings/environment-variables",
            }}
            docsLink={DAY0_VERCEL_MONOREPO_DOCS_HREF}
          />
        ) : null}
        {!showVercelMissingCred && vercelCardsToShow.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2">
            {vercelCardsToShow.map((svc) => (
              <div
                key={svc.service + (svc.anchorId ?? "") + (svc.probeKind ?? "")}
                data-testid="infra-probe-row"
              >
                <ServiceCard svc={svc} />
              </div>
            ))}
          </div>
        ) : null}
        {!showVercelMissingCred && vercelCardsToShow.length === 0 ? (
          <HqEmptyState
            title="No Vercel project rows"
            description="VERCEL_MONOREPO_PROJECT_NAMES is set but no matching projects were returned — check VERCEL_API_TOKEN, team scope, and slug spellings."
          />
        ) : null}
        <QuotaVercelPanel refreshSignal={quotaRefresh} />
      </section>

      {/* Render */}
      <section className="space-y-4" aria-label="Render backends and data">
        <SectionHeader title="Render" icon={Layers} pill={renderRollupPill(renderRows)} />
        <div className="space-y-6">
          {renderBySubgroup.apis.length ? (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">APIs / Web</p>
              <div className="grid gap-3 md:grid-cols-2">
                {renderBySubgroup.apis.map((svc) => (
                  <div key={svc.anchorId} data-testid="infra-probe-row">
                    <ServiceCard svc={svc} />
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {renderBySubgroup.workers.length ? (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Workers</p>
              <div className="grid gap-3 md:grid-cols-2">
                {renderBySubgroup.workers.map((svc) => (
                  <div key={svc.anchorId} data-testid="infra-probe-row">
                    <ServiceCard svc={svc} />
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {renderBySubgroup.data.length ? (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Data</p>
              <div className="grid gap-3 md:grid-cols-2">
                {renderBySubgroup.data.map((svc) => (
                  <div key={svc.anchorId} data-testid="infra-probe-row">
                    <ServiceCard svc={svc} />
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {renderBySubgroup.other.length ? (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Other services</p>
              <div className="grid gap-3 md:grid-cols-2">
                {renderBySubgroup.other.map((svc) => (
                  <div key={svc.anchorId} data-testid="infra-probe-row">
                    <ServiceCard svc={svc} />
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
        <QuotaRenderPanel refreshSignal={quotaRefresh} />

        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Health probes</p>
          <div className="grid gap-3 md:grid-cols-2">
            {coreHealthRows.map((svc) => (
              <SupplementaryCard key={svc.service} svc={svc} />
            ))}
          </div>
        </div>
      </section>

      {/* Hetzner */}
      <section className="space-y-4" aria-label="Hetzner dedicated servers">
        <SectionHeader title="Hetzner" icon={Server} pill="3 boxes" />
        <p className="text-xs text-zinc-500">
          Dedicated VMs in Helsinki — status is assumed (no browser-side SSH). Compose references are repo paths.
        </p>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {HETZNER_BOXES.map((box) => (
            <Card key={box.hostname} className="border border-zinc-800">
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold text-zinc-100">{box.hostname}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-2">
                      <span className="rounded border border-zinc-600 bg-zinc-900/80 px-2 py-0.5 font-mono text-xs text-zinc-300">
                        {box.plan}
                      </span>
                      <span className="text-xs text-zinc-500">
                        {box.vcpus} vCPU · {box.memoryGb} GB RAM
                      </span>
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="relative inline-block h-2.5 w-2.5">
                      <span className="absolute inset-0 motion-safe:animate-ping rounded-full bg-[var(--status-success)] opacity-40" />
                      <span className="relative inline-block h-2.5 w-2.5 rounded-full bg-[var(--status-success)]" />
                    </span>
                    <span className="text-[10px] font-medium uppercase tracking-wide text-[var(--status-success)]">
                      Assumed up
                    </span>
                  </div>
                </div>
                <p className="mt-2 font-mono text-sm text-zinc-300">{box.ip}</p>
                <p className="mt-2 text-sm text-zinc-400">{box.role}</p>
                <p className="mt-2 text-xs text-zinc-500">
                  Last probed: N/A — SSH-only
                </p>
                <p className="mt-1 text-xs text-zinc-600">
                  <span className="font-mono text-zinc-500">{box.composeFile}</span>
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <a
                    href="https://console.hetzner.cloud/"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-zinc-500 transition hover:text-zinc-300"
                  >
                    Hetzner Cloud console <ExternalLink className="h-3 w-3" />
                  </a>
                  <span className="text-xs tabular-nums text-zinc-500">
                    ~${box.monthlyCostEur.toFixed(2)}/mo est.
                  </span>
                </div>
                {box.dockerServices.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {box.dockerServices.map((name) => (
                      <span
                        key={name}
                        className="rounded-full border border-zinc-700 bg-zinc-900/60 px-2 py-0.5 font-mono text-[10px] text-zinc-400"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* API providers (PR-10) */}
      <section className="space-y-4" aria-label="API providers">
        <SectionHeader title="API providers" icon={Cpu} pill="Ledger on Cost tab" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {API_PROVIDER_CARDS.map((p) => (
            <HqEmptyState
              key={p.name}
              title={p.name}
              description="Quota wire-up coming in WS-76 PR-10."
              action={{ label: "Open vendor console", href: p.consoleHref }}
            />
          ))}
        </div>
      </section>

      {/* Supplementary / synthetic */}
      <section className="space-y-3" aria-label="Reachability and integrations">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
          <Server className="h-3.5 w-3.5" />
          Reachability & tokens
        </div>
        <div
          className={`inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-medium ${
            allHealthy
              ? "border-[var(--status-success)]/40 bg-[var(--status-success-bg)] text-[var(--status-success)]"
              : hasDegraded
                ? "border border-[var(--status-danger)]/40 bg-[var(--status-danger-bg)] text-[var(--status-danger)]"
                : "border border-[var(--status-warning)]/40 bg-[var(--status-warning-bg)] text-[var(--status-warning)]"
          }`}
        >
          <StatusDot
            healthy={allHealthy}
            configured={supplementaryRows.length === 0 || configuredCount === supplementaryRows.length}
          />
          {allHealthy
            ? "All supplementary checks green"
            : hasDegraded
              ? `${degradedCount} check${degradedCount > 1 ? "s" : ""} degraded (below)`
              : "Supplementary checks"}
        </div>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
          <HqStatCard
            label="Supplementary / HTTP"
            value={`${healthyCount}/${supplementaryRows.length}`}
            helpText="Public URLs, tokens, and sidecar checks"
            status={
              supplementaryRows.length === 0
                ? "neutral"
                : healthyCount === supplementaryRows.length
                  ? "success"
                  : hasDegraded
                    ? "danger"
                    : "warning"
            }
          />
          <HqStatCard
            label="Degraded (below)"
            value={degradedCount}
            helpText="HTTP / token checks"
            status={degradedCount > 0 ? "danger" : "success"}
          />
          <HqStatCard
            label="Platform rows"
            value={platformRows.length}
            helpText="Render + Vercel API-backed"
            status="neutral"
          />
        </div>
        <div className="space-y-6">
          {categoryOrder.map((cat) => {
            const catServices = grouped.get(cat);
            if (!catServices?.length) return null;
            const meta = categoryMeta[cat] ?? { label: cat, icon: Server };
            const CatIcon = meta.icon;
            return (
              <div key={cat}>
                <div className="mb-3 flex items-center gap-2">
                  <CatIcon className="h-4 w-4 text-zinc-500" />
                  <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">{meta.label}</p>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {catServices.map((svc) => (
                    <SupplementaryCard key={svc.service} svc={svc} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section
        id="infra-quotas"
        data-testid="infra-quota-panels"
        aria-label="Vendor quota snapshots via Brain API"
      >
        <div className="mb-3">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">GitHub Actions</p>
          <p className="mt-1 text-sm text-zinc-400">
            Org billing minutes · paid runners · Actions cache footprint (cross-repo).
          </p>
        </div>
        <QuotaGitHubActionsPanel refreshSignal={quotaRefresh} />
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-800 px-4 py-3">
        <div className="flex items-center gap-3 text-sm text-zinc-400">
          <Radio className="h-3.5 w-3.5" />
          <span>
            Last checked:{" "}
            <span className="text-zinc-200" suppressHydrationWarning>
              {formatTimePT(checkedAt)} PT
            </span>
          </span>
          <label className="flex cursor-pointer items-center gap-1.5 text-xs">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="h-3 w-3 rounded border-zinc-600 bg-zinc-800 accent-[var(--status-success)]"
            />
            Auto-refresh 30s
          </label>
          {refreshError ? (
            <span className="ml-3 rounded-full border border-[var(--status-danger)]/40 bg-[var(--status-danger-bg)] px-2 py-0.5 text-xs text-[var(--status-danger)]">
              Refresh failed: {refreshError}
            </span>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 transition hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "motion-safe:animate-spin" : ""}`} />
          Refresh
        </button>
      </div>
        </>
      )}
    </div>
  );
}
