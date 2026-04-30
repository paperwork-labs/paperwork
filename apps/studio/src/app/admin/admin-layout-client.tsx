"use client";

import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, Settings2 } from "lucide-react";

import { HqPageContainer } from "@/components/admin/hq/HqPageContainer";
import { CommandPalette, openCommandPalette } from "@/components/admin/CommandPalette";
import { buildNavGroups, type NavGroup } from "@/lib/admin-navigation";

const FOOTER_VENDOR_LINKS: {
  category: string;
  links: { label: string; href: string }[];
}[] = [
  {
    category: "Hosting",
    links: [
      { label: "Vercel", href: "https://vercel.com/paperwork-labs" },
      { label: "Render", href: "https://dashboard.render.com" },
      { label: "Cloudflare", href: "https://dash.cloudflare.com" },
    ],
  },
  {
    category: "Code",
    links: [{ label: "GitHub", href: "https://github.com/paperwork-labs" }],
  },
  {
    category: "AI cost",
    links: [
      { label: "Anthropic console", href: "https://console.anthropic.com" },
      { label: "OpenAI usage", href: "https://platform.openai.com/usage" },
    ],
  },
];

type Props = {
  children: React.ReactNode;
  /** Null only when caller could not derive counts (layout throws on bad JSON) */
  founderPending: { count: number; hasCritical: boolean } | null;
  /** Null if expenses data failed to load */
  expensesPending: { count: number; hasCritical: boolean } | null;
  expensesCountsUnknown?: boolean;
};

function AdminSidebarPanel({
  pathname,
  navGroups,
  expensesCountsUnknown,
  onNavLinkClick,
}: {
  pathname: string;
  navGroups: NavGroup[];
  expensesCountsUnknown?: boolean;
  onNavLinkClick?: () => void;
}) {
  return (
    <div className="sticky top-8 rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4">
      <div className="mb-5 flex items-start justify-between gap-2">
        <p className="bg-gradient-to-r from-zinc-300 to-zinc-500 bg-clip-text text-xs font-semibold uppercase tracking-widest text-transparent">
          Command Center
        </p>
        <kbd
          className="rounded border border-zinc-700/60 bg-zinc-800/80 px-1.5 py-0.5 font-mono text-[10px] font-medium text-zinc-500"
          title="Open command palette"
        >
          ⌘K
        </kbd>
      </div>
      <nav className="space-y-4" aria-label="Admin" data-testid="admin-sidebar-nav">
        {navGroups.map((group, groupIdx) => (
          <div key={group.label ?? `group-${groupIdx}`} className="space-y-1">
            {group.label ? (
              <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-zinc-600">
                {group.label}
              </p>
            ) : null}
            {group.items.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/admin" && pathname.startsWith(item.href));
              const Icon = item.icon;
              const badge = item.pendingBadge;
              const showPendingBadge = badge && badge.count > 0;
              const staticCount = item.staticPendingCount;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavLinkClick}
                  className={`flex items-center justify-between gap-2 rounded-lg border-l-2 px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? "border-zinc-400 bg-zinc-800/80 font-medium text-zinc-100"
                      : "border-transparent text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
                  }`}
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    <Icon
                      className={`h-4 w-4 shrink-0 ${
                        isActive ? "text-zinc-300" : "text-zinc-500"
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
                          item.href === "/admin/brain/conversations"
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
                        className="rounded-full bg-zinc-800/90 px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-zinc-500"
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
              <p className="px-0.5 text-[10px] font-semibold uppercase tracking-widest text-zinc-600">
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
                    className="flex items-center gap-2 text-zinc-500 transition hover:text-zinc-300"
                  >
                    <Settings2 className="h-3 w-3 shrink-0" />
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
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const navGroups = buildNavGroups(founderPending, expensesPending);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <CommandPalette />

      <div
        data-testid="admin-mobile-drawer-backdrop"
        className={`fixed inset-0 z-[45] bg-black/60 transition-opacity md:hidden ${
          mobileNavOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
        aria-hidden={!mobileNavOpen}
        onClick={() => setMobileNavOpen(false)}
      />

      <aside
        id="admin-mobile-drawer"
        data-testid="admin-mobile-drawer"
        aria-hidden={!mobileNavOpen}
        className={`fixed inset-y-0 left-0 z-[50] w-60 max-w-[min(16rem,calc(100vw-2rem))] overflow-y-auto border-r border-zinc-800/80 bg-zinc-950 p-4 shadow-2xl transition-transform duration-200 ease-out md:hidden ${
          mobileNavOpen ? "translate-x-0" : "-translate-x-full pointer-events-none"
        }`}
      >
        <AdminSidebarPanel
          pathname={pathname}
          navGroups={navGroups}
          expensesCountsUnknown={expensesCountsUnknown}
          onNavLinkClick={() => setMobileNavOpen(false)}
        />
      </aside>

      <HqPageContainer variant="wide" className="flex gap-4 py-8 md:gap-8">
        <aside className="hidden w-60 shrink-0 md:block">
          <AdminSidebarPanel
            pathname={pathname}
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
              className="mr-auto -ml-2 rounded-lg p-2 text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-100 md:hidden"
              onClick={() => setMobileNavOpen(true)}
            >
              <Menu className="h-5 w-5" aria-hidden />
            </button>
            <button
              type="button"
              data-testid="admin-header-command-palette"
              onClick={() => openCommandPalette()}
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-700/80 bg-zinc-900/60 px-2.5 py-1.5 text-xs text-zinc-400 transition hover:border-zinc-600 hover:text-zinc-200"
              title="Search and jump (⌘K)"
            >
              <span className="hidden text-zinc-500 sm:inline">Search</span>
              <kbd className="rounded border border-zinc-700/60 bg-zinc-800/80 px-1 py-0.5 font-mono text-[10px] font-medium text-zinc-500">
                ⌘K
              </kbd>
            </button>
            <UserButton />
          </div>
          {children}
        </main>
      </HqPageContainer>
    </div>
  );
}
