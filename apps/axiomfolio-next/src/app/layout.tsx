import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AxiomFolio",
  description: "Strategy-native portfolio intelligence — Next.js shell (Track E).",
};

const NAV = [
  { href: "/", label: "Home" },
  { href: "/system-status", label: "System Status" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/scanner", label: "Scanner" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased">
        <header className="border-b border-zinc-800 bg-zinc-950/70 backdrop-blur">
          <div className="mx-auto flex w-full max-w-7xl items-center gap-6 px-6 py-4">
            <Link href="/" className="text-sm font-semibold tracking-tight text-zinc-100">
              AxiomFolio
            </Link>
            <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-300">
              next.js preview
            </span>
            <nav className="ml-auto flex items-center gap-4 text-sm text-zinc-400">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="transition hover:text-zinc-100"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl px-6 py-8">{children}</main>
        <footer className="border-t border-zinc-800 py-6 text-center text-[10px] uppercase tracking-wide text-zinc-600">
          AxiomFolio · Next.js preview · Track E · Paperwork Labs
        </footer>
      </body>
    </html>
  );
}
