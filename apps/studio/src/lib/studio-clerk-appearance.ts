import { dark } from "@clerk/themes";

/**
 * Studio-branded Clerk appearance. Uses `data-theme="studio"` HSL tokens from
 * `packages/ui/src/themes.css` (imported via `globals.css`); keep in sync.
 */
export const studioClerkAppearance = {
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
    card: "border border-brand-primary/25 bg-brand-surface/60 shadow-2xl shadow-black/30",
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90",
    formFieldInput:
      "border-brand-primary/35 bg-brand-surface/50 transition focus:border-brand-accent",
    socialButtonsBlockButton:
      "border-brand-primary/30 hover:bg-brand-primary/10 hover:border-brand-accent/35",
    footer: "hidden",
    footerAction: "hidden",
    footerActionText: "hidden",
    footerActionLink: "hidden",
    badge: "hidden",
    internal: "hidden",
    headerTitle: "text-zinc-100",
    headerSubtitle: "text-zinc-400",
    formFieldLabel: "text-zinc-200",
    identityPreview: "bg-brand-primary/10 border-brand-primary/30",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-brand-accent/35",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/45",
  },
} as const;
