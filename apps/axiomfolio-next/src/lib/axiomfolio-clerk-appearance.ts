import { dark } from "@clerk/themes";

/**
 * AxiomFolio-branded Clerk appearance. Color tokens come from
 * `src/app/axiomfolio.css` (`.dark` + `@theme`); primary is gold-tinted,
 * surfaces follow `--background` / `--card` / `--border` oklch values.
 * Typed compatibly with Clerk's `Appearance` (via `as const` like Studio / LaunchFree).
 */
export const axiomfolioClerkAppearance = {
  baseTheme: dark,
  variables: {
    colorPrimary: "var(--primary)",
    colorBackground: "var(--background)",
    colorInputBackground: "var(--input)",
    colorInputText: "var(--foreground)",
    colorText: "var(--foreground)",
    colorTextSecondary: "var(--muted-foreground)",
    colorDanger: "var(--destructive)",
    borderRadius: "var(--radius-lg)",
    fontFamily: "var(--font-sans), ui-sans-serif, system-ui, sans-serif",
  },
  elements: {
    card:
      "border border-white/10 bg-card shadow-2xl shadow-black/35 backdrop-blur-sm",
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90",
    formFieldInput:
      "border-border/90 bg-background/40 transition focus:border-primary/50",
    socialButtonsBlockButton: "border-border/80 hover:bg-muted/50",
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
  },
} as const;
