import {
  BRAIN_HEALTH_DEGRADED_LATENCY_MS,
  checkBrainHealth,
} from "@/lib/brain-health";

import { BrainStatusBannerClient } from "./BrainStatusBannerClient";

/**
 * Server component: checks Brain `/health` (cached 30s in `checkBrainHealth`).
 * Renders nothing when Brain is healthy and responsive.
 */
export async function BrainStatusBanner() {
  const health = await checkBrainHealth();

  const showDown = !health.reachable || health.error != null;
  const showDegraded =
    health.reachable &&
    health.latencyMs != null &&
    health.latencyMs >= BRAIN_HEALTH_DEGRADED_LATENCY_MS;

  if (showDown) {
    return <BrainStatusBannerClient variant="down" />;
  }
  if (showDegraded) {
    return <BrainStatusBannerClient variant="degraded" />;
  }
  return null;
}
