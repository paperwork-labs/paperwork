import {
  clerkMiddleware,
  createRouteMatcher,
} from "@paperwork-labs/auth-clerk/server/clerk";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * LaunchFree auth: Clerk SSO + session cookie (legacy) on `/dashboard`, plus
 * Clerk + Basic Auth on `/admin` and `/api/admin` in production (Studio parity).
 *
 * Precedence for `/admin` and `/api/admin` in production only:
 * 1) Public routes: no admin gate.
 * 2) Development: admin routes ungated (local DX).
 * 3) `auth().userId` (Clerk) → allow.
 * 4) Valid Basic Auth (`ADMIN_EMAILS` + `ADMIN_ACCESS_PASSWORD`) → allow.
 * 5) Otherwise: browser → redirect to sign-in; `/api/*` → 401 + WWW-Authenticate.
 *
 * `/dashboard`: requires Clerk session OR legacy `session` cookie (unchanged redirect target for missing auth).
 * `/auth/login`, `/auth/register`: redirect to `/dashboard` when already authenticated (cookie or Clerk).
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
  "/form(.*)",
  "/legal(.*)",
  "/auth(.*)",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/health",
  "/api/health/(.*)",
]);

const isLaunchFreeAdminGated = createRouteMatcher(["/admin(.*)", "/api/admin(.*)"]);

const SESSION_COOKIE = "session";

function isDashboardPath(pathname: string) {
  return pathname.startsWith("/dashboard");
}

function isAuthPagePath(pathname: string) {
  return ["/auth/login", "/auth/register"].some((page) => pathname.startsWith(page));
}

export default clerkMiddleware(async (auth, request) => {
  if (isPublicRoute(request)) {
    return;
  }

  if (isLaunchFreeAdminGated(request) && process.env.NODE_ENV === "development") {
    return;
  }

  if (isLaunchFreeAdminGated(request) && process.env.NODE_ENV === "production") {
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

  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE);

  if (isDashboardPath(pathname)) {
    const { userId } = await auth();
    if (userId || hasSession) {
      return;
    }
    return NextResponse.redirect(new URL("/", request.url));
  }

  if (isAuthPagePath(pathname)) {
    const { userId } = await auth();
    if (userId || hasSession) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
    return;
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
