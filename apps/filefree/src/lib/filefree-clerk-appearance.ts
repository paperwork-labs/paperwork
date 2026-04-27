import { dark } from "@clerk/themes";

/**
 * FileFree-branded Clerk appearance. HSL tokens resolve from
 * `[data-theme="filefree"]` in `packages/ui/src/themes.css` (via `globals.css`).
 */
export const fileFreeClerkAppearance = {
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
    card: "border border-brand-primary/35 bg-brand-surface/40 shadow-2xl shadow-black/30",
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90",
    formFieldInput:
      "border-brand-primary/45 bg-brand-surface/50 transition focus:border-brand-accent/80",
    socialButtonsBlockButton:
      "border-brand-primary/50 hover:bg-brand-primary/10",
    footer: "hidden",
    footerAction: "hidden",
    footerActionText: "hidden",
    footerActionLink: "hidden",
    badge: "hidden",
    internal: "hidden",
    headerTitle: "text-foreground",
    headerSubtitle: "text-muted-foreground",
    formFieldLabel: "text-foreground/90",
    identityPreview: "bg-brand-primary/15 border-brand-primary/45",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-brand-accent/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/50",
  },
} as const;
