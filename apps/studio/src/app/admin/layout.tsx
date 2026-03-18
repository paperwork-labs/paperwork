import Link from "next/link";

const navItems = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/ops", label: "Ops" },
  { href: "/admin/infrastructure", label: "Infrastructure" },
  { href: "/admin/sprints", label: "Sprints" },
  { href: "/admin/agents", label: "Agents" },
];

export default function AdminLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto flex w-full max-w-7xl gap-8 px-6 py-8">
        <aside className="w-52 shrink-0 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
          <p className="mb-4 text-xs uppercase tracking-wide text-zinc-400">Command Center</p>
          <nav className="space-y-2">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="block rounded-md px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-800 hover:text-zinc-100"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </aside>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}

