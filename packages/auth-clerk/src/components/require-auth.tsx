"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { useRouter, usePathname } from "next/navigation";

/**
 * Client-side auth guard. Redirects to `/sign-in?redirect_url=<current>` when
 * Clerk reports the user is not signed in. Shows `fallback` (or nothing) while
 * Clerk is hydrating so we never flash protected content.
 *
 * Most apps should also have a `clerkMiddleware` route gate in
 * `src/middleware.ts` — this guard is the in-page belt-and-suspenders.
 */
export interface RequireAuthProps {
  children: ReactNode;
  /**
   * Where to send unauthenticated visitors. Defaults to `"/sign-in"`.
   */
  signInUrl?: string;
  /** Rendered while Clerk is loading. Defaults to `null`. */
  fallback?: ReactNode;
  /** Rendered between detection + redirect. Defaults to `fallback`. */
  redirectingFallback?: ReactNode;
}

export function RequireAuth({
  children,
  signInUrl = "/sign-in",
  fallback = null,
  redirectingFallback,
}: RequireAuthProps) {
  const { isLoaded, isSignedIn } = useUser();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      const redirectUrl = pathname || "/";
      const target = `${signInUrl}?redirect_url=${encodeURIComponent(redirectUrl)}`;
      router.replace(target);
    }
  }, [isLoaded, isSignedIn, pathname, router, signInUrl]);

  if (!isLoaded) return <>{fallback}</>;
  if (!isSignedIn) return <>{redirectingFallback ?? fallback}</>;
  return <>{children}</>;
}
