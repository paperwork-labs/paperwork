"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

const LAST_ROUTE_STORAGE_KEY = "qm.ui.last_route";

/**
 * Legacy hash-token callback route. Clerk uses hosted sign-in; this page only
 * restores the last in-app route when users land here without a token fragment.
 */
export default function AuthCallbackPage() {
  const router = useRouter();

  React.useEffect(() => {
    const hash = window.location.hash.replace("#", "");
    const params = new URLSearchParams(hash);
    if (params.get("token")) {
      window.history.replaceState(null, "", window.location.pathname);
    }

    let redirectTo = "/";
    try {
      const saved = localStorage.getItem(LAST_ROUTE_STORAGE_KEY);
      if (
        saved &&
        saved !== "/login" &&
        saved !== "/register" &&
        saved !== "/sign-in" &&
        saved !== "/sign-up" &&
        saved !== "/auth/callback"
      ) {
        redirectTo = saved;
      }
    } catch {
      // ignore storage errors
    }

    router.replace(redirectTo);
  }, [router]);

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-4"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <Loader2 className="size-8 animate-spin text-primary" aria-hidden />
      <p className="text-sm text-muted-foreground">Completing sign-in…</p>
    </div>
  );
}
