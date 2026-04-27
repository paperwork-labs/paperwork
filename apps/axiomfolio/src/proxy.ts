import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import type { NextFetchEvent, NextRequest } from "next/server";

// Track E feature flag — gate the Next.js shell behind an env-var so we
// can ship the scaffold today and flip routes on one-by-one without
// disturbing the production Vite app.
//
// When NEXT_PUBLIC_AXIOMFOLIO_NEXT_ENABLED is unset or "false", any
// request to a route listed in MATCHED_ROUTES is redirected to the Vite
// origin defined by NEXT_PUBLIC_AXIOMFOLIO_VITE_ORIGIN.
//
// Next 16 uses `proxy.ts` (not `middleware.ts`). Clerk is composed here
// so only one network boundary file exists (see Next.js "middleware-to-proxy").

const MATCHED_ROUTES = new Set(["/system-status", "/portfolio", "/scanner"]);

/**
 * AxiomFolio (Next.js) — foundation Clerk + legacy `qm_token` auth.
 * `RequireAuthClient` remains the client gate. No server-side `auth().protect()`.
 */
const isClerkPublicRoute = createRouteMatcher([
  "/",
  "/auth/callback",
  "/login",
  "/register",
  "/auth/forgot-password(.*)",
  "/auth/reset-password(.*)",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/pricing",
  "/api/health",
  "/api/health/(.*)",
]);

const clerk = clerkMiddleware((_, request) => {
  if (isClerkPublicRoute(request)) {
    return;
  }
  // Non-blocking: all other routes pass through; legacy auth unchanged.
});

function isEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_AXIOMFOLIO_NEXT_ENABLED;
  return raw === "true" || raw === "1";
}

function viteOrigin(): string | null {
  return process.env.NEXT_PUBLIC_AXIOMFOLIO_VITE_ORIGIN ?? null;
}

function axiomViteShellGate(req: NextRequest): NextResponse | null {
  const { pathname } = req.nextUrl;
  const gated = [...MATCHED_ROUTES].some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
  if (!gated) return null;
  if (isEnabled()) return null;
  const origin = viteOrigin();
  if (!origin) {
    return new NextResponse(
      "AxiomFolio Next.js shell is disabled. Set NEXT_PUBLIC_AXIOMFOLIO_NEXT_ENABLED=true to use this route, " +
        "or NEXT_PUBLIC_AXIOMFOLIO_VITE_ORIGIN to redirect to the Vite deployment.",
      { status: 503 },
    );
  }
  const url = new URL(pathname, origin);
  url.search = req.nextUrl.search;
  return NextResponse.redirect(url, 307);
}

export function proxy(req: NextRequest, event: NextFetchEvent) {
  const vite = axiomViteShellGate(req);
  if (vite) {
    return vite;
  }
  return clerk(req, event);
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
