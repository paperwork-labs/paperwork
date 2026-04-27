import { NextResponse } from "next/server";
import { cached, getInfrastructureView } from "@/lib/command-center";
import { getE2EInfrastructureFixture } from "@/lib/e2e-infra-mock";

export const dynamic = "force-dynamic";

/** Keep below client auto-refresh (30s) so each tick can observe fresh deploy state. */
const CACHE_TTL = 25_000;

export async function GET() {
  if (process.env.STUDIO_E2E_FIXTURE === "1") {
    const e2e = getE2EInfrastructureFixture();
    return NextResponse.json({
      services: e2e.services,
      platformSummary: e2e.platformSummary,
      platformPartial: e2e.platformPartial,
      checkedAt: new Date().toISOString(),
    });
  }
  const view = await cached("admin:infrastructure", CACHE_TTL, getInfrastructureView);
  return NextResponse.json({
    services: view.services,
    platformSummary: view.platformSummary,
    platformPartial: view.platformPartial,
    checkedAt: new Date().toISOString(),
  });
}
