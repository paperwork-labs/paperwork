/**
 * Bridges Clerk session tokens into non-React modules (axios, etc.).
 * `ClerkTokenBridge` in providers registers `getToken` from `@clerk/nextjs`.
 */

type ClerkGetToken = (options?: { template?: string }) => Promise<string | null>;

let getTokenImpl: ClerkGetToken | null = null;

export function setClerkApiTokenGetter(fn: ClerkGetToken | null): void {
  getTokenImpl = fn;
}

export async function getClerkSessionTokenForApi(): Promise<string | null> {
  if (!getTokenImpl) return null;
  try {
    return await getTokenImpl();
  } catch {
    return null;
  }
}
