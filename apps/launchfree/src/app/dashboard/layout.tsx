import type { ReactNode } from "react";
import Link from "next/link";
import { FileText, LayoutDashboard, PlusCircle, Rocket } from "lucide-react";

const navLinkClass =
  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-400 transition-colors hover:bg-slate-800/80 hover:text-teal-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400/50";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <div className="flex min-h-screen flex-col md:flex-row">
        <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-950/95 backdrop-blur-md md:hidden">
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            <Link
              href="/"
              className="flex items-center gap-2 font-semibold text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400/50"
            >
              <Rocket className="size-5 text-teal-400" aria-hidden />
              LaunchFree
            </Link>
            <details className="group relative">
              <summary className="flex cursor-pointer list-none items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-medium text-slate-200 marker:hidden [&::-webkit-details-marker]:hidden">
                <LayoutDashboard className="size-4 text-teal-400" aria-hidden />
                Menu
              </summary>
              <nav
                className="absolute right-0 mt-2 w-56 space-y-1 rounded-xl border border-slate-800 bg-slate-900 p-2 shadow-xl"
                aria-label="Dashboard navigation"
              >
                <Link href="/dashboard" className={navLinkClass}>
                  <LayoutDashboard className="size-4 shrink-0" aria-hidden />
                  My LLCs
                </Link>
                <Link href="/form" className={navLinkClass}>
                  <PlusCircle className="size-4 shrink-0" aria-hidden />
                  Start new LLC
                </Link>
              </nav>
            </details>
          </div>
        </header>

        <aside className="hidden w-56 shrink-0 border-r border-slate-800 bg-slate-950 md:flex md:flex-col">
          <div className="flex h-16 items-center gap-2 border-b border-slate-800 px-5">
            <Link
              href="/"
              className="flex items-center gap-2 font-semibold tracking-tight text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400/50"
            >
              <Rocket className="size-5 text-teal-400" aria-hidden />
              LaunchFree
            </Link>
          </div>
          <nav
            className="flex flex-1 flex-col gap-1 p-3"
            aria-label="Dashboard navigation"
          >
            <Link href="/dashboard" className={navLinkClass}>
              <LayoutDashboard className="size-4 shrink-0" aria-hidden />
              My LLCs
            </Link>
            <Link href="/form" className={navLinkClass}>
              <PlusCircle className="size-4 shrink-0" aria-hidden />
              Start new LLC
            </Link>
            <Link href="/" className={navLinkClass}>
              <FileText className="size-4 shrink-0" aria-hidden />
              Home
            </Link>
          </nav>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <main className="flex-1 px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
