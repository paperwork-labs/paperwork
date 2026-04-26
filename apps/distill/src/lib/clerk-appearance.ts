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
    card: "border border-teal-900/50 bg-slate-950/70 shadow-2xl shadow-black/30",
    rootBox: "w-full",
    formButtonPrimary:
      "font-medium shadow-sm !bg-[#0F766E] hover:!bg-[#0D9488] active:!opacity-90 border-none",
    formFieldInput: "border-teal-800/80 bg-slate-950/50 transition focus:border-[#0F766E]",
    socialButtonsBlockButton:
      "border-teal-800/60 hover:bg-teal-950/50 hover:border-[#C2410C]/40",
    footer: "text-slate-500",
    headerTitle: "text-slate-100",
    headerSubtitle: "text-slate-400",
    formFieldLabel: "text-slate-200",
    identityPreview: "bg-teal-950/40 border-teal-800/50",
    userButtonTrigger:
      "rounded-lg p-0.5 transition hover:bg-teal-950/50 focus:ring-2 focus:ring-[#0F766E]/30",
    userButtonAvatarBox: "h-8 w-8 rounded-lg ring-1 ring-teal-800/60",
  },
} as const;
