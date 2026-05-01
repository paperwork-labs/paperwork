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
 *
 * All presets use Clerk v7 variable names (`colorForeground`, `colorInput`, …)
 * and align contrast/readability with `studioAppearance` (zinc-type text,
 * sky focus rings, legible OAuth buttons).
 */

/** Shared focus ring (Paperwork sky / consistent a11y). */
const SKY_RING = "hsl(199 89% 48%)";

export const accountsAppearance: Appearance = createClerkAppearance({
  /** Paperwork sky — primary CTA / brand anchor for the auth host */
  primary: SKY_RING,
  accent: "hsl(199 89% 60%)",
  background: "hsl(222 47% 11%)",
  inputBackground: "hsl(216 34% 16%)",
  foreground: "hsl(210 40% 98%)",
  mutedForeground: "hsl(215 16% 57%)",
  destructive: "hsl(0 63% 31%)",
  primaryForeground: "hsl(210 40% 98%)",
  ring: SKY_RING,
  neutral: "hsl(215 16% 47%)",
  border: "hsl(216 34% 20%)",
  cardClassName:
    "border border-brand-primary/25 bg-brand-surface/60 shadow-2xl shadow-black/30",
  inputClassName:
    "border-brand-primary/35 bg-brand-surface/50 text-zinc-100 placeholder:text-zinc-500 transition focus:border-brand-accent focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-slate-950",
  socialButtonClassName:
    "border-brand-primary/30 bg-zinc-900/85 text-zinc-100 hover:bg-zinc-800/90 hover:border-brand-accent/35",
  primaryButtonClassName:
    "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90 text-zinc-50",
  elementOverrides: {
    headerTitle: "text-zinc-100",
    headerSubtitle: "text-zinc-400",
    formFieldLabel: "text-zinc-200",
    dividerText: "text-zinc-400",
    dividerLine: "bg-zinc-700",
    identityPreview: "bg-brand-primary/10 border-brand-primary/30",
    identityPreviewText: "text-zinc-100",
    identityPreviewEditButton: "text-sky-400 hover:text-sky-300",
    formResendCodeLink: "text-sky-400 hover:text-sky-300",
    otpCodeFieldInput:
      "border-brand-primary/35 bg-brand-surface/50 text-zinc-100 text-center tracking-widest transition focus:border-brand-accent focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-slate-950",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-sky-500/40 focus:ring-offset-2 focus:ring-offset-slate-950",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/45",
  },
});

export const fileFreeAppearance: Appearance = createClerkAppearance({
  primary: "hsl(var(--primary))",
  accent: SKY_RING,
  background: "hsl(240 10% 3.9%)",
  inputBackground: "hsl(240 3.7% 15.9%)",
  foreground: "hsl(0 0% 98%)",
  mutedForeground: "hsl(240 5% 64.9%)",
  destructive: "hsl(0 62.8% 30.6%)",
  primaryForeground: "hsl(210 40% 98%)",
  ring: SKY_RING,
  neutral: "hsl(240 4% 46%)",
  border: "hsl(240 3.7% 15.9%)",
  cardClassName:
    "border border-brand-primary/35 bg-brand-surface/40 shadow-2xl shadow-black/30",
  inputClassName:
    "border-brand-primary/45 bg-brand-surface/50 text-zinc-100 placeholder:text-zinc-500 transition focus:border-brand-accent/80 focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
  socialButtonClassName:
    "border-brand-primary/50 bg-zinc-900/85 text-zinc-100 hover:bg-zinc-800/90 hover:border-brand-accent/40",
  primaryButtonClassName:
    "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90 text-zinc-50",
  elementOverrides: {
    headerTitle: "text-zinc-100",
    headerSubtitle: "text-zinc-400",
    formFieldLabel: "text-zinc-200",
    dividerText: "text-zinc-400",
    dividerLine: "bg-zinc-700",
    identityPreview: "bg-brand-primary/15 border-brand-primary/45",
    identityPreviewText: "text-zinc-100",
    identityPreviewEditButton: "text-sky-400 hover:text-sky-300",
    formResendCodeLink: "text-sky-400 hover:text-sky-300",
    otpCodeFieldInput:
      "border-brand-primary/45 bg-brand-surface/50 text-zinc-100 text-center tracking-widest transition focus:border-brand-accent/80 focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-sky-500/40 focus:ring-offset-2 focus:ring-offset-zinc-950",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/50",
  },
});

