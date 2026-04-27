import type { InfrastructureView, InfraStatus } from "@/lib/infra-types";

/** Nine platform rows: eight Render (incl. Postgres + Redis) + one Vercel (E2E / CI). */
export function getE2EInfrastructureFixture(): InfrastructureView {
  const r = (
    name: string,
    type: string,
    st: "live" | "building" | "failed" | "suspended",
  ): InfraStatus => {
    const healthy = st === "live" || st === "building";
    return {
      service: name,
      category: "hosting",
      configured: true,
      healthy,
      detail: `Render · ${type} · ${st === "failed" ? "build_failed" : "live"} · f025554`,
      latencyMs: null,
      dashboardUrl: "https://dashboard.render.com",
      probeKind: "render",
      platformType: type,
      stateLabel: st,
      deployState: st === "failed" ? "build_failed" : "live",
      commitSha: "f0255542",
      lastDeployedAt: new Date().toISOString(),
      anchorId: `render-mock-${name.replace(/[^a-z0-9-]/gi, "-")}`,
    };
  };
  const v = (name: string): InfraStatus => ({
    service: name,
    category: "hosting",
    configured: true,
    healthy: true,
    detail: "Vercel production · ready · a1b2c3d",
    latencyMs: null,
    dashboardUrl: `https://vercel.com/paperwork-labs/${name}`,
    probeKind: "vercel",
    platformType: "vercel-project",
    stateLabel: "live",
    deployState: "ready",
    commitSha: "a1b2c3d",
    lastDeployedAt: new Date().toISOString(),
    anchorId: `vercel-mock-${name}`,
  });
  const platformRows: InfraStatus[] = [
    r("brain-api", "web", "live"),
    r("filefree-api", "web", "live"),
    r("axiomfolio-api", "web", "failed"),
    r("axiomfolio-worker", "worker", "live"),
    r("axiomfolio-worker-heavy", "worker", "live"),
    r("axiomfolio-frontend", "static", "live"),
    r("axiomfolio-db", "postgres", "live"),
    r("axiomfolio-redis", "redis", "live"),
    v("studio"),
  ];
  return {
    services: platformRows,
    platformSummary: {
      render: { live: 7, building: 0, failed: 1, suspended: 0, total: 8 },
      vercel: { live: 1, building: 0, failed: 0, suspended: 0, total: 1 },
    },
    platformPartial: [],
  };
}
