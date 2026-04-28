"use client";

import { useUser } from "@clerk/nextjs";

/**
 * Result of `useAdmin()`.
 *
 * `isLoaded` mirrors Clerk's user-loaded flag so callers can avoid flickering
 * "denied" UI before Clerk has hydrated; `isAdmin` is only meaningful after
 * `isLoaded` flips true.
 */
export interface UseAdminResult {
  isLoaded: boolean;
  isAdmin: boolean;
  email: string | null;
}

/**
 * Resolves the comma-separated `ADMIN_EMAILS` allow-list from a runtime env
 * source. Browser builds can't read `process.env.ADMIN_EMAILS` directly
 * (server-only), so we look at the standard `NEXT_PUBLIC_ADMIN_EMAILS` mirror
 * and fall back to a window-injected list (set by Studio's middleware on
 * authenticated admin shells when needed).
 */
function getAdminAllowList(override?: string): Set<string> {
  const raw =
    override ??
    process.env.NEXT_PUBLIC_ADMIN_EMAILS ??
    (typeof window !== "undefined"
      ? (window as unknown as { __PAPERWORK_ADMIN_EMAILS__?: string }).__PAPERWORK_ADMIN_EMAILS__ ?? ""
      : "");

  return new Set(
    raw
      .split(",")
      .map((email: string) => email.trim().toLowerCase())
      .filter(Boolean),
  );
}

/**
 * Composite admin gate: a Clerk-authenticated user is `isAdmin` iff their
 * `primaryEmailAddress` appears in the runtime allow-list.
 *
 * @example
 *   const { isLoaded, isAdmin } = useAdmin();
 *   if (!isLoaded) return null;
 *   if (!isAdmin) return <NotAuthorized />;
 *
 * @param adminEmailsOverride Optional comma-separated allow-list (testing).
 */
export function useAdmin(adminEmailsOverride?: string): UseAdminResult {
  const { isLoaded, isSignedIn, user } = useUser();
  const email = user?.primaryEmailAddress?.emailAddress?.toLowerCase() ?? null;
  const allowList = getAdminAllowList(adminEmailsOverride);
  const isAdmin = Boolean(isLoaded && isSignedIn && email && allowList.has(email));

  return { isLoaded, isAdmin, email };
}
