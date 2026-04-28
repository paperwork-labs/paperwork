"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";

import { useAdmin } from "../hooks/use-admin";

/**
 * Composite Clerk + ADMIN_EMAILS gate. Renders `children` only when:
 *   1. Clerk has loaded
 *   2. The user is signed in
 *   3. Their primary email is in the runtime allow-list
 *
 * Mirrors Studio's server-side middleware (`apps/studio/src/middleware.ts`)
 * for client-rendered admin surfaces (`/admin/*` pages that hydrate before
 * the middleware decision propagates).
 */
export interface RequireAdminProps {
  children: ReactNode;
  /** Where to redirect non-admin Clerk users. Defaults to `"/"`. */
  notAuthorizedUrl?: string;
  /** Where to redirect signed-out users. Defaults to `"/sign-in"`. */
  signInUrl?: string;
  /** Rendered while Clerk hydrates. Defaults to `null`. */
  fallback?: ReactNode;
  /** Comma-separated email override — primarily for tests. */
  adminEmailsOverride?: string;
}

export function RequireAdmin({
  children,
  notAuthorizedUrl = "/",
  signInUrl = "/sign-in",
  fallback = null,
  adminEmailsOverride,
}: RequireAdminProps) {
  const { isLoaded, isAdmin, email } = useAdmin(adminEmailsOverride);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoaded) return;
    if (isAdmin) return;

    if (!email) {
      const redirectUrl = pathname || "/";
      router.replace(`${signInUrl}?redirect_url=${encodeURIComponent(redirectUrl)}`);
    } else {
      router.replace(notAuthorizedUrl);
    }
  }, [isLoaded, isAdmin, email, pathname, router, signInUrl, notAuthorizedUrl]);

  if (!isLoaded || !isAdmin) return <>{fallback}</>;
  return <>{children}</>;
}
