"use client";

import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { GitBranch, Globe, Menu, Sparkles } from "lucide-react";

import { BrainContextPicker } from "@/components/admin/BrainContextPicker";
import { HqPageContainer } from "@/components/admin/hq/HqPageContainer";
import { CommandPalette, openCommandPalette } from "@/components/admin/CommandPalette";
import { buildNavGroups, type NavGroup } from "@/lib/admin-navigation";

/** Shared hover surface for sidebar/header controls; `:focus-visible` ring from `globals.css`. */
const SIDEBAR_FOCUS_SURFACE =
  "rounded-lg outline-none hover:bg-zinc-800/40 motion-safe:transition-colors";

const FOOTER_VENDOR_LINKS: {
  category: string;
  icon: LucideIcon;
  links: { label: string; href: string }[];
}[] = [
  {
    category: "Hosting",
    icon: Globe,
    links: [
      { label: "Vercel", href: "https://vercel.com/paperwork-labs" },
      { label: "Render", href: "https://dashboard.render.com" },
      { label: "Cloudflare", href: "https://dash.cloudflare.com" },
    ],
  },
  {
    category: "Code",
    icon: GitBranch,
    links: [{ label: "GitHub", href: "https://github.com/paperwork-labs" }],
  },
  {
    category: "AI cost",
    icon: Sparkles,
    links: [
      { label: "Anthropic console", href: "https://console.anthropic.com" },
      { label: "OpenAI usage", href: "https://platform.openai.com/usage" },
    ],
  },
];

type Props = {
  children: React.ReactNode;
  founderPending: { count: number; hasCritical: boolean } | null;
  expensesPending: { count: number; hasCritical: boolean } | null;
  expensesCountsUnknown?: boolean;
};

function navItemIsActive(
  pathname: string,
  searchParams: URLSearchParams,
  itemHref: string
): boolean {
  const [pathPart, queryPart] = itemHref.split("?");
  if (queryPart) {
    if (pathname !== pathPart) return false;
    const want = new URLSearchParams(queryPart);
    for (const key of want.keys()) {
      if (searchParams.get(key) !== want.get(key)) return false;
    }
    return true;
  }
  if (itemHref === "/admin") return pathname === "/admin";
  if (!pathname.startsWith(pathPart)) return false;
  if (pathPart === "/admin/infrastructure" && searchParams.get("tab") === "cost") {
    return false;
  }
  return true;
}

