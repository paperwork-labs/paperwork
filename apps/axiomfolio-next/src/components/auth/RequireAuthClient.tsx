"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

/**
 * Client-side auth gate matching Vite `RequireAuth` (redirect to `/login` when no `qm_token`).
 */
export function RequireAuthClient({ children }: { children: React.ReactNode }) {
  const { token, ready } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  React.useEffect(() => {
    if (!ready || token) return;
    const search = typeof window !== "undefined" ? window.location.search : "";
    const returnTo = `${pathname}${search}`;
    router.replace(`/login?returnTo=${encodeURIComponent(returnTo)}`);
  }, [ready, token, router, pathname]);

  if (!ready) {
    return null;
  }
  if (!token) {
    return null;
  }
  return <>{children}</>;
}
