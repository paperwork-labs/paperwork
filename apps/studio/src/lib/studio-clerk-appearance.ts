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
    card: "border border-zinc-800/80 bg-zinc-900/50 shadow-2xl shadow-black/30",
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90",
    formFieldInput:
      "border-zinc-700/90 bg-zinc-950/40 transition focus:border-zinc-500",
    socialButtonsBlockButton: "border-zinc-700/80 hover:bg-zinc-800/60",
    footer: "text-zinc-500",
    headerTitle: "text-zinc-100",
    headerSubtitle: "text-zinc-400",
    formFieldLabel: "text-zinc-200",
    identityPreview: "bg-zinc-800/50 border-zinc-700/60",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-zinc-800/50 focus:ring-2 focus:ring-zinc-500/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-zinc-700/80",
  },
} as const;
