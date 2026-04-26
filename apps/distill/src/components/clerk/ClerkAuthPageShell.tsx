import type { ReactNode } from "react";

/**
 * Full-viewport dark shell for auth routes — teal + burnt orange glow (Distill).
 */
export function ClerkAuthPageShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950 text-slate-100">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_100%_70%_at_50%_-15%,rgba(15,118,110,0.25),transparent_50%),radial-gradient(ellipse_80%_50%_at_100%_0%,rgba(194,65,12,0.12),transparent_45%)]"
        aria-hidden
      />
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center p-6">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </div>
  );
}
