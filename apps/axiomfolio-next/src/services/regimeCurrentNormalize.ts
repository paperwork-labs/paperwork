/**
 * Normalizes GET /market-data/regime/current response bodies for callers that receive
 * `makeOptimizedRequest` output (FastAPI JSON), optional axios-style `{ data: { regime } }`,
 * or an already-unwrapped row with `regime_state`.
 *
 * Returns a regime object or null — never undefined.
 */
export function normalizeRegimeCurrentBody(raw: unknown): Record<string, unknown> | null {
  if (raw == null || typeof raw !== 'object') {
    return null;
  }
  const o = raw as Record<string, unknown>;
  let candidate: unknown;
  const inner = o.data;
  if (inner != null && typeof inner === 'object' && 'regime' in inner) {
    candidate = (inner as Record<string, unknown>).regime;
  } else {
    candidate = undefined;
  }
  if (candidate === undefined && 'regime' in o) {
    candidate = o.regime;
  }
  if ((candidate === undefined || candidate === null) && typeof o.regime_state === 'string') {
    return o;
  }
  if (candidate === undefined || candidate === null) {
    return null;
  }
  if (Array.isArray(candidate) || typeof candidate !== 'object') {
    return null;
  }
  return candidate as Record<string, unknown>;
}
