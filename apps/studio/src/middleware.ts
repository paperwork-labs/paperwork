import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Studio auth: Clerk SSO + Basic Auth (escape hatch) on admin surfaces.
 *
 * Precedence (per request, for `/admin` and `/api/admin` in production only):
 * 1) Public and self-authenticated routes: no Studio gate (Clerk may still run for session state).
 * 2) `auth().userId` (Clerk session) → allow.
 * 3) Valid Basic Auth against ADMIN_EMAILS + ADMIN_ACCESS_PASSWORD → allow.
 * 4) Otherwise: browser navigations → redirect to sign-in; `/api/*` → 401 + WWW-Authenticate.
 *    If CLERK_DOMAIN_DEGRADED=1: skip sign-in redirect; return 401 + Basic challenge only (emergency Basic-only access).
 *
 * Development: same public rules; `/admin` + `/api/admin` stay ungated (preserves pre-Clerk local DX).
 * Secrets API routes use `secrets-auth.ts` only — we do not apply this Basic/Clerk wall there.
 */
function parseBasicAuth(authHeader: string | null): { username: string; password: string } | null {
  if (!authHeader || !authHeader.startsWith("Basic ")) {
    return null;
  }

  try {
    const decoded = atob(authHeader.slice(6));
    const separator = decoded.indexOf(":");
    if (separator < 0) return null;
    return {
      username: decoded.slice(0, separator),
      password: decoded.slice(separator + 1),
    };
  } catch {
    return null;
  }
}

function basicAuthAllows(request: NextRequest): boolean {
  const allowedEmailsRaw = process.env.ADMIN_EMAILS || "";
  const requiredPassword = process.env.ADMIN_ACCESS_PASSWORD || "";

  const allowedEmails = new Set(
    allowedEmailsRaw
      .split(",")
      .map((email) => email.trim().toLowerCase())
      .filter(Boolean),
  );

  if (allowedEmails.size === 0 || !requiredPassword) {
    return false;
  }

  const auth = parseBasicAuth(request.headers.get("authorization"));
  if (!auth) return false;

  const email = auth.username.trim().toLowerCase();
  return allowedEmails.has(email) && auth.password === requiredPassword;
}

function basicAuthUnauthorized() {
  return new NextResponse("Unauthorized", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Paperwork Labs Admin"' },
  });
}

const isPublicRoute = createRouteMatcher([
  "/",
  "/docs(.*)",
  "/login(.*)",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/health",
  "/api/health/(.*)",
]);

const isSecretsApi = createRouteMatcher(["/api/secrets(.*)"]);

const isStudioGated = createRouteMatcher(["/admin(.*)", "/api/admin(.*)"]);

export default clerkMiddleware(async (auth, request) => {
  if (isPublicRoute(request) || isSecretsApi(request)) {
    return;
  }

  if (isStudioGated(request) && process.env.NODE_ENV === "development") {
    return;
  }

  if (isStudioGated(request) && process.env.NODE_ENV === "production") {
    const { userId, redirectToSignIn } = await auth();

    if (userId) {
      return;
    }

    if (basicAuthAllows(request)) {
      return;
    }

    // Set CLERK_DOMAIN_DEGRADED=1 on Vercel when Clerk's Account Portal custom domain DNS is broken / not yet configured. Falls back to Basic Auth only.
    if (process.env.CLERK_DOMAIN_DEGRADED === "1") {
      return basicAuthUnauthorized();
    }

    if (request.nextUrl.pathname.startsWith("/api/")) {
      return basicAuthUnauthorized();
    }

    return redirectToSignIn({ returnBackUrl: request.url });
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