export const launchFreeAppearance: Appearance = createClerkAppearance({
  primary: "hsl(var(--primary))",
  accent: SKY_RING,
  background: "hsl(224 47% 7%)",
  inputBackground: "hsl(217 33% 17%)",
  foreground: "hsl(210 40% 98%)",
  mutedForeground: "hsl(215 16% 57%)",
  destructive: "hsl(0 62.8% 30.6%)",
  primaryForeground: "hsl(210 40% 98%)",
  ring: SKY_RING,
  neutral: "hsl(215 16% 47%)",
  border: "hsl(217 33% 22%)",
  cardClassName:
    "border border-brand-primary/30 bg-brand-surface/90 shadow-2xl shadow-black/30",
  inputClassName:
    "border-brand-primary/40 bg-brand-surface/70 text-zinc-100 placeholder:text-zinc-500 transition focus:border-brand-accent focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
  socialButtonClassName:
    "border-brand-primary/35 bg-zinc-900/85 text-zinc-100 hover:bg-zinc-800/90 hover:border-brand-accent/40",
  primaryButtonClassName:
    "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90 text-zinc-50",
  elementOverrides: {
    headerTitle: "text-zinc-100",
    headerSubtitle: "text-zinc-400",
    formFieldLabel: "text-zinc-200",
    dividerText: "text-zinc-400",
    dividerLine: "bg-zinc-700",
    identityPreview: "bg-brand-primary/10 border-brand-primary/35",
    identityPreviewText: "text-zinc-100",
    identityPreviewEditButton: "text-sky-400 hover:text-sky-300",
    formResendCodeLink: "text-sky-400 hover:text-sky-300",
    otpCodeFieldInput:
      "border-brand-primary/40 bg-brand-surface/70 text-zinc-100 text-center tracking-widest transition focus:border-brand-accent focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-sky-500/40 focus:ring-offset-2 focus:ring-offset-zinc-950",
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
  primaryForeground: "hsl(210 40% 98%)",
  ring: SKY_RING,
  neutral: "hsl(215 16% 47%)",
  border: "hsl(216 25% 20%)",
  cardClassName:
    "border border-brand-primary/40 bg-brand-surface/80 shadow-2xl shadow-black/30",
  inputClassName:
    "border-brand-primary/50 bg-brand-surface/60 text-zinc-100 placeholder:text-zinc-500 transition focus:border-brand-primary focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
  socialButtonClassName:
    "border-brand-primary/50 bg-zinc-900/85 text-zinc-100 hover:bg-zinc-800/90 hover:border-brand-accent/40",
  primaryButtonClassName:
    "font-medium shadow-sm !bg-brand-primary hover:!brightness-110 active:!opacity-90 border-none text-zinc-50",
  elementOverrides: {
    headerTitle: "text-zinc-100",
    headerSubtitle: "text-zinc-400",
    formFieldLabel: "text-zinc-200",
    dividerText: "text-zinc-400",
    dividerLine: "bg-zinc-700",
    identityPreview: "bg-brand-primary/15 border-brand-primary/40",
    identityPreviewText: "text-zinc-100",
    identityPreviewEditButton: "text-sky-400 hover:text-sky-300",
    formResendCodeLink: "text-sky-400 hover:text-sky-300",
    otpCodeFieldInput:
      "border-brand-primary/50 bg-brand-surface/60 text-zinc-100 text-center tracking-widest transition focus:border-brand-primary focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-sky-500/40 focus:ring-offset-2 focus:ring-offset-zinc-950",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-primary/50",
  },
});

export const studioAppearance: Appearance = createClerkAppearance({
  primary: "hsl(var(--primary))",
  accent: "hsl(199 89% 48%)",
  background: "hsl(240 10% 3.9%)",
  inputBackground: "hsl(240 3.7% 15.9%)",
  foreground: "hsl(0 0% 98%)",
  mutedForeground: "hsl(240 5% 64.9%)",
  destructive: "hsl(0 62.8% 30.6%)",
  primaryForeground: "hsl(210 40% 98%)",
  ring: "hsl(199 89% 48%)",
  neutral: "hsl(240 4% 46%)",
  border: "hsl(240 3.7% 15.9%)",
  cardClassName:
    "border border-brand-primary/25 bg-brand-surface/60 shadow-2xl shadow-black/30",
  inputClassName:
    "border-brand-primary/35 bg-brand-surface/50 text-zinc-100 placeholder:text-zinc-500 transition focus:border-brand-accent focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
  socialButtonClassName:
    "border-brand-primary/30 bg-zinc-900/85 text-zinc-100 hover:bg-zinc-800/90 hover:border-brand-accent/35",
  primaryButtonClassName:
    "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90 text-zinc-50",
  elementOverrides: {
    headerTitle: "text-zinc-100",
    headerSubtitle: "text-zinc-400",
    formFieldLabel: "text-zinc-200",
    dividerText: "text-zinc-400",
    dividerLine: "bg-zinc-700",
    identityPreview: "bg-brand-primary/10 border-brand-primary/30",
    identityPreviewText: "text-zinc-100",
    identityPreviewEditButton: "text-sky-400 hover:text-sky-300",
    formResendCodeLink: "text-sky-400 hover:text-sky-300",
    otpCodeFieldInput:
      "border-brand-primary/35 bg-brand-surface/50 text-zinc-100 text-center tracking-widest transition focus:border-brand-accent focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-sky-500/40 focus:ring-offset-2 focus:ring-offset-zinc-950",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/45",
  },
});

export const trinketsAppearance: Appearance = createClerkAppearance({
  primary: "#6366F1",
  accent: "#38BDF8",
  background: "hsl(240 10% 3.9%)",
  inputBackground: "hsl(240 3.7% 15.9%)",
  foreground: "hsl(0 0% 98%)",
  mutedForeground: "hsl(240 5% 64.9%)",
  destructive: "hsl(0 62.8% 30.6%)",
  primaryForeground: "hsl(210 40% 98%)",
  ring: SKY_RING,
  neutral: "hsl(240 4% 46%)",
  border: "hsl(240 3.7% 15.9%)",
  cardClassName:
    "border border-brand-primary/25 bg-brand-surface/85 shadow-2xl shadow-black/35",
  inputClassName:
    "border-brand-primary/35 bg-brand-surface/70 text-zinc-100 placeholder:text-zinc-500 transition focus:border-brand-accent/80 focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
  socialButtonClassName:
    "border-brand-primary/40 bg-zinc-900/85 text-zinc-100 hover:bg-zinc-800/90 hover:border-brand-accent/35",
  primaryButtonClassName:
    "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90 text-zinc-50",
  elementOverrides: {
    headerTitle: "text-zinc-100",
    headerSubtitle: "text-zinc-400",
    formFieldLabel: "text-zinc-200",
    dividerText: "text-zinc-400",
    dividerLine: "bg-zinc-700",
    identityPreview: "bg-brand-primary/12 border-brand-primary/35",
    identityPreviewText: "text-zinc-100",
    identityPreviewEditButton: "text-sky-400 hover:text-sky-300",
    formResendCodeLink: "text-sky-400 hover:text-sky-300",
    otpCodeFieldInput:
      "border-brand-primary/35 bg-brand-surface/70 text-zinc-100 text-center tracking-widest transition focus:border-brand-accent/80 focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-brand-primary/10 focus:ring-2 focus:ring-sky-500/40 focus:ring-offset-2 focus:ring-offset-zinc-950",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-brand-accent/45",
  },
});

export const axiomfolioAppearance: Appearance = createClerkAppearance({
  primary: "var(--primary)",
  accent: SKY_RING,
  background: "var(--background)",
  inputBackground: "var(--input)",
  foreground: "var(--foreground)",
  mutedForeground: "var(--muted-foreground)",
  destructive: "var(--destructive)",
  primaryForeground: "var(--primary-foreground)",
  ring: SKY_RING,
  neutral: "var(--muted-foreground)",
  border: "var(--border)",
  borderRadius: "var(--radius-lg)",
  fontFamily: "var(--font-sans), ui-sans-serif, system-ui, sans-serif",
  cardClassName:
    "border border-white/10 bg-card shadow-2xl shadow-black/35 backdrop-blur-sm",
  inputClassName:
    "border-border/90 bg-background/40 text-zinc-100 placeholder:text-zinc-500 transition focus:border-primary/50 focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
  socialButtonClassName:
    "border-border/80 bg-zinc-900/85 text-zinc-100 hover:bg-zinc-800/90 hover:border-primary/35",
  primaryButtonClassName:
    "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90",
  elementOverrides: {
    headerTitle: "text-zinc-100",
    headerSubtitle: "text-zinc-400",
    formFieldLabel: "text-zinc-200",
    dividerText: "text-zinc-400",
    dividerLine: "bg-zinc-700",
    formResendCodeLink: "text-sky-400 hover:text-sky-300",
    otpCodeFieldInput:
      "border-border/90 bg-background/40 text-zinc-100 text-center tracking-widest transition focus:border-primary/50 focus:ring-2 focus:ring-sky-500/55 focus:ring-offset-2 focus:ring-offset-zinc-950",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-muted/50 focus:ring-2 focus:ring-sky-500/40 focus:ring-offset-2 focus:ring-offset-zinc-950",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-primary/45",
  },
});
