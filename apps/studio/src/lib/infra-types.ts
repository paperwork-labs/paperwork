/**
 * Infra / command-center shared types (avoids circular imports with infra-probes).
 */

export type PlatformProbeKind = "standard" | "render" | "vercel";
export type PlatformState = "live" | "building" | "failed" | "suspended";

export type InfraStatus = {
  service: string;
  category: "core" | "frontend" | "ops" | "data" | "cache" | "hosting";
  configured: boolean;
  healthy: boolean;
  detail: string;
  latencyMs: number | null;
  dashboardUrl: string | null;
  consoleUrl?: string | null;
  /** Render / Vercel API–backed platform rows; synthetic probes omit this. */
  probeKind?: PlatformProbeKind;
  /** e.g. web, worker, static, vercel-project, postgres, redis, keyvalue */
  platformType?: string;
  stateLabel?: PlatformState;
  /** Raw provider deploy state (e.g. `live`, `build_failed`, `ready`). */
  deployState?: string;
  commitSha?: string | null;
  lastDeployedAt?: string | null;
  /** In-page hash anchor, e.g. `render-srv-abc`. */
  anchorId?: string;
};

export type PlatformStateCounts = {
  live: number;
  building: number;
  failed: number;
  suspended: number;
  total: number;
};

export type PlatformHealthSummary = {
  /** Every Render service + Postgres + Key Value row. */
  render: PlatformStateCounts;
  vercel: PlatformStateCounts;
};

export type InfrastructureView = {
  services: InfraStatus[];
  platformSummary: PlatformHealthSummary;
  platformPartial: string[];
};
