import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

function safeEqual(a: string, b: string): boolean {
  const bufA = Buffer.from(a, "utf8");
  const bufB = Buffer.from(b, "utf8");
  if (bufA.length !== bufB.length) return false;
  try {
    return timingSafeEqual(bufA, bufB);
  } catch {
    return false;
  }
}

type AuthResult =
  | { ok: true }
  | { ok: false; response: NextResponse };

/**
 * Authenticates API requests using either:
 * 1. Bearer token (SECRETS_API_KEY) for machine-to-machine access (n8n, scripts)
 * 2. Basic Auth (ADMIN_EMAILS + ADMIN_ACCESS_PASSWORD) for admin browser sessions
 */
export function authenticateSecretsRequest(request: NextRequest): AuthResult {
  const authHeader = request.headers.get("authorization");
  if (!authHeader) {
    return {
      ok: false,
      response: NextResponse.json({ error: "Missing authorization header" }, { status: 401 }),
    };
  }

  if (authHeader.startsWith("Bearer ")) {
    return validateBearerToken(authHeader.slice(7));
  }

  if (authHeader.startsWith("Basic ")) {
    return validateBasicAuth(authHeader.slice(6));
  }

  return {
    ok: false,
    response: NextResponse.json({ error: "Invalid authorization scheme" }, { status: 401 }),
  };
}

function validateBearerToken(token: string): AuthResult {
  const expectedKey = process.env.SECRETS_API_KEY?.trim();
  if (!expectedKey) {
    return {
      ok: false,
      response: NextResponse.json({ error: "API key auth not configured" }, { status: 503 }),
    };
  }

  if (!safeEqual(token.trim(), expectedKey)) {
    return {
      ok: false,
      response: NextResponse.json({ error: "Invalid API key" }, { status: 403 }),
    };
  }

  return { ok: true };
}

function validateBasicAuth(encoded: string): AuthResult {
  const allowedEmailsRaw = process.env.ADMIN_EMAILS || "";
  const requiredPassword = process.env.ADMIN_ACCESS_PASSWORD || "";

  const allowedEmails = new Set(
    allowedEmailsRaw
      .split(",")
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean),
  );

  if (allowedEmails.size === 0 || !requiredPassword) {
    return {
      ok: false,
      response: NextResponse.json({ error: "Admin auth not configured" }, { status: 503 }),
    };
  }

  try {
    const decoded = atob(encoded);
    const sep = decoded.indexOf(":");
    if (sep < 0) {
      return { ok: false, response: NextResponse.json({ error: "Malformed credentials" }, { status: 401 }) };
    }

    const email = decoded.slice(0, sep).trim().toLowerCase();
    const password = decoded.slice(sep + 1);

    if (!allowedEmails.has(email) || !safeEqual(password, requiredPassword)) {
      return { ok: false, response: NextResponse.json({ error: "Invalid credentials" }, { status: 403 }) };
    }

    return { ok: true };
  } catch {
    return { ok: false, response: NextResponse.json({ error: "Malformed credentials" }, { status: 401 }) };
  }
}
