"use client";

import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Settings2,
  Shield,
  KeyRound,
  Rocket,
  Bot,
  BarChart3,
  BookOpen,
  Workflow,
  Target,
  Boxes,
  Timer,
} from "lucide-react";

type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
};

type NavGroup = {
  label: string | null;
  items: NavItem[];
};

const navGroups: NavGroup[] = [
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
    ],
  },
  {
    label: "System",
    items: [
      { href: "/admin/architecture", label: "Architecture", icon: Workflow },
      { href: "/admin/workflows", label: "Workflows", icon: Bot },
      { href: "/admin/n8n-mirror", label: "n8n cron mirror", icon: Timer },
      { href: "/admin/docs", label: "Docs", icon: BookOpen },
      { href: "/admin/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/admin/infrastructure", label: "Infrastructure", icon: Shield },
      { href: "/admin/secrets", label: "Secrets", icon: KeyRound },
    ],
  },
];

export default function AdminLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto flex w-full max-w-7xl gap-8 px-6 py-8">
        <aside className="w-52 shrink-0">
          <div className="sticky top-8 rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4">
            <p className="mb-5 bg-gradient-to-r from-zinc-300 to-zinc-500 bg-clip-text text-xs font-semibold uppercase tracking-widest text-transparent">
              Command Center
            </p>
            <nav className="space-y-4">
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
                      (item.href !== "/admin" && pathname.startsWith(item.href));
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                          isActive
                            ? "border-l-2 border-zinc-400 bg-zinc-800/80 font-medium text-zinc-100"
                            : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
                        }`}
                      >
                        <Icon
                          className={`h-4 w-4 shrink-0 ${
                            isActive ? "text-zinc-300" : "text-zinc-500"
                          }`}
                        />
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              ))}
            </nav>
            <div className="mt-6 border-t border-zinc-800/60 pt-4">
              <div className="space-y-1.5 text-xs">
                <a
                  href="https://n8n.paperworklabs.com"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 text-zinc-500 transition hover:text-zinc-300"
                >
                  <Settings2 className="h-3 w-3" />
                  n8n editor
                </a>
                <a
                  href="https://vercel.com/paperwork-labs"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 text-zinc-500 transition hover:text-zinc-300"
                >
                  <Settings2 className="h-3 w-3" />
                  Vercel
                </a>
                <a
                  href="https://dashboard.render.com"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 text-zinc-500 transition hover:text-zinc-300"
                >
                  <Settings2 className="h-3 w-3" />
                  Render
                </a>
              </div>
            </div>
          </div>
        </aside>
        <main className="min-w-0 flex-1">
          <div className="mb-6 flex items-center justify-end border-b border-zinc-800/60 pb-4">
            {/* UserButton does not throw when the SSO Frontend API host is unreachable; it stays in a loading or signed-out state rather than crashing the tree. */}
            <UserButton />
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}

