import type { ReactNode } from "react";
import Link from "next/link";

import { cn } from "@/lib/utils";
import AppLogo from "@/components/ui/AppLogo";

const TAGLINE = "Strategy-native portfolio intelligence";

/**
 * Full-viewport auth shell: AxiomFolio blue gradient, brand mark, and tagline
 * above the Clerk sign-in / sign-up card (matches `AuthLayout` treatment).
 */
export function ClerkAuthPageShell({ children }: { children: ReactNode }) {
  return (
    <div
      className={cn(
        "relative flex min-h-screen flex-col items-center justify-center px-4 py-10 text-white md:px-8 md:py-14",
        "bg-[rgb(var(--auth-gradient-bg))]",
      )}
      style={{
        background:
          "radial-gradient(1200px 600px at 20% 10%, rgb(var(--auth-gradient-blue) / 0.18), transparent 55%), radial-gradient(900px 500px at 85% 25%, rgb(var(--auth-gradient-amber) / 0.1), transparent 55%), rgb(var(--auth-gradient-bg))",
      }}
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(900px 500px at 50% 20%, rgb(var(--auth-gradient-glow) / 0.06), transparent 60%)",
        }}
        aria-hidden
      />
      <div className="relative w-full max-w-[420px] md:max-w-[440px]">
        <Link
          href="/"
          aria-label="AxiomFolio home"
          className={cn(
            "mb-6 flex items-center justify-center gap-3.5 rounded-sm",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-[rgb(var(--auth-gradient-bg))]",
          )}
        >
          <AppLogo size={64} />
          <div className="flex min-w-0 flex-col text-left">
            <span className="text-xl font-semibold tracking-tight text-white">AxiomFolio</span>
            <span className="text-sm font-normal text-slate-300/90">{TAGLINE}</span>
          </div>
        </Link>
        {children}
      </div>
    </div>
  );
}
