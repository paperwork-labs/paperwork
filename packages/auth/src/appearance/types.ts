/**
 * Local shim for Clerk's `Appearance` shape. We don't import from `@clerk/types`
 * because that package isn't directly exposed in @clerk/nextjs v7's dep tree
 * (the public type alias is `any` inside `@clerk/shared/types`). Defining the
 * shape we actually use here keeps the package buildable without forcing a
 * peer-dep on a private @clerk/types resolution.
 *
 * If Clerk ever ships a stable public type, switch this re-export to the
 * upstream alias and delete this file.
 */
export interface ClerkAppearance {
  baseTheme?: unknown;
  variables?: Record<string, string | undefined>;
  elements?: Record<string, string>;
  layout?: Record<string, unknown>;
}

export type Appearance = ClerkAppearance;
