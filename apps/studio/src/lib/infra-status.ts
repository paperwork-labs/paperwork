/**
 * Infra UI status semantics — derives honest multi-state probes from Infra API rows + scan staleness.
 */
import type { InfraStatus } from "@/lib/infra-types";
import type { StatusLevel } from "@/styles/design-tokens";

export type ServiceStatus = "ok" | "degraded" | "down" | "missing_cred" | "stale" | "unknown";

export type ServiceProbeResult = {
  service: string;
  vendor: string;
  status: ServiceStatus;
  latencyMs: number | null;
  lastChecked: string;
  error: string | null;
  url: string | null;
};

/** HTTP latency at or above this (ms) counts as degraded when the endpoint still responds OK. */
export const INFRA_DEGRADED_LATENCY_MS = 1000;

/** Whole-scan age after which readings are surfaced as stale. */
export const INFRA_STALE_SCAN_MS = 3 * 60 * 1000;

export type InfraAggregateCounts = {
  total: number;
  ok: number;
  degraded: number;
  down: number;
  missingCred: number;
  stale: number;
  unknown: number;
};

function isPlatformRow(svc: InfraStatus): svc is InfraStatus & { probeKind: "render" | "vercel" } {
  return svc.probeKind === "render" || svc.probeKind === "vercel";
}

/** Display vendor for infra table rollup (capitalized pillar). */
export function infraVendorLabel(svc: InfraStatus): string {
  if (svc.probeKind === "vercel") return "Vercel";
  if (svc.probeKind === "render") return "Render";
  if (svc.service === "Hetzner Cloud") return "Hetzner";
  if (svc.dashboardUrl?.includes("neon.tech")) return "Neon";
  if (svc.dashboardUrl?.includes("slack.com")) return "Slack";
  if (svc.dashboardUrl?.includes("upstash.com")) return "Upstash";
  if (svc.service.includes("Postiz")) return "Hosting";
  if (svc.dashboardUrl?.includes("vercel.com")) return "Vercel";
  if (svc.dashboardUrl?.includes("render.com")) return "Render";
  return "Connectivity";
}

/**
 * Maps ServiceStatus → StatusDot / StatusBadge `status` tier.
 * Use extra opacity on the row/dot for STALE beyond this mapping when needed.
 */
export function serviceStatusLevel(status: ServiceStatus): StatusLevel {
  switch (status) {
    case "ok":
      return "success";
    case "degraded":
    case "stale":
      return "warning";
    case "down":
      return "danger";
    case "missing_cred":
      return "neutral";
    case "unknown":
    default:
      return "neutral";
  }
}

function platformBaseStatus(svc: InfraStatus): Exclude<ServiceStatus, "stale"> {
  const label = svc.stateLabel;
  if (label === "building") return "degraded";
  if (label === "failed") return "down";
  if (label === "suspended") return "down";
  if (label === "live") return svc.healthy ? "ok" : "down";
  return svc.healthy ? "ok" : "down";
}

function supplementaryBaseStatus(svc: InfraStatus): Exclude<ServiceStatus, "stale"> {
  if (!svc.configured) return "missing_cred";
  if (!svc.healthy) return "down";
  if (svc.latencyMs != null && svc.latencyMs >= INFRA_DEGRADED_LATENCY_MS) return "degraded";
  return "ok";
}

function deriveBaseStatus(svc: InfraStatus): Exclude<ServiceStatus, "stale"> | "unknown" {
  if (!svc.configured) return "missing_cred";
  if (isPlatformRow(svc)) return platformBaseStatus(svc);
  return supplementaryBaseStatus(svc);
}

function applyStale(
  status: Exclude<ServiceStatus, "stale"> | "unknown",
  scanStale: boolean,
): ServiceStatus {
  if (status === "missing_cred") return status;
  if (scanStale) return "stale";
  return status;
}

export function scanAgeMs(lastCheckedIso: string, nowMs: number = Date.now()): number {
  const t = Date.parse(lastCheckedIso);
  if (!Number.isFinite(t)) return 0;
  return Math.max(0, nowMs - t);
}

