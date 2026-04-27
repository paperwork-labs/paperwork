import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Auth backdrop for AxiomFolio — locked blue/amber radial gradient. The
 * brand wordmark + tagline previously lived here; they're now provided by
 * `<SignInShell>` from `@paperwork-labs/auth-clerk` so the entire monorepo
 * shares one wordmark pattern.
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
        {children}
      </div>
    </div>
  );
}
