"use client";

import * as React from "react";
import { useUser } from "@clerk/nextjs";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/context/AuthContext";

/**
 * Dual-mode client gate (WS-14): Clerk session OR legacy `qm_token`.
 * Mirrors `@paperwork-labs/auth-clerk` RequireAuth redirect shape (`/sign-in?redirect_url=…`).
 */
export function RequireAuthClient({ children }: { children: React.ReactNode }) {
  const { isLoaded: clerkLoaded, isSignedIn } = useUser();
  const { token, ready: legacyReady } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const legacyOk = legacyReady && !!token;
  const clerkOk = clerkLoaded && !!isSignedIn;
  const isLoaded = clerkLoaded && (isSignedIn || legacyReady);
  const allowed = clerkOk || legacyOk;

  React.useEffect(() => {
    if (!isLoaded || allowed) return;
    const search = typeof window !== "undefined" ? window.location.search : "";
    const returnPath = `${pathname}${search}`;
    router.replace(`/sign-in?redirect_url=${encodeURIComponent(returnPath)}`);
  }, [isLoaded, allowed, router, pathname]);

  if (!isLoaded) {
    return null;
  }
  if (!allowed) {
    return null;
  }
  return <>{children}</>;
}
