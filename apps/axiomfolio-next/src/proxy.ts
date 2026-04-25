import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Track E feature flag — gate the Next.js shell behind an env-var so we
// can ship the scaffold today and flip routes on one-by-one without
// disturbing the production Vite app.
//
// When NEXT_PUBLIC_AXIOMFOLIO_NEXT_ENABLED is unset or "false", any
// request to a route listed in MATCHED_ROUTES is redirected to the Vite
// origin defined by NEXT_PUBLIC_AXIOMFOLIO_VITE_ORIGIN.
//
// Next 16 renamed `middleware.ts` → `proxy.ts`. The function is still
// called `middleware` by the runtime; the filename is what changed.

const MATCHED_ROUTES = new Set(["/system-status", "/portfolio", "/scanner"]);

function isEnabled(): boolean {
  const raw = process.env.NEXT_PUBLIC_AXIOMFOLIO_NEXT_ENABLED;
  return raw === "true" || raw === "1";
}

function viteOrigin(): string | null {
  return process.env.NEXT_PUBLIC_AXIOMFOLIO_VITE_ORIGIN ?? null;
}

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const gated = [...MATCHED_ROUTES].some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
  if (!gated) return NextResponse.next();
  if (isEnabled()) return NextResponse.next();
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

export const config = {
  matcher: ["/system-status/:path*", "/portfolio/:path*", "/scanner/:path*"],
};
