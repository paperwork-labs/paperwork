import { dark } from "@clerk/themes";

/**
 * LaunchFree-branded Clerk appearance. HSL tokens come from
 * `packages/ui/src/themes.css` under `[data-theme="launchfree"]` (imported via
 * `globals.css`); `elements` use a slate-950/800 card treatment.
 */
export const launchFreeClerkAppearance = {
  baseTheme: dark,
  variables: {
    colorPrimary: "hsl(var(--primary))",
    colorBackground: "hsl(var(--background))",
    colorInputBackground: "hsl(var(--input))",
    colorInputText: "hsl(var(--foreground))",
    colorText: "hsl(var(--foreground))",
    colorTextSecondary: "hsl(var(--muted-foreground))",
    colorDanger: "hsl(var(--destructive))",
    borderRadius: "0.5rem",
    fontFamily: "var(--font-inter), ui-sans-serif, system-ui, sans-serif",
  },
  elements: {
    card: "border border-brand-primary/30 bg-brand-surface/90 shadow-2xl shadow-black/30",
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90",
    formFieldInput:
      "border-brand-primary/40 bg-brand-surface/70 transition focus:border-brand-accent",
    socialButtonsBlockButton:
      "border-brand-primary/35 hover:bg-brand-primary/10 hover:border-brand-accent/40",
    footer: "hidden",
    footerAction: "hidden",
    footerActionText: "hidden",
    footerActionLink: "hidden",
    badge: "hidden",
    internal: "hidden",
    headerTitle: "text-slate-100",
    headerSubtitle: "text-slate-400",
    formFieldLabel: "text-slate-200",
    identityPreview: "bg-brand-primary/10 border-brand-primary/35",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-brand-accent/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/45",
  },
} as const;
