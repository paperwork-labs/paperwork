import { dark } from "@clerk/themes";

const amber = "#F59E0B";
const surface = "#0F172A";
const textPrimary = "#F8FAFC";
const textMuted = "#94A3B8";

/**
 * Paperwork Labs parent Clerk chrome for `accounts.paperworklabs.com` only.
 * Slate ink + single amber accent (no azure, no product hues).
 */
export const accountsClerkAppearance = {
  baseTheme: dark,
  variables: {
    colorPrimary: amber,
    colorBackground: surface,
    colorInputBackground: "#1E293B",
    colorInputText: textPrimary,
    colorText: textPrimary,
    colorTextSecondary: textMuted,
    colorDanger: "#F87171",
    borderRadius: "0.5rem",
    fontFamily: "var(--font-inter), ui-sans-serif, system-ui, sans-serif",
  },
  elements: {
    card: `border border-slate-700/80 bg-slate-900/60 shadow-2xl shadow-black/40`,
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm transition-colors hover:opacity-95 active:opacity-90",
    formFieldInput:
      "border-slate-600/90 bg-slate-900/50 transition focus:border-amber-500/70 focus:ring-amber-500/20",
    socialButtonsBlockButton:
      "border-slate-600/70 hover:bg-slate-800/60 hover:border-amber-500/40",
    footer: "hidden",
    footerAction: "hidden",
    footerActionText: "hidden",
    footerActionLink: "hidden",
    badge: "hidden",
    internal: "hidden",
    headerTitle: "text-[#F8FAFC]",
    headerSubtitle: "text-slate-400",
    formFieldLabel: "text-[#F8FAFC]/90",
    identityPreview: "bg-slate-800/60 border-slate-600/80",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-slate-800/80 focus:ring-2 focus:ring-amber-500/30",
    userButtonAvatarBox: `h-8 w-8 rounded-lg ring-1 ring-slate-600`,
  },
} as const;
