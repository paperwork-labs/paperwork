export { useIdleTimeout } from "./hooks/use-idle-timeout";
export { useClerkUser } from "./hooks/use-clerk-user";
export { useAdmin, type UseAdminResult } from "./hooks/use-admin";

export { SessionTimeoutDialog } from "./components/session-timeout-dialog";
export { SignInShell, type SignInShellProps } from "./SignInShell";
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
  fileFreeAppearance,
  launchFreeAppearance,
  distillAppearance,
  studioAppearance,
  trinketsAppearance,
  axiomfolioAppearance,
  type CreateClerkAppearanceOptions,
  type Appearance,
  type ClerkAppearance,
} from "./clerk-appearance";

export {
  verifyClerkJwt,
  extractClerkToken,
  type VerifyClerkJwtOptions,
  type ClerkJwtPayload,
} from "./server/verify-clerk-jwt";
