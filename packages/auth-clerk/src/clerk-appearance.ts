/**
 * Barrel for Clerk `Appearance` helpers and per-app presets.
 *
 * Historical note: six near-identical `*-clerk-appearance.ts` files under each app
 * were consolidated into `createClerkAppearance` + `appearance/presets.ts` (PR #210, WS-12).
 */
export {
  createClerkAppearance,
  type CreateClerkAppearanceOptions,
} from "./appearance/create-clerk-appearance";
export type { Appearance, ClerkAppearance } from "./appearance/types";
export {
  fileFreeAppearance,
  launchFreeAppearance,
  distillAppearance,
  studioAppearance,
  trinketsAppearance,
  axiomfolioAppearance,
} from "./appearance/presets";
