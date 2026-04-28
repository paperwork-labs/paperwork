import type { InfrastructureView, InfraStatus } from "@/lib/infra-types";

/** Platform rows aligned with root `render.yaml` + `VERCEL_MONOREPO_PROJECT_NAMES` (E2E / CI). */
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
  const v = (name: string, ok: boolean): InfraStatus => ({
    service: name,
    category: "hosting",
    configured: true,
    healthy: ok,
    detail: ok ? "Vercel production · ready · a1b2c3d" : "Vercel production · error",
    latencyMs: null,
    dashboardUrl: `https://vercel.com/paperwork-labs/${name}`,
    probeKind: "vercel",
    platformType: "vercel-project",
    stateLabel: ok ? "live" : "failed",
    deployState: ok ? "ready" : "error",
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
    r("axiomfolio-db", "postgres", "live"),
    r("axiomfolio-redis", "redis", "live"),
    v("studio", true),
    v("filefree", true),
    v("launchfree", true),
    v("distill", true),
    v("trinkets", true),
    v("axiomfolio", true),
  ];
  return {
    services: platformRows,
    platformSummary: {
      render: { live: 6, building: 0, failed: 1, suspended: 0, total: 7 },
      vercel: { live: 6, building: 0, failed: 1, suspended: 0, total: 6 },
    },
    platformPartial: [],
  };
}
