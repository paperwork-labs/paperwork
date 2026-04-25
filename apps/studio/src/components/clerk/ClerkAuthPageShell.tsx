import type { ReactNode } from "react";

/**
 * Full-viewport dark shell for auth routes — matches /admin’s zinc-950 + subtle glow
 * (see `ClerkAuthPageShell` in sign-in / sign-up pages). No heavy deps.
 */
export function ClerkAuthPageShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-zinc-950 text-zinc-100">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_100%_70%_at_50%_-15%,hsl(240_5%_40%/0.22),transparent_55%)]"
        aria-hidden
      />
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center p-6">
        {children}
      </div>
    </div>
  );
}
