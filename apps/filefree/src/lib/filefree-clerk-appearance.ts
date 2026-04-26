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
    card: "border border-violet-950/80 bg-violet-950/35 shadow-2xl shadow-black/30",
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90",
    formFieldInput:
      "border-violet-900/70 bg-violet-950/40 transition focus:border-violet-500/80",
    socialButtonsBlockButton: "border-violet-900/60 hover:bg-violet-950/50",
    footer: "text-muted-foreground",
    headerTitle: "text-foreground",
    headerSubtitle: "text-muted-foreground",
    formFieldLabel: "text-foreground/90",
    identityPreview: "bg-violet-950/50 border-violet-900/60",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-violet-950/50 focus:ring-2 focus:ring-primary/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-violet-800/80",
  },
} as const;
