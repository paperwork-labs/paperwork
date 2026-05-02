"use client";

import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { GitBranch, Globe, Sparkles } from "lucide-react";

import type { NavGroup } from "@/lib/admin-navigation";

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
      { label: "Hetzner", href: "https://console.hetzner.cloud/" },
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

function navItemIsActive(
  pathname: string,
  searchParams: URLSearchParams,
  itemHref: string,
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
  /** Prefix match only at segment boundaries (/admin/foo matches /admin/foo/bar, not /admin/foobar). */
  const segmentMatches =
    pathPart === "/admin"
      ? pathname === "/admin"
      : pathname === pathPart || pathname.startsWith(`${pathPart}/`);
  if (!segmentMatches) return false;
  if (pathPart === "/admin/infrastructure" && searchParams.get("tab") === "cost") {
    return false;
  }
  return true;
}

export type AdminSidebarNavProps = {
  pathname: string;
  searchParams: URLSearchParams;
  navGroups: NavGroup[];
  expensesCountsUnknown?: boolean;
  /** Called after an in-app navigation or external footer link is activated (e.g. close mobile drawer). */
  onNavigate?: () => void;
};

export function AdminSidebarNav({
  pathname,
  searchParams,
  navGroups,
  expensesCountsUnknown,
  onNavigate,
}: AdminSidebarNavProps) {
  return (
    <div className="sticky top-8 rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4">
      <div className="mb-5 flex items-start justify-between gap-2">
        <Link
          href="/admin"
          data-testid="admin-sidebar-home-link"
          aria-label="Paperwork Studio — admin home"
          onClick={onNavigate}
          className={`min-w-0 block p-1 max-lg:min-h-11 max-lg:px-3 max-lg:py-2 ${SIDEBAR_FOCUS_SURFACE}`}
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
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  className={`flex max-lg:min-h-11 items-center justify-between gap-2 rounded-lg border-l-2 border-transparent px-3 py-2 text-sm motion-safe:transition-colors ${
                    isActive
                      ? "border-emerald-400/85 bg-zinc-800/80 font-medium text-zinc-100"
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
        <p
          className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-zinc-500"
          data-testid="admin-shortcuts-hint"
        >
          <span className="whitespace-nowrap">
            <kbd className="rounded border border-zinc-700/60 bg-zinc-800/80 px-1 py-0.5 font-mono text-[10px] font-medium text-zinc-400">
              ⌘K
            </kbd>{" "}
            Command palette
          </span>
          <span className="text-zinc-600">·</span>
          <span className="whitespace-nowrap">
            <kbd className="rounded border border-zinc-700/60 bg-zinc-800/80 px-1 py-0.5 font-mono text-[10px] font-medium text-zinc-400">
              ?
            </kbd>{" "}
            Shortcuts
          </span>
        </p>
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
                    onClick={onNavigate}
                    className="flex items-center gap-2 text-zinc-400 motion-safe:transition-colors hover:text-zinc-300 max-lg:min-h-11 max-lg:rounded-lg max-lg:px-2 max-lg:py-2 max-lg:hover:bg-zinc-800/40"
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
