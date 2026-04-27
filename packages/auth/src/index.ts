export { useIdleTimeout } from "./hooks/use-idle-timeout";
export { useClerkUser } from "./hooks/use-clerk-user";
export { useAdmin, type UseAdminResult } from "./hooks/use-admin";

export { SessionTimeoutDialog } from "./components/session-timeout-dialog";
export { SignInShell, type SignInShellProps } from "./components/sign-in-shell";
export { SignUpShell, type SignUpShellProps } from "./components/sign-up-shell";
export { RequireAuth, type RequireAuthProps } from "./components/require-auth";
export { RequireAdmin, type RequireAdminProps } from "./components/require-admin";

export {
  PAPERWORK_PRODUCTS,
  getSiblingProducts,
  formatSiblingExplainer,
  type PaperworkProduct,
} from "./products";

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

export {
  verifyClerkJwt,
  extractClerkToken,
  type VerifyClerkJwtOptions,
  type ClerkJwtPayload,
} from "./server/verify-clerk-jwt";
