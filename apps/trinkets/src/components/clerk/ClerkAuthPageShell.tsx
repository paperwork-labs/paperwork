import type { ReactNode } from "react";

/**
 * Full-viewport dark shell for auth routes — stone-950 + indigo + sky cyan glow
 * (Trinkets locked palette).
 */
export function ClerkAuthPageShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-stone-950 text-amber-50">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_100%_70%_at_50%_-15%,rgb(99_102_241/0.22),transparent_55%)]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_100%_100%,rgb(56_189_248/0.12),transparent_50%)]"
        aria-hidden
      />
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center p-6">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </div>
  );
}
