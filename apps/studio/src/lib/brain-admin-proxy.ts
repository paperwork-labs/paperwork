/**
 * Brain admin API is mounted at `{BRAIN_API_URL}/api/v1/admin/...` (see `apis/brain/app/main.py`).
 * Studio proxies these with `X-Brain-Secret` for server-side admin pages.
 */

function sanitizeEnv(val: string | undefined): string {
  if (!val) return "";
  return val.trim().replace(/\\n$/, "").replace(/\/+$/, "");
}

export function brainApiV1Root(): string | null {
  const raw = sanitizeEnv(process.env.BRAIN_API_URL);
  if (!raw) return null;
  return raw.endsWith("/api/v1") ? raw : `${raw}/api/v1`;
}

export type BrainAdminAuth = { ok: true; root: string; secret: string } | { ok: false };

export function getBrainAdminFetchOptions(): BrainAdminAuth {
  const root = brainApiV1Root();
  const secret = sanitizeEnv(process.env.BRAIN_API_SECRET);
  if (!root || !secret) return { ok: false };
  return { ok: true, root, secret };
}
