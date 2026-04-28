import { dark } from "@clerk/themes";

import type { Appearance } from "./types";

/**
 * Single-source factory for per-app Clerk `<SignIn />` / `<SignUp />` appearance.
 *
 * Replaces the six near-identical `*-clerk-appearance.ts` files that previously
 * lived under each app's `src/lib/`. The shared shape (variables block + the
 * "footer / footerAction / badge / internal: hidden" element overrides) is
 * captured here; per-app deltas come in via the `primary` / `accent` / `surface`
 * options. Apps that need extreme bespoke tweaks (e.g. AxiomFolio's
 * `bg-card backdrop-blur-sm` card) can pass a plain `elementOverrides` map that
 * gets shallow-merged on top.
 *
 * Why this factory exists:
 *   - Six copies of the same Appearance block drifted in three places (Distill
 *     hard-coded `#0F766E`, Trinkets hard-coded `#6366F1`, FileFree used HSL
 *     vars). Centralizing means one place to fix when Clerk renames a slot.
 *   - "Hide the footer" was the most-duplicated change in PR #210 — we now
 *     guarantee it is on by default.
 */
export interface CreateClerkAppearanceOptions {
  /**
   * Primary brand color (e.g. `"#0F766E"`, `"hsl(var(--primary))"`,
   * `"var(--primary)"`). Used for `colorPrimary` + the formButtonPrimary CTA.
   */
  primary: string;
  /**
   * Accent color used for focus rings + hover borders. Defaults to `primary`.
   */
  accent?: string;
  /**
   * Body / card background color used for `colorBackground`.
   * Defaults to `"hsl(var(--background))"`.
   */
  background?: string;
  /**
   * Input field background. Defaults to `"hsl(var(--input))"`.
   */
  inputBackground?: string;
  /**
   * Body text color. Defaults to `"hsl(var(--foreground))"`.
   */
  foreground?: string;
  /**
   * Muted / secondary text color. Defaults to `"hsl(var(--muted-foreground))"`.
   */
  mutedForeground?: string;
  /**
   * Destructive / danger color. Defaults to `"hsl(var(--destructive))"`.
   */
  destructive?: string;
  /**
   * Border radius for inputs + buttons. Defaults to `"0.5rem"`.
   */
  borderRadius?: string;
  /**
   * Font family. Defaults to the Inter stack used across the monorepo.
   */
  fontFamily?: string;
  /**
   * If `true` (default), use Clerk's built-in `dark` base theme.
   */
  isDark?: boolean;
  /**
   * Tailwind classes appended to the Clerk `card` element (the modal/box that
   * wraps the form). Useful for app-specific borders / shadows / glass blur.
   */
  cardClassName?: string;
  /**
   * Tailwind classes for the `formFieldInput` slot.
   */
  inputClassName?: string;
  /**
   * Tailwind classes for the `socialButtonsBlockButton` slot (Google/Apple).
   */
  socialButtonClassName?: string;
  /**
   * Tailwind classes for the `formButtonPrimary` slot. Most callers should
   * leave this as the default since `colorPrimary` already drives the bg.
   */
  primaryButtonClassName?: string;
  /**
   * Optional shallow overrides merged on top of the computed `elements` map.
   */
  elementOverrides?: Record<string, string>;
}

const DEFAULT_FONT_FAMILY =
  "var(--font-inter), ui-sans-serif, system-ui, sans-serif";

const DEFAULT_PRIMARY_BUTTON_CLASS =
  "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90";

const DEFAULT_CARD_CLASS =
  "border border-border/60 bg-card shadow-2xl shadow-black/30";

const DEFAULT_INPUT_CLASS =
  "border-border/80 bg-background/40 transition focus:border-primary/60";

const DEFAULT_SOCIAL_BUTTON_CLASS =
  "border-border/70 hover:bg-muted/50";

/**
 * Build a Clerk `Appearance` object for a per-app `<SignIn />` / `<SignUp />`.
 *
 * @example
 *   <SignIn appearance={createClerkAppearance({ primary: "#0F766E" })} />
 *
 * @example dark mode by default + AxiomFolio surface:
 *   createClerkAppearance({
 *     primary: "var(--primary)",
 *     cardClassName: "border border-white/10 bg-card backdrop-blur-sm",
 *   })
 */
export function createClerkAppearance(
  options: CreateClerkAppearanceOptions,
): Appearance {
  const {
    primary,
    accent = primary,
    background = "hsl(var(--background))",
    inputBackground = "hsl(var(--input))",
    foreground = "hsl(var(--foreground))",
    mutedForeground = "hsl(var(--muted-foreground))",
    destructive = "hsl(var(--destructive))",
    borderRadius = "0.5rem",
    fontFamily = DEFAULT_FONT_FAMILY,
    isDark = true,
    cardClassName = DEFAULT_CARD_CLASS,
    inputClassName = DEFAULT_INPUT_CLASS,
    socialButtonClassName = DEFAULT_SOCIAL_BUTTON_CLASS,
    primaryButtonClassName = DEFAULT_PRIMARY_BUTTON_CLASS,
    elementOverrides,
  } = options;

  const baseElements: Record<string, string> = {
    card: cardClassName,
    rootBox: "w-full",
    formButtonPrimary: primaryButtonClassName,
    formFieldInput: inputClassName,
    socialButtonsBlockButton: socialButtonClassName,
    footer: "hidden",
    footerAction: "hidden",
    footerActionText: "hidden",
    footerActionLink: "hidden",
    badge: "hidden",
    internal: "hidden",
    headerTitle: "text-foreground",
    headerSubtitle: "text-muted-foreground",
    formFieldLabel: "text-foreground/90",
    identityPreview: "bg-muted/50 border-border/80",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-muted/50 focus:ring-2 focus:ring-primary/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-border/80",
  };

  const elements: Record<string, string> = elementOverrides
    ? { ...baseElements, ...elementOverrides }
    : baseElements;

  return {
    baseTheme: isDark ? dark : undefined,
    variables: {
      colorPrimary: primary,
      // `colorAccent` was added in @clerk/types v4; cast keeps us compatible
      // when callers' lockfiles haven't bumped yet.
      ...(accent !== primary ? ({ colorAccent: accent } as Record<string, string>) : {}),
      colorBackground: background,
      colorInputBackground: inputBackground,
      colorInputText: foreground,
      colorText: foreground,
      colorTextSecondary: mutedForeground,
      colorDanger: destructive,
      borderRadius,
      fontFamily,
    },
    elements,
  };
}