export function scanIsStale(lastCheckedIso: string, nowMs?: number): boolean {
  return scanAgeMs(lastCheckedIso, nowMs) > INFRA_STALE_SCAN_MS;
}

export function formatRelativeMinutesAgo(iso: string, nowMs: number = Date.now()): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "unknown";
  const sec = Math.max(1, Math.floor((nowMs - t) / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} minute${min === 1 ? "" : "s"} ago`;
  const h = Math.floor(min / 60);
  return `${h} hour${h === 1 ? "" : "s"} ago`;
}

export function infraRowToProbeResult(
  svc: InfraStatus,
  lastCheckedIso: string,
  options?: { url?: string | null; scanStale?: boolean; nowMs?: number },
): ServiceProbeResult {
  const vendor = infraVendorLabel(svc);
  const scanStale =
    options?.scanStale ?? scanIsStale(lastCheckedIso, options?.nowMs);
  const base = deriveBaseStatus(svc);
  const status = applyStale(base, scanStale);

  let error: string | null = null;
  if (status === "missing_cred") error = "credentials needed";
  else if (status === "stale") {
    error = `last checked ${formatRelativeMinutesAgo(lastCheckedIso, options?.nowMs)}`;
  } else if (status === "down") {
    error = svc.detail ?? "Down";
  } else if (status === "degraded") {
    if (isPlatformRow(svc) && svc.stateLabel === "building") error = "deploy in progress";
    else if (svc.latencyMs != null && svc.latencyMs >= INFRA_DEGRADED_LATENCY_MS) error = "slow";
    else error = svc.detail;
  }

  return {
    service: svc.service,
    vendor,
    status,
    latencyMs: svc.latencyMs ?? null,
    lastChecked: lastCheckedIso,
    error,
    url: options?.url ?? null,
  };
}

export function tallyProbeStatuses(rows: ServiceProbeResult[]): InfraAggregateCounts {
  const c: InfraAggregateCounts = {
    total: rows.length,
    ok: 0,
    degraded: 0,
    down: 0,
    missingCred: 0,
    stale: 0,
    unknown: 0,
  };
  for (const r of rows) {
    switch (r.status) {
      case "ok":
        c.ok++;
        break;
      case "degraded":
        c.degraded++;
        break;
      case "down":
        c.down++;
        break;
      case "missing_cred":
        c.missingCred++;
        break;
      case "stale":
        c.stale++;
        break;
      default:
        c.unknown++;
    }
  }
  return c;
}

export function vendorHealthyCounts(rows: ServiceProbeResult[]): {
  ok: number;
  total: number;
} {
  let ok = 0;
  for (const r of rows) {
    if (r.status === "ok") ok++;
  }
  return { ok, total: rows.length };
}

export function formatVendorRollup(rows: ServiceProbeResult[]): string {
  if (rows.length === 0) return "no rows";
  if (rows.every((r) => r.status === "missing_cred")) return "credentials needed";
  const { ok, total } = vendorHealthyCounts(rows);
  return `${ok} of ${total} services healthy`;
}

export function probeRowAccentClass(status: ServiceStatus): string {
  switch (status) {
    case "ok":
      return "border-l-4 border-l-[var(--status-success)]/70 bg-[var(--status-success-bg)]/25";
    case "degraded":
      return "border-l-4 border-l-[var(--status-warning)]/70 bg-[var(--status-warning-bg)]/22";
    case "stale":
      return "border-l-4 border-l-[var(--status-warning)]/50 bg-[var(--status-warning-bg)]/14 opacity-90";
    case "down":
      return "border-l-4 border-l-[var(--status-danger)]/70 bg-[var(--status-danger-bg)]/22";
    case "missing_cred":
      return "border-l-4 border-l-zinc-600 bg-zinc-900/50";
    default:
      return "border-l-4 border-l-zinc-600 bg-zinc-900/40";
  }
}
