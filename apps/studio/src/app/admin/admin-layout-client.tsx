"use client";

import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Settings2,
  Shield,
  Rocket,
  Target,
  Boxes,
  BookOpen,
  Sparkles,
  GitBranch,
  Kanban,
  Workflow,
  Receipt,
  Users,
  MessageSquare,
} from "lucide-react";

type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  /** Pending founder-only items (Conversations nav — data from founder-actions sync until PR E) */
  pendingBadge?: { count: number; hasCritical: boolean } | null;
  /** Static sidebar count; always rendered including 0 (PR N wires Expenses) */
  staticPendingCount?: number;
};

type NavGroup = {
  label: string | null;
  items: NavItem[];
};

function buildNavGroups(
  founderPending: { count: number; hasCritical: boolean } | null,
  expensesPending: { count: number; hasCritical: boolean } | null
): NavGroup[] {
  return [
    {
      label: null,
      items: [{ href: "/admin", label: "Overview", icon: LayoutDashboard }],
    },
    {
      label: "Trackers",
      items: [
        { href: "/admin/tasks", label: "Tasks (company)", icon: Target },
        { href: "/admin/products", label: "Products", icon: Boxes },
        { href: "/admin/sprints", label: "Sprints", icon: Rocket },
        { href: "/admin/workstreams", label: "Workstreams", icon: Kanban },
        { href: "/admin/pr-pipeline", label: "PR pipeline", icon: GitBranch },
        {
          href: "/admin/expenses",
          label: "Expenses",
          icon: Receipt,
          pendingBadge: expensesPending,
        },
      ],
    },
    {
      label: "Architecture",
      items: [
        { href: "/admin/architecture", label: "Architecture", icon: Workflow },
        { href: "/admin/docs", label: "Docs", icon: BookOpen },
        { href: "/admin/infrastructure", label: "Infrastructure", icon: Shield },
      ],
    },
    {
      label: "Brain",
      items: [
        { href: "/admin/brain/personas", label: "Personas", icon: Users },
        {
          href: "/admin/brain/conversations",
          label: "Conversations",
          icon: MessageSquare,
          pendingBadge: founderPending,
        },
        {
          href: "/admin/brain/self-improvement",
          label: "Self-improvement",
          icon: Sparkles,
        },
      ],
    },
  ];
}

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
  {
    category: "Comms",
    links: [
      {
        label: "Slack #brain-status",
        href: "https://app.slack.com/client",
      },
    ],
  },
];

type Props = {
  children: React.ReactNode;
  /** Null only when caller could not derive counts (layout throws on bad JSON) */
  founderPending: { count: number; hasCritical: boolean } | null;
  /** Null if expenses data failed to load */
  expensesPending: { count: number; hasCritical: boolean } | null;
};

export function AdminLayoutClient({ children, founderPending, expensesPending }: Props) {
  const pathname = usePathname();
  const navGroups = buildNavGroups(founderPending, expensesPending);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto flex w-full max-w-7xl gap-8 px-6 py-8">
        <aside className="w-60 shrink-0">
          <div className="sticky top-8 rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4">
            <p className="mb-5 bg-gradient-to-r from-zinc-300 to-zinc-500 bg-clip-text text-xs font-semibold uppercase tracking-widest text-transparent">
              Command Center
            </p>
            <nav className="space-y-4" aria-label="Admin">
              {navGroups.map((group, groupIdx) => (
                <div
                  key={group.label ?? `group-${groupIdx}`}
                  className="space-y-1"
                >
                  {group.label ? (
                    <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-zinc-600">
                      {group.label}
                    </p>
                  ) : null}
                  {group.items.map((item) => {
                    const isActive =
                      pathname === item.href ||
                      (item.href !== "/admin" &&
                        pathname.startsWith(item.href));
                    const Icon = item.icon;
                    const badge = item.pendingBadge;
                    const showPendingBadge = badge && badge.count > 0;
                    const staticCount = item.staticPendingCount;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                          isActive
                            ? "border-l-2 border-zinc-400 bg-zinc-800/80 font-medium text-zinc-100"
                            : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
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
                          {showPendingBadge ? (
                            <span
                              className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium tabular-nums ${
                                badge.hasCritical
                                  ? "bg-red-500/20 text-red-300"
                                  : "bg-amber-500/20 text-amber-200"
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
        </aside>
        <main className="min-w-0 flex-1">
          <div className="mb-6 flex items-center justify-end border-b border-zinc-800/60 pb-4">
            <UserButton />
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
