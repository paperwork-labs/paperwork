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
      "border border-indigo-500/20 bg-stone-950/70 shadow-2xl shadow-indigo-950/40",
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90",
    formFieldInput:
      "border-stone-700/90 bg-stone-950/50 transition focus:border-sky-400/80 focus:ring-sky-400/20",
    socialButtonsBlockButton:
      "border-indigo-500/40 hover:bg-indigo-950/50 hover:border-sky-400/30",
    footer: "hidden",
    footerAction: "hidden",
    footerActionText: "hidden",
    footerActionLink: "hidden",
    badge: "hidden",
    internal: "hidden",
    headerTitle: "text-stone-100",
    headerSubtitle: "text-stone-400",
    formFieldLabel: "text-stone-200",
    identityPreview: "bg-stone-900/50 border-indigo-500/30",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-indigo-950/40 focus:ring-2 focus:ring-sky-400/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-sky-400/40",
  },
} as const;
