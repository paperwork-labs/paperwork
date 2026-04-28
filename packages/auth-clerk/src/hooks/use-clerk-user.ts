"use client";

/**
 * Re-export of Clerk's `useUser` hook so app code can depend on
 * `@paperwork-labs/auth-clerk/hooks/use-clerk-user` instead of pinning to
 * `@clerk/nextjs` directly. When we ever swap providers or shim during tests
 * this is the seam we'll override.
 */
export { useUser as useClerkUser } from "@clerk/nextjs";
