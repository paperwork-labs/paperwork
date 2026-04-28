"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { useRouter, usePathname } from "next/navigation";

import { useAuthStore } from "@/stores/auth-store";

/**
 * Consumer route guard (WS-13 dual-mode): Clerk session OR legacy `/api/v1/auth/me` session.
 * Redirects to Clerk sign-in with `redirect_url` when neither is present after hydration.
 */
export interface RequireAuthProps {
  children: ReactNode;
  signInUrl?: string;
  fallback?: ReactNode;
  redirectingFallback?: ReactNode;
}

export function RequireAuth({
  children,
  signInUrl = "/sign-in",
  fallback = null,
  redirectingFallback,
}: RequireAuthProps) {
  const { isLoaded: clerkLoaded, isSignedIn } = useUser();
  const { isAuthenticated, isLoading: legacyLoading } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();

  const ready = clerkLoaded && !legacyLoading;
  const allowed = Boolean(isSignedIn) || isAuthenticated;

  useEffect(() => {
    if (!ready) return;
    if (!allowed) {
      const redirectUrl = pathname || "/";
      const target = `${signInUrl}?redirect_url=${encodeURIComponent(redirectUrl)}`;
      router.replace(target);
    }
  }, [allowed, pathname, ready, router, signInUrl]);

  if (!ready) return <>{fallback}</>;
  if (!allowed) return <>{redirectingFallback ?? fallback}</>;
  return <>{children}</>;
}
