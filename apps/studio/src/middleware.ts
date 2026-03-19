import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

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

function unauthorizedResponse() {
  return new NextResponse("Unauthorized", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Paperwork Labs Admin"' },
  });
}

export function middleware(request: NextRequest) {
  const allowedEmailsRaw = process.env.ADMIN_EMAILS || "";
  const requiredPassword = process.env.ADMIN_ACCESS_PASSWORD || "";

  const allowedEmails = new Set(
    allowedEmailsRaw
      .split(",")
      .map((email) => email.trim().toLowerCase())
      .filter(Boolean),
  );

  // Fail closed when guard configuration is missing.
  if (allowedEmails.size === 0 || !requiredPassword) {
    return new NextResponse("Admin access is not configured.", { status: 503 });
  }

  const auth = parseBasicAuth(request.headers.get("authorization"));
  if (!auth) return unauthorizedResponse();

  const email = auth.username.trim().toLowerCase();
  const password = auth.password;

  if (!allowedEmails.has(email) || password !== requiredPassword) {
    return unauthorizedResponse();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*"],
  // Note: /api/secrets/* routes handle their own auth via secrets-auth.ts
  // (supports both Basic Auth and Bearer token for machine access)
};
