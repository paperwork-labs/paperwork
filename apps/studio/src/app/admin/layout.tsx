"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Activity,
  Settings2,
  Shield,
  KeyRound,
  Rocket,
  Bot,
  BarChart3,
} from "lucide-react";

const navItems = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard },
  { href: "/admin/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/admin/ops", label: "Ops", icon: Activity },
  { href: "/admin/infrastructure", label: "Infrastructure", icon: Shield },
  { href: "/admin/secrets", label: "Secrets", icon: KeyRound },
  { href: "/admin/sprints", label: "Sprints", icon: Rocket },
  { href: "/admin/agents", label: "Agents", icon: Bot },
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
            <nav className="space-y-1">
              {navItems.map((item) => {
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
                    <Icon className={`h-4 w-4 shrink-0 ${isActive ? "text-zinc-300" : "text-zinc-500"}`} />
                    {item.label}
                  </Link>
                );
              })}
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
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}

