import {
  clerkMiddleware,
  createRouteMatcher,
} from "@paperwork-labs/auth-clerk/server/clerk";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PREFIXES = ["/file", "/dashboard"];
const AUTH_PAGES = ["/auth/login", "/auth/register"];
const SESSION_COOKIE = "session";

/**
 * FileFree auth: legacy session cookies + Clerk SSO on admin surfaces (when added),
 * with Basic Auth as a documented operator escape hatch.
 *
 * Legacy session: `/file` and `/dashboard` require the session cookie; `/auth/*`
 * redirect to `/file` when already signed in. Unchanged.
 *
 * Admin (production only, `/admin` and `/api/admin`):
 * 1) `auth().userId` (Clerk) → allow
 * 2) Valid Basic Auth against ADMIN_EMAILS + ADMIN_ACCESS_PASSWORD → allow
 * 3) Otherwise: browser → redirect to sign-in; API → 401 + WWW-Authenticate
 *
 * Development: admin routes stay ungated (matches Studio local DX).
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
  "/api/health",
  "/api/health/(.*)",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/auth/login(.*)",
  "/auth/register(.*)",
  "/pricing(.*)",
  "/about(.*)",
  "/privacy(.*)",
  "/terms(.*)",
  "/design(.*)",
  "/advisory(.*)",
  "/demo(.*)",
  "/ops(.*)",
  "/guides(.*)",
  "/sitemap.xml",
  "/robots.txt",
]);

const isFileFreeGated = createRouteMatcher(["/admin(.*)", "/api/admin(.*)"]);

function legacySessionRedirect(request: NextRequest): NextResponse | null {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE);

  const isProtected = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
  if (isProtected && !hasSession) {
    const loginUrl = new URL("/auth/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const isAuthPage = AUTH_PAGES.some((page) => pathname.startsWith(page));
  if (isAuthPage && hasSession) {
    return NextResponse.redirect(new URL("/file", request.url));
  }

  return null;
}

export default clerkMiddleware(async (auth, request) => {
  const legacy = legacySessionRedirect(request);
  if (legacy) {
    return legacy;
  }

  if (isPublicRoute(request)) {
    return;
  }

  if (isFileFreeGated(request) && process.env.NODE_ENV === "development") {
    return;
  }

  if (isFileFreeGated(request) && process.env.NODE_ENV === "production") {
    const { userId, redirectToSignIn } = await auth();

    if (userId) {
      return;
    }

    if (basicAuthAllows(request)) {
      return;
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
