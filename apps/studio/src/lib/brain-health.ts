import { unstable_cache } from "next/cache";

const HEALTH_PATH = "/health";
const FETCH_TIMEOUT_MS = 3_000;
/** Responses slower than this still succeed but are treated as degraded (amber). */
export const BRAIN_HEALTH_DEGRADED_LATENCY_MS = 2_000;

export type BrainHealthResult = {
  reachable: boolean;
  latencyMs: number | null;
  error: string | null;
};

function brainServiceRootFromEnv(): string | null {
  const raw = process.env.BRAIN_API_URL?.trim();
  if (!raw) return null;
  return raw.replace(/\/+$/, "");
}

async function fetchBrainHealthUncached(): Promise<BrainHealthResult> {
  const root = brainServiceRootFromEnv();
  if (!root) {
    return { reachable: true, latencyMs: null, error: null };
  }

  const url = `${root}${HEALTH_PATH}`;
  const started = performance.now();

  try {
    const res = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    const latencyMs = Math.round(performance.now() - started);

    if (!res.ok) {
      return {
        reachable: false,
        latencyMs,
        error: `HTTP ${res.status}`,
      };
    }

    let json: unknown;
    try {
      json = await res.json();
    } catch {
      return {
        reachable: false,
        latencyMs,
        error: "Invalid JSON from Brain /health",
      };
    }

    const success =
      typeof json === "object" &&
      json !== null &&
      (json as { success?: unknown }).success === true;
    if (!success) {
      return {
        reachable: false,
        latencyMs,
        error: "Brain /health did not return success",
      };
    }

    return { reachable: true, latencyMs, error: null };
  } catch (e) {
    const latencyMs = Math.round(performance.now() - started);
    const message = e instanceof Error ? e.message : "network error";
    const timedOut =
      e instanceof Error &&
      (message.includes("aborted") ||
        message.includes("AbortError") ||
        message.includes("timeout"));
    return {
      reachable: false,
      latencyMs: timedOut ? null : latencyMs,
      error: timedOut ? "Request timed out" : message,
    };
  }
}

const getBrainHealthCached = unstable_cache(fetchBrainHealthUncached, ["brain-admin-health"], {
  revalidate: 30,
});

/**
 * Checks Brain `GET {BRAIN_API_URL}/health` with a 3s timeout.
 * Result is cached for 30s per deployment (see `unstable_cache` revalidate).
 */
export async function checkBrainHealth(): Promise<BrainHealthResult> {
  return getBrainHealthCached();
}