function AdminSidebarPanel({
  pathname,
  searchParams,
  navGroups,
  expensesCountsUnknown,
  onNavLinkClick,
}: {
  pathname: string;
  searchParams: URLSearchParams;
  navGroups: NavGroup[];
  expensesCountsUnknown?: boolean;
  onNavLinkClick?: () => void;
}) {
  return (
    <div className="sticky top-8 rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4">
      <div className="mb-5 flex items-start justify-between gap-2">
        <Link
          href="/admin"
          data-testid="admin-sidebar-home-link"
          aria-label="Paperwork Studio — admin home"
          onClick={onNavLinkClick}
          className={`min-w-0 block p-1 ${SIDEBAR_FOCUS_SURFACE}`}
        >
          <span className="block text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-400">
            Paperwork Labs
          </span>
          <span className="mt-0.5 block text-lg font-bold leading-tight tracking-tight text-zinc-100">
            Studio
          </span>
        </Link>
        <kbd
          className="rounded border border-zinc-700/60 bg-zinc-800/80 px-1.5 py-0.5 font-mono text-[10px] font-medium text-zinc-400"
          title="Open command palette"
        >
          ⌘K
        </kbd>
      </div>
      <nav className="space-y-4" aria-label="Admin" data-testid="admin-sidebar-nav">
        {navGroups.map((group, groupIdx) => (
          <div key={group.label ?? `group-${groupIdx}`} className="space-y-1">
            {group.label ? (
              <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-zinc-400">
                {group.label}
              </p>
            ) : null}
            {group.items.map((item) => {
              const isActive = navItemIsActive(pathname, searchParams, item.href);
              const Icon = item.icon;
              const badge = item.pendingBadge;
              const showPendingBadge = badge && badge.count > 0;
              const staticCount = item.staticPendingCount;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavLinkClick}
                  className={`flex items-center justify-between gap-2 border-l-2 border-transparent rounded-lg px-3 py-2 text-sm motion-safe:transition-colors ${
                    isActive
                      ? "border-zinc-400 bg-zinc-800/80 font-medium text-zinc-100"
                      : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
                  }`}
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    <Icon
                      className={`h-4 w-4 shrink-0 ${
                        isActive ? "text-zinc-300" : "text-zinc-400"
                      }`}
                    />
                    <span className="truncate">{item.label}</span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end gap-0.5">
                    {item.href === "/admin/expenses" && expensesCountsUnknown ? (
                      <span
                        className="rounded-full border border-[var(--status-warning)]/35 bg-[var(--status-warning-bg)] px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-[var(--status-warning)]"
                        title="Could not load expense counts from Brain"
                      >
                        …
                      </span>
                    ) : null}
                    {showPendingBadge ? (
                      <span
                        data-testid={
                          item.href === "/admin/conversations"
                            ? "conversations-sidebar-badge"
                            : undefined
                        }
                        className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium tabular-nums ${
                          badge.hasCritical
                            ? "bg-[var(--status-danger-bg)] text-[var(--status-danger)]"
                            : "bg-[var(--status-warning-bg)] text-[var(--status-warning)]"
                        }`}
                        title="Pending founder-only items"
                      >
                        {badge.count} pending
                      </span>
                    ) : null}
                    {staticCount !== undefined ? (
                      <span
                        className="rounded-full bg-zinc-800/90 px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-zinc-400"
                        title="Expense approvals — live count in PR N"
                      >
                        {staticCount} pending
                      </span>
                    ) : null}
                  </span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      <div
        className="mt-6 border-t border-zinc-800/60 pt-4"
        data-testid="admin-vendor-footer"
      >
        <div className="space-y-3 text-xs">
          {FOOTER_VENDOR_LINKS.map((section) => (
            <div key={section.category} className="space-y-1">
              <p className="px-0.5 text-[10px] font-semibold uppercase tracking-widest text-zinc-400">
                {section.category}
              </p>
              <div className="space-y-1">
                {section.links.map((link) => (
                  <a
                    key={link.href + link.label}
                    href={link.href}
                    target="_blank"
                    rel="noreferrer"
                    onClick={onNavLinkClick}
                    className="flex items-center gap-2 text-zinc-400 motion-safe:transition-colors hover:text-zinc-300"
                  >
                    <section.icon
                      className="h-3 w-3 shrink-0 opacity-80"
                      aria-hidden
                    />
                    {link.label}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

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

  return (
    <div data-testid="admin-shell" className="min-h-screen overflow-x-hidden bg-zinc-950 text-zinc-100">
      <CommandPalette />

      <div
        data-testid="admin-mobile-drawer-backdrop"
        className={`fixed inset-0 z-[45] bg-black/60 motion-safe:transition-opacity md:hidden ${
          mobileNavOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
        aria-hidden={!mobileNavOpen}
        onClick={() => setMobileNavOpen(false)}
      />

      <aside
        id="admin-mobile-drawer"
        data-testid="admin-mobile-drawer"
        aria-hidden={!mobileNavOpen}
        className={`fixed inset-y-0 left-0 z-[50] w-60 max-w-[min(16rem,calc(100vw-2rem))] overflow-y-auto border-r border-zinc-800/80 bg-zinc-950 p-4 shadow-2xl motion-safe:transition-transform motion-safe:duration-200 motion-safe:ease-out md:hidden ${
          mobileNavOpen ? "translate-x-0" : "-translate-x-full pointer-events-none"
        }`}
      >
        <AdminSidebarPanel
          pathname={pathname}
          searchParams={searchParams}
          navGroups={navGroups}
          expensesCountsUnknown={expensesCountsUnknown}
          onNavLinkClick={() => setMobileNavOpen(false)}
        />
      </aside>

      <HqPageContainer variant="wide" className="flex gap-4 py-8 md:gap-8">
        <aside className="hidden w-60 shrink-0 md:block">
          <AdminSidebarPanel
            pathname={pathname}
            searchParams={searchParams}
            navGroups={navGroups}
            expensesCountsUnknown={expensesCountsUnknown}
          />
        </aside>
        <main className="min-w-0 flex-1">
          <div className="mb-6 flex items-center justify-end gap-3 border-b border-zinc-800/60 pb-4">
            <button
              type="button"
              data-testid="admin-mobile-menu-button"
              aria-label="Open navigation menu"
              aria-expanded={mobileNavOpen}
              aria-controls="admin-mobile-drawer"
              className="mr-auto -ml-2 rounded-lg p-2 text-zinc-400 motion-safe:transition-colors hover:bg-zinc-800 hover:text-zinc-100 md:hidden"
              onClick={() => setMobileNavOpen(true)}
            >
              <Menu className="h-5 w-5" aria-hidden />
            </button>
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
          {children}
        </main>
      </HqPageContainer>
    </div>
  );
}
