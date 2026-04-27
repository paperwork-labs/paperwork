import { dark } from "@clerk/themes";

/**
 * Trinkets-branded Clerk appearance: locked indigo primary (#6366F1) + sky cyan
 * (#38BDF8) accents. Background/text bridge to `data-theme="trinkets"` in
 * `packages/ui` via HSL custom properties; primary stays indigo (not theme amber).
 */
export const trinketsClerkAppearance = {
  baseTheme: dark,
  variables: {
    colorPrimary: "#6366F1",
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
    card:
      "border border-brand-primary/25 bg-brand-surface/85 shadow-2xl shadow-black/35",
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90",
    formFieldInput:
      "border-brand-primary/35 bg-brand-surface/70 transition focus:border-brand-accent/80 focus:ring-brand-accent/20",
    socialButtonsBlockButton:
      "border-brand-primary/40 hover:bg-brand-primary/10 hover:border-brand-accent/35",
    footer: "hidden",
    footerAction: "hidden",
    footerActionText: "hidden",
    footerActionLink: "hidden",
    badge: "hidden",
    internal: "hidden",
    headerTitle: "text-stone-100",
    headerSubtitle: "text-stone-400",
    formFieldLabel: "text-stone-200",
    identityPreview: "bg-brand-primary/12 border-brand-primary/35",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-brand-accent/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/45",
  },
} as const;
