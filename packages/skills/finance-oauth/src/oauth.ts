import { createHash, randomBytes } from "node:crypto";

const BASE64URL_PATTERN = /^[A-Za-z0-9_-]+$/;

function stripBase64Padding(s: string): string {
  return s.replace(/=+$/, "");
}

/**
 * RFC 7636: produce a high-entropy code verifier (43–128 chars, base64url).
 */
export function generateCodeVerifier(length?: number): string {
  const n = length ?? 64;
  if (n < 43 || n > 128) {
    throw new RangeError(
      `PKCE code verifier length must be between 43 and 128 inclusive, got ${n}`,
    );
  }
  const buf = randomBytes(96);
  const encoded = stripBase64Padding(buf.toString("base64url"));
  if (encoded.length < n) {
    throw new Error("Internal error: insufficient entropy for code verifier");
  }
  const verifier = encoded.slice(0, n);
  if (!BASE64URL_PATTERN.test(verifier)) {
    throw new Error("Generated code verifier failed base64url validation");
  }
  return verifier;
}

/**
 * RFC 7636: S256 code challenge (SHA-256 of verifier, base64url).
 */
export async function generateCodeChallenge(
  verifier: string,
): Promise<string> {
  const hash = createHash("sha256").update(verifier).digest();
  return stripBase64Padding(Buffer.from(hash).toString("base64url"));
}

/**
 * Merge OAuth authorization query params into an authorize URL.
 */
export function buildPkceUrl(
  authUrl: string,
  params: Record<string, string>,
): string {
  const url = new URL(authUrl);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  return url.toString();
}
