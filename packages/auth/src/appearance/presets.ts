import { createClerkAppearance } from "./create-clerk-appearance";
import type { Appearance } from "./types";

/**
 * Thin per-app appearance presets — kept here only as a convenience for callers
 * that don't want to pass options inline. New apps should prefer calling
 * `createClerkAppearance({ primary, accent, … })` directly so the values
 * live next to the page that uses them.
 *
 * Each preset preserves the visual tokens that previously lived in the deleted
 * `apps/<slug>/src/lib/<slug>-clerk-appearance.ts` files (PR #210).
 */

export const fileFreeAppearance: Appearance = createClerkAppearance({
  primary: "hsl(var(--primary))",
  cardClassName:
    "border border-violet-950/80 bg-violet-950/35 shadow-2xl shadow-black/30",
  inputClassName:
    "border-violet-900/70 bg-violet-950/40 transition focus:border-violet-500/80",
  socialButtonClassName: "border-violet-900/60 hover:bg-violet-950/50",
  elementOverrides: {
    identityPreview: "bg-violet-950/50 border-violet-900/60",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-violet-950/50 focus:ring-2 focus:ring-primary/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-violet-800/80",
  },
});

export const launchFreeAppearance: Appearance = createClerkAppearance({
  primary: "hsl(var(--primary))",
  cardClassName:
    "border border-slate-800/80 bg-slate-950/60 shadow-2xl shadow-black/30",
  inputClassName:
    "border-slate-700/90 bg-slate-950/50 transition focus:border-slate-500",
  socialButtonClassName: "border-slate-700/80 hover:bg-slate-800/60",
  elementOverrides: {
    headerTitle: "text-slate-100",
    headerSubtitle: "text-slate-400",
    formFieldLabel: "text-slate-200",
    identityPreview: "bg-slate-800/50 border-slate-700/60",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-slate-800/50 focus:ring-2 focus:ring-slate-500/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-slate-700/80",
  },
});

export const distillAppearance: Appearance = createClerkAppearance({
  primary: "#0F766E",
  accent: "#C2410C",
  background: "hsl(222 47% 11%)",
  inputBackground: "hsl(216 34% 16%)",
  foreground: "hsl(210 40% 98%)",
  mutedForeground: "hsl(215 16% 57%)",
  destructive: "hsl(0 63% 31%)",
  cardClassName:
    "border border-teal-900/50 bg-slate-950/70 shadow-2xl shadow-black/30",
  inputClassName:
    "border-teal-800/80 bg-slate-950/50 transition focus:border-[#0F766E]",
  socialButtonClassName:
    "border-teal-800/60 hover:bg-teal-950/50 hover:border-[#C2410C]/40",
  primaryButtonClassName:
    "font-medium shadow-sm !bg-[#0F766E] hover:!bg-[#0D9488] active:!opacity-90 border-none",
  elementOverrides: {
    headerTitle: "text-slate-100",
    headerSubtitle: "text-slate-400",
    formFieldLabel: "text-slate-200",
    identityPreview: "bg-teal-950/40 border-teal-800/50",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-teal-950/50 focus:ring-2 focus:ring-[#0F766E]/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-teal-800/60",
  },
});

export const studioAppearance: Appearance = createClerkAppearance({
  primary: "hsl(var(--primary))",
  cardClassName:
    "border border-zinc-800/80 bg-zinc-900/50 shadow-2xl shadow-black/30",
  inputClassName:
    "border-zinc-700/90 bg-zinc-950/40 transition focus:border-zinc-500",
  socialButtonClassName: "border-zinc-700/80 hover:bg-zinc-800/60",
  elementOverrides: {
    headerTitle: "text-zinc-100",
    headerSubtitle: "text-zinc-400",
    formFieldLabel: "text-zinc-200",
    identityPreview: "bg-zinc-800/50 border-zinc-700/60",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-zinc-800/50 focus:ring-2 focus:ring-zinc-500/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-zinc-700/80",
  },
});

export const trinketsAppearance: Appearance = createClerkAppearance({
  primary: "#6366F1",
  accent: "#38BDF8",
  cardClassName:
    "border border-indigo-500/20 bg-stone-950/70 shadow-2xl shadow-indigo-950/40",
  inputClassName:
    "border-stone-700/90 bg-stone-950/50 transition focus:border-sky-400/80 focus:ring-sky-400/20",
  socialButtonClassName:
    "border-indigo-500/40 hover:bg-indigo-950/50 hover:border-sky-400/30",
  elementOverrides: {
    headerTitle: "text-stone-100",
    headerSubtitle: "text-stone-400",
    formFieldLabel: "text-stone-200",
    identityPreview: "bg-stone-900/50 border-indigo-500/30",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-indigo-950/40 focus:ring-2 focus:ring-sky-400/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-sky-400/40",
  },
});

export const axiomfolioAppearance: Appearance = createClerkAppearance({
  primary: "var(--primary)",
  background: "var(--background)",
  inputBackground: "var(--input)",
  foreground: "var(--foreground)",
  mutedForeground: "var(--muted-foreground)",
  destructive: "var(--destructive)",
  borderRadius: "var(--radius-lg)",
  fontFamily: "var(--font-sans), ui-sans-serif, system-ui, sans-serif",
  cardClassName:
    "border border-white/10 bg-card shadow-2xl shadow-black/35 backdrop-blur-sm",
  inputClassName:
    "border-border/90 bg-background/40 transition focus:border-primary/50",
  socialButtonClassName: "border-border/80 hover:bg-muted/50",
});
