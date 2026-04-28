/**
 * Validates an in-app return path from query params (e.g. `returnTo`, Clerk `redirect_url`).
 * Rejects non-path URLs, open redirects, and auth entry routes.
 */
export function safeAppReturnPath(raw: string | null): string | null {
  if (raw == null || raw === "") return null;
  let decoded: string;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    return null;
  }
  if (!decoded.startsWith("/") || decoded.startsWith("//")) return null;
  const pathOnly = decoded.split(/[?#]/)[0];
  const blocked = new Set([
    "/login",
    "/register",
    "/sign-in",
    "/sign-up",
    "/auth/callback",
  ]);
  if (blocked.has(pathOnly)) return null;
  return decoded;
}
