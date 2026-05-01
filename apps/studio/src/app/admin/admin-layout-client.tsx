"use client";

import { UserButton } from "@clerk/nextjs";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Menu } from "lucide-react";

import { BrainContextPicker } from "@/components/admin/BrainContextPicker";
import { HqPageContainer } from "@/components/admin/hq/HqPageContainer";
import { CommandPalette, openCommandPalette } from "@/components/admin/CommandPalette";
import { buildNavGroups } from "@/lib/admin-navigation";

import { AdminSidebarNav } from "./admin-sidebar-nav";

type Props = {
  children: React.ReactNode;
  founderPending: { count: number; hasCritical: boolean } | null;
  expensesPending: { count: number; hasCritical: boolean } | null;
  expensesCountsUnknown?: boolean;
};

export function AdminLayoutClient({
  children,
  founderPending,
  expensesPending,
  expensesCountsUnknown = false,
}: Props) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const navGroups = buildNavGroups(founderPending, expensesPending);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileNavOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mobileNavOpen]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mobileNavOpen]);

  const sidebarNavProps = {
    pathname,
    searchParams,
    navGroups,
    expensesCountsUnknown,
  };

  return (
    <div data-testid="admin-shell" className="min-h-screen overflow-x-hidden bg-zinc-950 text-zinc-100">
      <CommandPalette />

      <header className="sticky top-0 z-[60] flex items-center gap-3 border-b border-zinc-800 bg-zinc-950/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-zinc-950/80 lg:hidden">
        <button
          type="button"
          data-testid="admin-mobile-menu-button"
          aria-label="Open navigation menu"
          aria-expanded={mobileNavOpen}
          aria-controls="admin-mobile-drawer"
          className="flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-lg px-3 py-2 text-zinc-400 motion-safe:transition-colors hover:bg-zinc-800 hover:text-zinc-100 lg:hidden"
          onClick={() => setMobileNavOpen((open) => !open)}
        >
          <Menu className="h-5 w-5" aria-hidden />
        </button>
        <span className="min-w-0 flex-1 truncate text-sm font-semibold text-zinc-100">
          Paperwork Labs Studio
        </span>
        <div className="flex min-h-11 min-w-11 shrink-0 items-center justify-center">
          <UserButton />
        </div>
      </header>

      {mobileNavOpen ? (
        <>
          <button
            type="button"
            data-testid="admin-mobile-drawer-backdrop"
            aria-label="Close menu"
            className="fixed inset-0 z-[45] bg-black/60 lg:hidden"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside
            id="admin-mobile-drawer"
            data-testid="admin-mobile-drawer"
            className="fixed left-0 top-0 z-50 h-full w-[min(18rem,calc(100vw-2rem))] max-w-[calc(100vw-2rem)] overflow-y-auto border-r border-zinc-800 bg-zinc-950 p-4 shadow-2xl lg:hidden"
            aria-modal="true"
            role="dialog"
            aria-label="Admin navigation"
          >
            <AdminSidebarNav {...sidebarNavProps} onNavigate={() => setMobileNavOpen(false)} />
          </aside>
        </>
      ) : null}

      <HqPageContainer variant="wide" className="flex gap-4 py-8 lg:gap-8">
        <aside className="hidden w-60 shrink-0 lg:block">
          <AdminSidebarNav {...sidebarNavProps} />
        </aside>
        <main className="min-w-0 flex-1">
          <div className="mb-6 hidden items-center justify-end gap-3 border-b border-zinc-800/60 pb-4 lg:flex">
            <button
              type="button"
              data-testid="admin-header-command-palette"
              onClick={() => openCommandPalette()}
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-700/80 bg-zinc-900/60 px-2.5 py-1.5 text-xs text-zinc-400 motion-safe:transition-colors hover:border-zinc-600 hover:text-zinc-200"
              title="Search and jump (⌘K)"
            >
              <span className="hidden text-zinc-400 sm:inline">Search</span>
              <kbd className="rounded border border-zinc-700/60 bg-zinc-800/80 px-1 py-0.5 font-mono text-[10px] font-medium text-zinc-400">
                ⌘K
              </kbd>
            </button>
            <BrainContextPicker />
            <UserButton />
          </div>

          <div className="mb-6 flex items-center justify-end gap-3 border-b border-zinc-800/60 pb-4 lg:hidden">
            <button
              type="button"
              data-testid="admin-mobile-command-palette"
              onClick={() => openCommandPalette()}
              className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg border border-zinc-700/80 bg-zinc-900/60 px-3 py-2 text-xs text-zinc-400 motion-safe:transition-colors hover:border-zinc-600 hover:text-zinc-200 sm:flex-none sm:justify-start"
              title="Search and jump (⌘K)"
            >
              <span className="text-zinc-400">Search</span>
              <kbd className="rounded border border-zinc-700/60 bg-zinc-800/80 px-1 py-0.5 font-mono text-[10px] font-medium text-zinc-400">
                ⌘K
              </kbd>
            </button>
            <BrainContextPicker />
          </div>

          {children}
        </main>
      </HqPageContainer>
    </div>
  );
}
