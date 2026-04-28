/**
 * Brain admin API is mounted at `{BRAIN_API_URL}/api/v1/admin/...` (see `apis/brain/app/main.py`).
 * Studio proxies these with `X-Brain-Secret` for server-side admin pages.
 */

export function brainApiV1Root(): string | null {
  const raw = process.env.BRAIN_API_URL?.trim().replace(/\/+$/, "");
  if (!raw) return null;
  return raw.endsWith("/api/v1") ? raw : `${raw}/api/v1`;
}

export type BrainAdminAuth = { ok: true; root: string; secret: string } | { ok: false };

export function getBrainAdminFetchOptions(): BrainAdminAuth {
  const root = brainApiV1Root();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!root || !secret) return { ok: false };
  return { ok: true, root, secret };
}
