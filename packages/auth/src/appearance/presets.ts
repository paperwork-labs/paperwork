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
 * Track M: element classes use `brand.*` Tailwind tokens from each app's
 * `globals.css` + `tailwind.config.ts`.
 */

export const fileFreeAppearance: Appearance = createClerkAppearance({
  primary: "hsl(var(--primary))",
  cardClassName:
    "border border-brand-primary/35 bg-brand-surface/40 shadow-2xl shadow-black/30",
  inputClassName:
    "border-brand-primary/45 bg-brand-surface/50 transition focus:border-brand-accent/80",
  socialButtonClassName: "border-brand-primary/50 hover:bg-brand-primary/10",
  elementOverrides: {
    headerTitle: "text-foreground",
    headerSubtitle: "text-muted-foreground",
    formFieldLabel: "text-foreground/90",
    identityPreview: "bg-brand-primary/15 border-brand-primary/45",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-brand-accent/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/50",
  },
});

export const launchFreeAppearance: Appearance = createClerkAppearance({
  primary: "hsl(var(--primary))",
  cardClassName:
    "border border-brand-primary/30 bg-brand-surface/90 shadow-2xl shadow-black/30",
  inputClassName:
    "border-brand-primary/40 bg-brand-surface/70 transition focus:border-brand-accent",
  socialButtonClassName:
    "border-brand-primary/35 hover:bg-brand-primary/10 hover:border-brand-accent/40",
  elementOverrides: {
    headerTitle: "text-slate-100",
    headerSubtitle: "text-slate-400",
    formFieldLabel: "text-slate-200",
    identityPreview: "bg-brand-primary/10 border-brand-primary/35",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-brand-accent/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/45",
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
    "border border-brand-primary/40 bg-brand-surface/80 shadow-2xl shadow-black/30",
  inputClassName:
    "border-brand-primary/50 bg-brand-surface/60 transition focus:border-brand-primary",
  socialButtonClassName:
    "border-brand-primary/50 hover:bg-brand-primary/10 hover:border-brand-accent/40",
  primaryButtonClassName:
    "font-medium shadow-sm !bg-brand-primary hover:!brightness-110 active:!opacity-90 border-none",
  elementOverrides: {
    headerTitle: "text-slate-100",
    headerSubtitle: "text-slate-400",
    formFieldLabel: "text-slate-200",
    identityPreview: "bg-brand-primary/15 border-brand-primary/40",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-brand-primary/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-primary/50",
  },
});

export const studioAppearance: Appearance = createClerkAppearance({
  primary: "hsl(var(--primary))",
  cardClassName:
    "border border-brand-primary/25 bg-brand-surface/60 shadow-2xl shadow-black/30",
  inputClassName:
    "border-brand-primary/35 bg-brand-surface/50 transition focus:border-brand-accent",
  socialButtonClassName:
    "border-brand-primary/30 hover:bg-brand-primary/10 hover:border-brand-accent/35",
  elementOverrides: {
    headerTitle: "text-zinc-100",
    headerSubtitle: "text-zinc-400",
    formFieldLabel: "text-zinc-200",
    identityPreview: "bg-brand-primary/10 border-brand-primary/30",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-brand-accent/35",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/45",
  },
});

export const trinketsAppearance: Appearance = createClerkAppearance({
  primary: "#6366F1",
  accent: "#38BDF8",
  cardClassName:
    "border border-brand-primary/25 bg-brand-surface/85 shadow-2xl shadow-black/35",
  inputClassName:
    "border-brand-primary/35 bg-brand-surface/70 transition focus:border-brand-accent/80 focus:ring-brand-accent/20",
  socialButtonClassName:
    "border-brand-primary/40 hover:bg-brand-primary/10 hover:border-brand-accent/35",
  elementOverrides: {
    headerTitle: "text-stone-100",
    headerSubtitle: "text-stone-400",
    formFieldLabel: "text-stone-200",
    identityPreview: "bg-brand-primary/12 border-brand-primary/35",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-brand-accent/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/45",
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
