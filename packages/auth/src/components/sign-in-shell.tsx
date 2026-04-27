import { Children, cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";

import { formatSiblingExplainer } from "../products";
import type { Appearance } from "../appearance/types";

/**
 * Wordmark-driven shell for per-app sign-in / sign-up surfaces.
 *
 * Locked decision (Q2 2026): the brand wordmark on every per-app sign-in card
 * is APP-NAME-PRIMARY ("FileFree"), with "by Paperwork Labs" attribution and
 * the cross-product explainer ("Your Paperwork ID also works on …"). The flat
 * "Paperwork ID" headline is reserved exclusively for `accounts.paperworklabs.com`,
 * which is enabled via `isPrimaryHost`.
 *
 * `<SignUpShell>` is a thin wrapper around this component that swaps the
 * default verb to "Create your {App} account".
 *
 * @example FileFree sign-in:
 *   <SignInShell
 *     appName="FileFree"
 *     appWordmark={<FileFreeWordmark />}
 *     appTagline="Free tax filing"
 *     appearance={createClerkAppearance({ primary: "var(--brand-primary)" })}
 *   >
 *     <SignIn />
 *   </SignInShell>
 *
 * @example accounts.paperworklabs.com (the only place "Paperwork ID" is the headline):
 *   <SignInShell
 *     appName="Paperwork Labs"
 *     appWordmark={<PaperworkIdWordmark />}
 *     appTagline="One account, every tool"
 *     isPrimaryHost
 *   >
 *     <SignIn />
 *   </SignInShell>
 *
 * @example Studio (admin parent-brand surface):
 *   <SignInShell variant="admin" appName="Studio" appWordmark={<StudioMark />} appTagline="Paperwork Labs admin tools">
 *     <SignIn />
 *   </SignInShell>
 */
export interface SignInShellProps {
  /** Display name used in the default headline ("Sign in to {appName}"). */
  appName: string;
  /** Brand wordmark element rendered above the headline (Logo + name + tagline). */
  appWordmark: ReactNode;
  /** Short tagline used in the attribution line ("{tagline}, by Paperwork Labs"). */
  appTagline: string;
  /**
   * Override the default verb. Defaults to:
   *   - `Sign in to ${appName}` for `<SignInShell>` (non-primary host)
   *   - `Paperwork ID`            for `<SignInShell isPrimaryHost>`
   *
   * `<SignUpShell>` defaults this to `Create your ${appName} account`.
   */
  signInVerb?: string;
  /**
   * Slug for the current product (e.g. `"filefree"`). Used to filter the
   * sibling-product list in the explainer. If omitted, falls back to a
   * lowercased `appName`.
   */
  appSlug?: string;
  /**
   * Set to `true` only on `accounts.paperworklabs.com` (Track H4). Flips the
   * headline to "Paperwork ID" and the explainer to the unified-account copy.
   */
  isPrimaryHost?: boolean;
  /**
   * Visual variant. Defaults to `"customer"` (full attribution + explainer).
   * `"admin"` (Studio) drops the explainer because Studio is internal.
   */
  variant?: "customer" | "admin";
  /** Clerk Appearance object — usually built with `createClerkAppearance(...)`. */
  appearance?: Appearance;
  /** The actual `<SignIn />` or `<SignUp />` element. */
  children: ReactNode;
}

export function SignInShell({
  appName,
  appWordmark,
  appTagline,
  signInVerb,
  appSlug,
  isPrimaryHost = false,
  variant = "customer",
  appearance,
  children,
}: SignInShellProps) {
  const headline = isPrimaryHost
    ? "Paperwork ID"
    : signInVerb ?? `Sign in to ${appName}`;

  const slug = (appSlug ?? appName).toLowerCase();
  const explainer = isPrimaryHost
    ? "One account for FileFree, LaunchFree, Distill, AxiomFolio, Trinkets, and everything Paperwork Labs."
    : formatSiblingExplainer(slug);

  const showExplainer = variant !== "admin";
  const attribution = isPrimaryHost
    ? appTagline
    : `${appTagline}, by Paperwork Labs`;

  const decoratedChildren = appearance
    ? Children.map(children, (child) => {
        if (!isValidElement(child)) return child;
        const element = child as ReactElement<{ appearance?: Appearance }>;
        if (element.props.appearance) return element;
        return cloneElement(element, { appearance });
      })
    : children;

  return (
    <div className="w-full max-w-md" data-testid="sign-in-shell">
      <header className="mb-6 flex flex-col items-center gap-3 text-center">
        <div className="flex items-center justify-center" data-testid="sign-in-shell-wordmark">
          {appWordmark}
        </div>
        <h1
          className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl"
          data-testid="sign-in-shell-headline"
        >
          {headline}
        </h1>
      </header>

      <div data-testid="sign-in-shell-clerk">{decoratedChildren}</div>

      <footer className="mt-6 space-y-3 text-center" data-testid="sign-in-shell-footer">
        <div
          className="mx-auto h-px w-16 bg-border/60"
          aria-hidden
        />
        <p
          className="text-sm text-muted-foreground"
          data-testid="sign-in-shell-attribution"
        >
          {attribution}
        </p>
        {showExplainer && (
          <p
            className="text-xs text-muted-foreground/80"
            data-testid="sign-in-shell-explainer"
          >
            {explainer}
          </p>
        )}
      </footer>
    </div>
  );
}
