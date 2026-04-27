/**
 * ADMIN_EMAILS is a comma-separated list (same as middleware and secrets Basic auth).
 */
export function getAdminEmailSet(): Set<string> {
  const raw = process.env.ADMIN_EMAILS || "";
  return new Set(
    raw
      .split(",")
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean),
  );
}

export function isAdminClerkEmail(email: string | null | undefined): boolean {
  if (!email) return false;
  return getAdminEmailSet().has(email.trim().toLowerCase());
}
