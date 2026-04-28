import type { ReactNode } from "react";

/**
 * Full-viewport shell for sign-in / sign-up — neutral slate + cool accent (primary host).
 */
export function AccountsAuthPageShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950 text-slate-100">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_100%_70%_at_50%_-15%,rgba(148,163,184,0.18),transparent_50%),radial-gradient(ellipse_80%_50%_at_100%_0%,rgba(56,189,248,0.1),transparent_45%)]"
        aria-hidden
      />
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center p-6">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </div>
  );
}
