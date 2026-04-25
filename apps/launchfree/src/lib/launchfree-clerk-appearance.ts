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
    card: "border border-slate-800/80 bg-slate-950/60 shadow-2xl shadow-black/30",
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90",
    formFieldInput:
      "border-slate-700/90 bg-slate-950/50 transition focus:border-slate-500",
    socialButtonsBlockButton: "border-slate-700/80 hover:bg-slate-800/60",
    footer: "text-slate-500",
    headerTitle: "text-slate-100",
    headerSubtitle: "text-slate-400",
    formFieldLabel: "text-slate-200",
    identityPreview: "bg-slate-800/50 border-slate-700/60",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-slate-800/50 focus:ring-2 focus:ring-slate-500/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-slate-700/80",
  },
} as const;
