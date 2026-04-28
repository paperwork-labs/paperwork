import { createClerkAppearance } from "@paperwork-labs/auth-clerk/appearance";

/**
 * Neutral Clerk appearance for the primary auth host. `auth-clerk` has no
 * dedicated `paperworkLabsAppearance` preset yet; this uses slate/sky tokens
 * aligned with `globals.css` brand RGB variables.
 */
export const accountsAppearance = createClerkAppearance({
  primary: "#94a3b8",
  accent: "#38bdf8",
  background: "hsl(222 47% 11%)",
  inputBackground: "hsl(216 34% 16%)",
  foreground: "hsl(210 40% 98%)",
  mutedForeground: "hsl(215 16% 57%)",
  destructive: "hsl(0 63% 31%)",
  cardClassName:
    "border border-white/10 bg-brand-surface/80 shadow-2xl shadow-black/30",
  inputClassName:
    "border-white/15 bg-brand-surface/60 transition focus:border-brand-accent/70",
  socialButtonClassName:
    "border-white/20 hover:bg-white/5 hover:border-brand-accent/40",
  primaryButtonClassName:
    "font-medium shadow-sm !bg-brand-primary hover:!brightness-110 active:!opacity-90 border-none",
  elementOverrides: {
    headerTitle: "text-slate-100",
    headerSubtitle: "text-slate-400",
    formFieldLabel: "text-slate-200",
    identityPreview: "bg-white/10 border-white/20",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-white/10 focus:ring-2 focus:ring-brand-accent/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/45",
  },
});
