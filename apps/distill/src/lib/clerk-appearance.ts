import { dark } from "@clerk/themes";

/**
 * Distill-branded Clerk appearance: locked palette teal #0F766E + burnt orange
 * #C2410C accents on a dark base.
 */
export const distillClerkAppearance = {
  baseTheme: dark,
  variables: {
    colorPrimary: "#0F766E",
    colorBackground: "hsl(222 47% 11%)",
    colorInputBackground: "hsl(216 34% 16%)",
    colorInputText: "hsl(210 40% 98%)",
    colorText: "hsl(210 40% 98%)",
    colorTextSecondary: "hsl(215 16% 57%)",
    colorDanger: "hsl(0 63% 31%)",
    borderRadius: "0.5rem",
    fontFamily: "var(--font-inter), ui-sans-serif, system-ui, sans-serif",
  },
  elements: {
    card: "border border-brand-primary/40 bg-brand-surface/80 shadow-2xl shadow-black/30",
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm !bg-brand-primary hover:!brightness-110 active:!opacity-90 border-none",
    formFieldInput:
      "border-brand-primary/50 bg-brand-surface/60 transition focus:border-brand-primary",
    socialButtonsBlockButton:
      "border-brand-primary/50 hover:bg-brand-primary/10 hover:border-brand-accent/40",
    footer: "hidden",
    footerAction: "hidden",
    footerActionText: "hidden",
    footerActionLink: "hidden",
    badge: "hidden",
    internal: "hidden",
    headerTitle: "text-slate-100",
    headerSubtitle: "text-slate-400",
    formFieldLabel: "text-slate-200",
    identityPreview: "bg-brand-primary/15 border-brand-primary/40",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-brand-primary/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-primary/50",
  },
} as const;
