import { SignInShell, type SignInShellProps } from "./sign-in-shell";

/**
 * Sign-up variant of `<SignInShell>` — same wordmark + attribution + explainer
 * pattern, but the default verb becomes `Create your ${appName} account`.
 *
 * `isPrimaryHost` (accounts.paperworklabs.com) keeps the "Paperwork ID"
 * headline regardless of which shell is used.
 */
export type SignUpShellProps = Omit<SignInShellProps, "signInVerb"> & {
  /**
   * Override the default sign-up verb. Defaults to
   * `Create your ${appName} account`.
   */
  signUpVerb?: string;
};

export function SignUpShell({
  signUpVerb,
  appName,
  ...rest
}: SignUpShellProps) {
  return (
    <SignInShell
      {...rest}
      appName={appName}
      signInVerb={signUpVerb ?? `Create your ${appName} account`}
    />
  );
}
