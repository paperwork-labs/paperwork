/**
 * Clerk Next.js server helpers — single import path next to SignInShell / appearance.
 * Re-exports stay thin so @clerk version bumps resolve in one workspace package.
 */
export { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
