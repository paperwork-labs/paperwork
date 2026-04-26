import type { ReactNode } from "react";

/**
 * Auth shell for Clerk — matches FileFree dark canvas; height accounts for fixed
 * nav + `pt-14` in the root layout.
 */
export function ClerkAuthPageShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-[calc(100dvh-3.5rem)] overflow-hidden bg-background text-foreground">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_100%_70%_at_50%_-15%,hsl(263_70%_50%/0.18),transparent_55%)]"
        aria-hidden
      />
      <div className="relative z-10 flex min-h-[calc(100dvh-3.5rem)] flex-col items-center justify-center p-6">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </div>
  );
}
