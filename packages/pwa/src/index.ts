// Track M.7 — public surface for @paperwork-labs/pwa.
//
// Consumers should prefer the subpath exports for smaller bundles
// (e.g. import { isStandalone } from "@paperwork-labs/pwa/display-mode"),
// but this barrel is here for convenience.

export { getDisplayMode, isStandalone, isIos } from "./displayMode";
export type { PwaDisplayMode } from "./displayMode";

export { usePWAInstallable } from "./usePWAInstallable";
export type {
  UsePWAInstallableOptions,
  UsePWAInstallableResult,
} from "./usePWAInstallable";

export { InstallPrompt, default as DefaultInstallPrompt } from "./InstallPrompt";
export type { InstallPromptProps } from "./InstallPrompt";

export { buildManifest } from "./manifest";
export type {
  BuildManifestInput,
  ManifestIcon,
  WebAppManifest,
} from "./manifest";
