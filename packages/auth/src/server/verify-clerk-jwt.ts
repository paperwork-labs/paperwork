import { createRemoteJWKSet, jwtVerify } from "jose";
import type { JWTPayload, JWTVerifyOptions } from "jose";

/**
 * Verifies a Clerk-issued JWT against the issuer's JWKS. Suitable for Node
 * API routes (`/app/api/*`) and edge handlers that don't already use Clerk's
 * server SDK.
 *
 * The Clerk hub issues tokens whose `iss` claim is the Frontend API URL
 * (e.g. `https://clerk.example.com` or `https://clerk.<frontend-api>`). The
 * JWKS lives at `<issuer>/.well-known/jwks.json`.
 *
 * @example minimal usage:
 *   const payload = await verifyClerkJwt(req.headers.get("authorization")?.slice(7) ?? "", {
 *     issuer: process.env.CLERK_JWT_ISSUER!,
 *   });
 *
 * @example with custom audience:
 *   const payload = await verifyClerkJwt(token, {
 *     issuer,
 *     audience: "https://api.filefree.ai",
 *   });
 *
 * @throws `Error` if the token is malformed, expired, or fails signature
 *         verification. Callers should treat any thrown error as a 401.
 */
export interface VerifyClerkJwtOptions extends Omit<JWTVerifyOptions, "issuer"> {
  /**
   * Clerk Frontend API URL (no trailing slash). Required.
   * Example: `"https://clerk.filefree.ai"`.
   */
  issuer: string;
  /**
   * Override the JWKS URL. Defaults to `${issuer}/.well-known/jwks.json`.
   */
  jwksUrl?: string;
}

export interface ClerkJwtPayload extends JWTPayload {
  /** Clerk user id (`user_*`). */
  sub?: string;
  /** Clerk session id (`sess_*`). */
  sid?: string;
  /** Clerk org id (`org_*`), if present. */
  org_id?: string;
  /** Clerk org role (e.g. `"admin"`, `"basic_member"`), if present. */
  org_role?: string;
  /** Custom claims set by Clerk JWT templates. */
  [claim: string]: unknown;
}

const jwksCache = new Map<string, ReturnType<typeof createRemoteJWKSet>>();

function getJwks(jwksUrl: string) {
  let jwks = jwksCache.get(jwksUrl);
  if (!jwks) {
    jwks = createRemoteJWKSet(new URL(jwksUrl), {
      cooldownDuration: 30_000,
      cacheMaxAge: 10 * 60_000,
    });
    jwksCache.set(jwksUrl, jwks);
  }
  return jwks;
}

/**
 * Verify a Clerk JWT and return the decoded payload. Throws on any failure.
 */
export async function verifyClerkJwt(
  token: string,
  options: VerifyClerkJwtOptions,
): Promise<ClerkJwtPayload> {
  if (!token || typeof token !== "string") {
    throw new Error("verifyClerkJwt: token is empty");
  }

  const issuer = options.issuer.replace(/\/+$/, "");
  const jwksUrl = options.jwksUrl ?? `${issuer}/.well-known/jwks.json`;
  const jwks = getJwks(jwksUrl);

  const { jwksUrl: _ignored, ...verifyOptions } = options;

  const { payload } = await jwtVerify(token, jwks, {
    ...verifyOptions,
    issuer,
  });

  return payload as ClerkJwtPayload;
}

/**
 * Extracts a bearer token from an `Authorization` header value (or the raw
 * cookie value Clerk sets at `__session`). Returns `null` when neither is
 * present.
 */
export function extractClerkToken(input: {
  authorization?: string | null;
  sessionCookie?: string | null;
}): string | null {
  const auth = input.authorization?.trim();
  if (auth && auth.toLowerCase().startsWith("bearer ")) {
    const token = auth.slice(7).trim();
    if (token) return token;
  }
  const cookie = input.sessionCookie?.trim();
  if (cookie) return cookie;
  return null;
}
